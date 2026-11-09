"""HTTP client and HTML scraper for the Electrohold tariff page.

The *parsing* side of this module (:meth:`ElectroholdApiClient.parse_tariffs`
and its helpers) imports no Home Assistant and does no I/O, so it can be unit
tested against a saved HTML fixture in complete isolation. The *fetching* side
uses :mod:`aiohttp` so it runs natively on Home Assistant's event loop with the
shared client session, rather than blocking in an executor thread.
"""
from __future__ import annotations

import asyncio
import logging
import re
from re import Pattern
from typing import Final

import aiohttp
from bs4 import BeautifulSoup

from .const import (
    DAY_KEYWORD,
    DEFAULT_TIMEOUT,
    ELECTROHOLD_URL,
    FINAL_PRICE_HINTS,
    NIGHT_KEYWORD,
    PRICE_COLUMN_HINTS,
    PRICE_SANITY_MAX,
    PRICE_SANITY_MIN,
    VAT_HINTS,
)
from .models import ElectroholdTariffs

_LOGGER = logging.getLogger(__name__)

# Matches values such as "0,12854 €" or "0.12854 €".
_EURO_VALUE_PATTERN: Final[Pattern[str]] = re.compile(r"(\d+[,.]\d+)\s*€")


class ElectroholdApiError(Exception):
    """Base class for all errors raised by :class:`ElectroholdApiClient`."""


class ElectroholdConnectionError(ElectroholdApiError):
    """The Electrohold website could not be reached."""


class ElectroholdParseError(ElectroholdApiError):
    """The tariff values could not be located on the page."""


class ElectroholdApiClient:
    """Fetch and parse electricity tariffs from the Electrohold website."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        url: str = ELECTROHOLD_URL,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize the client.

        Args:
            session: Shared aiohttp session (use Home Assistant's
                ``async_get_clientsession``).
            url: Page to scrape. Overridable mainly for testing.
            timeout: Total per-request timeout in seconds.
        """
        self._session = session
        self._url = url
        self._timeout = timeout

    async def async_fetch_tariffs(self) -> ElectroholdTariffs:
        """Return the current tariffs.

        Raises:
            ElectroholdConnectionError: The page could not be fetched.
            ElectroholdParseError: The page was fetched but could not be parsed.
        """
        html = await self._async_fetch_page()
        return self.parse_tariffs(html)

    async def _async_fetch_page(self) -> str:
        """Download the raw HTML of the tariff page."""
        _LOGGER.debug("Fetching Electrohold tariff page: %s", self._url)
        try:
            async with self._session.get(
                self._url, timeout=aiohttp.ClientTimeout(total=self._timeout)
            ) as response:
                response.raise_for_status()
                return await response.text()
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            raise ElectroholdConnectionError(
                f"Could not fetch tariff page {self._url}: {exc}"
            ) from exc

    @classmethod
    def parse_tariffs(cls, html: str) -> ElectroholdTariffs:
        """Parse the day and night *final* base prices (pre-VAT) from raw HTML.

        Pure function: given the same HTML it always returns the same result
        and performs no I/O. The correct value is chosen by column *meaning*
        (header text), not by price magnitude or position, so it is resilient
        to tariff changes and layout shifts. See :meth:`_extract_zone_price`
        for the fallback chain when the header cannot be understood.
        """
        soup = BeautifulSoup(html, "html.parser")

        for table in soup.find_all("table"):
            rows = [
                [cell.get_text(strip=True) for cell in row.find_all(["td", "th"])]
                for row in table.find_all("tr")
            ]
            target_ord, price_col_count = cls._locate_final_price_column(rows)

            day = cls._extract_zone_price(rows, DAY_KEYWORD, target_ord, price_col_count)
            night = cls._extract_zone_price(
                rows, NIGHT_KEYWORD, target_ord, price_col_count
            )
            if day is not None and night is not None:
                cls._warn_on_suspicious_pair(day, night)
                tariffs = ElectroholdTariffs(day_base=day, night_base=night)
                _LOGGER.debug("Parsed tariffs: %s", tariffs)
                return tariffs

        raise ElectroholdParseError(
            "Could not locate valid day and night tariff values on the page"
        )

    @classmethod
    def _locate_final_price_column(
        cls, rows: list[list[str]]
    ) -> tuple[int | None, int | None]:
        """Find the 'final price (incl. network services, excl. VAT)' column.

        Returns ``(target_ordinal, price_column_count)`` where ``target_ordinal``
        is the position of the target column *among the price columns only*
        (so leading label/rowspan cells are irrelevant), and
        ``price_column_count`` is how many price columns the header has. Returns
        ``(None, None)`` when no header can be understood, signalling the caller
        to fall back to positional extraction.
        """
        for row in rows:
            # A header row describes columns and carries no euro amounts.
            if any(cls._euro_value(cell) is not None for cell in row):
                continue

            price_cols = [
                index
                for index, cell in enumerate(row)
                if cls._contains_any(cell, PRICE_COLUMN_HINTS)
            ]
            if len(price_cols) < 2:
                continue  # need at least an energy column and a final column

            for ordinal, index in enumerate(price_cols):
                header = row[index]
                if cls._contains_any(header, FINAL_PRICE_HINTS) and not cls._contains_any(
                    header, VAT_HINTS
                ):
                    _LOGGER.debug(
                        "Final-price column located: header=%r (price column %d/%d)",
                        header,
                        ordinal + 1,
                        len(price_cols),
                    )
                    return ordinal, len(price_cols)

        _LOGGER.debug("No final-price header found; will fall back to position")
        return None, None

    @classmethod
    def _extract_zone_price(
        cls,
        rows: list[list[str]],
        keyword: str,
        target_ord: int | None,
        price_col_count: int | None,
    ) -> float | None:
        """Return the final price for the row labelled with ``keyword``.

        Selection is layered, most-robust first:
          1. Header-aligned: the Nth euro value, where N is the final-price
             column's ordinal among price columns (immune to magnitude, leading
             label cells and rowspan).
          2. Positional fallback: the last (right-most) euro value — the final
             price always sits to the right of the energy price.
        The chosen value must pass the sanity range or it is rejected.
        """
        for row in rows:
            if not any(keyword in cell for cell in row):
                continue

            euros = [
                value for cell in row if (value := cls._euro_value(cell)) is not None
            ]
            if not euros:
                continue

            chosen: float | None = None
            if (
                target_ord is not None
                and price_col_count is not None
                and len(euros) == price_col_count
                and target_ord < len(euros)
            ):
                chosen = euros[target_ord]
            else:
                chosen = euros[-1]
                _LOGGER.warning(
                    "Header-based column match unavailable for %s tariff; falling "
                    "back to the right-most euro value %s in row %s",
                    keyword,
                    chosen,
                    row,
                )

            if PRICE_SANITY_MIN <= chosen <= PRICE_SANITY_MAX:
                return chosen

            _LOGGER.warning(
                "Discarding %s tariff value %s: outside sanity range [%s, %s] (row %s)",
                keyword,
                chosen,
                PRICE_SANITY_MIN,
                PRICE_SANITY_MAX,
                row,
            )

        return None

    @staticmethod
    def _warn_on_suspicious_pair(day: float, night: float) -> None:
        """Log if the night price is not cheaper than the day price."""
        if night > day:
            _LOGGER.warning(
                "Night tariff %s is higher than day tariff %s — the source layout "
                "may have changed; please verify",
                night,
                day,
            )

    @staticmethod
    def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
        """Return True if ``text`` contains any needle (case-insensitive)."""
        lowered = text.lower()
        return any(needle in lowered for needle in needles)

    @staticmethod
    def _euro_value(text: str) -> float | None:
        """Return the first euro amount in ``text`` as a float, or None."""
        match = _EURO_VALUE_PATTERN.search(text)
        if not match:
            return None
        return float(match.group(1).replace(",", "."))
