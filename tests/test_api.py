"""Tests for the HA-free Electrohold API client and parser."""
from __future__ import annotations

import pytest

from .fixtures import (
    INCOMPLETE_PAGE_HTML,
    NO_HEADER_PAGE_HTML,
    RISEN_BASE_PAGE_HTML,
    TARIFF_PAGE_HTML,
    WITH_VAT_COLUMN_PAGE_HTML,
)


def test_parses_final_price_column_not_energy_column(api):
    """The FINAL (network-services-included) column is selected, not energy."""
    tariffs = api.ElectroholdApiClient.parse_tariffs(TARIFF_PAGE_HTML)

    assert tariffs.day_base == pytest.approx(0.12854)
    assert tariffs.night_base == pytest.approx(0.07660)


def test_selection_is_independent_of_price_magnitude(api):
    """Even when the energy base price rises above day values, pick final."""
    tariffs = api.ElectroholdApiClient.parse_tariffs(RISEN_BASE_PAGE_HTML)

    # Final column, not the (now larger) energy column.
    assert tariffs.day_base == pytest.approx(0.20000)
    assert tariffs.night_base == pytest.approx(0.16000)


def test_avoids_vat_inclusive_column(api):
    """A future 'с ДДС' column to the right must not be chosen."""
    tariffs = api.ElectroholdApiClient.parse_tariffs(WITH_VAT_COLUMN_PAGE_HTML)

    assert tariffs.day_base == pytest.approx(0.12854)
    assert tariffs.night_base == pytest.approx(0.07660)


def test_falls_back_to_rightmost_when_header_unreadable(api):
    """Without an understandable header, the right-most value is the final one."""
    tariffs = api.ElectroholdApiClient.parse_tariffs(NO_HEADER_PAGE_HTML)

    assert tariffs.day_base == pytest.approx(0.12854)
    assert tariffs.night_base == pytest.approx(0.07660)


def test_raises_when_incomplete(api):
    """Missing a required row surfaces a parse error."""
    with pytest.raises(api.ElectroholdParseError):
        api.ElectroholdApiClient.parse_tariffs(INCOMPLETE_PAGE_HTML)


def test_raises_on_empty_html(api):
    """A page with no tables is a parse error, not a crash."""
    with pytest.raises(api.ElectroholdParseError):
        api.ElectroholdApiClient.parse_tariffs("<html><body>No data</body></html>")


def test_sanity_range_rejects_absurd_values(api):
    """A standing charge in whole euros must not be accepted as a tariff."""
    html = """
    <html><body><table>
      <tr><th>Зони</th><th>Крайни цени с включени мрежови услуги</th></tr>
      <tr><td>Дневна</td><td>15,00 €</td></tr>
      <tr><td>Нощна</td><td>12,00 €</td></tr>
    </table></body></html>
    """
    with pytest.raises(api.ElectroholdParseError):
        api.ElectroholdApiClient.parse_tariffs(html)


def test_euro_value_handles_both_decimal_separators(api):
    """Comma and dot decimal separators both parse to the same float."""
    euro = api.ElectroholdApiClient._euro_value
    assert euro("0,12478 €/кВтч") == pytest.approx(0.12478)
    assert euro("0.12478 €") == pytest.approx(0.12478)
    assert euro("no price here") is None
