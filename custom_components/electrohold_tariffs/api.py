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
    DAY_MAX_PRICE,
    DAY_MIN_PRICE,
    DEFAULT_TIMEOUT,
    ELECTROHOLD_URL,
    NIGHT_KEYWORD,
    NIGHT_MAX_PRICE,
    NIGHT_MIN_PRICE,
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
        """Parse day and night base tariffs out of raw HTML.

        Pure function: given the same HTML it always returns the same result
        and performs no I/O.
        """
        rows = cls._table_rows(BeautifulSoup(html, "html.parser"))

        day = cls._find_price(rows, DAY_KEYWORD, DAY_MIN_PRICE, DAY_MAX_PRICE)
        night = cls._find_price(rows, NIGHT_KEYWORD, NIGHT_MIN_PRICE, NIGHT_MAX_PRICE)

        missing = [name for name, value in (("day", day), ("night", night)) if value is None]
        if missing:
            raise ElectroholdParseError(
                f"Could not locate valid tariff values for: {', '.join(missing)}"
            )
        # Guaranteed non-None by the check above; asserted for the type checker.
        assert day is not None and night is not None

        tariffs = ElectroholdTariffs(day_base=day, night_base=night)
        _LOGGER.debug("Parsed tariffs: %s", tariffs)
        return tariffs

    @staticmethod
    def _table_rows(soup: BeautifulSoup) -> list[list[str]]:
        """Return every table row on the page as a list of cell texts."""
        rows: list[list[str]] = []
        for table in soup.find_all("table"):
            for row in table.find_all("tr"):
                cells = row.find_all(["td", "th"])
                rows.append([cell.get_text(strip=True) for cell in cells])
        return rows

    @classmethod
    def _find_price(
        cls,
        rows: list[list[str]],
        keyword: str,
        min_value: float,
        max_value: float | None,
    ) -> float | None:
        """Find the first in-range euro value in a row matching ``keyword``."""
        for cell_texts in rows:
            if not any(keyword in text for text in cell_texts):
                continue
            value = cls._extract_euro_value(cell_texts, min_value, max_value)
            if value is not None:
                return value
        return None

    @staticmethod
    def _extract_euro_value(
        cell_texts: list[str],
        min_value: float,
        max_value: float | None,
    ) -> float | None:
        """Extract the first euro value within ``[min_value, max_value]``."""
        for text in cell_texts:
            match = _EURO_VALUE_PATTERN.search(text)
            if not match:
                continue
            value = float(match.group(1).replace(",", "."))
            if value < min_value or (max_value is not None and value > max_value):
                _LOGGER.debug(
                    "Discarding out-of-range euro value %s from %r (bounds [%s, %s])",
                    value,
                    text,
                    min_value,
                    max_value,
                )
                continue
            return value
        return None
