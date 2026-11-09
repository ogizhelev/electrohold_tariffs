"""Tests for the HA-free Electrohold API client and parser."""
from __future__ import annotations

import pytest

from .fixtures import INCOMPLETE_PAGE_HTML, TARIFF_PAGE_HTML


def test_parse_tariffs_extracts_day_and_night(api):
    """A well-formed page yields the expected base prices."""
    tariffs = api.ElectroholdApiClient.parse_tariffs(TARIFF_PAGE_HTML)

    assert tariffs.day_base == pytest.approx(0.12854)
    assert tariffs.night_base == pytest.approx(0.07660)


def test_parse_tariffs_ignores_out_of_range_values(api):
    """The 1,50 € 'Друго' row must not be mistaken for a tariff."""
    tariffs = api.ElectroholdApiClient.parse_tariffs(TARIFF_PAGE_HTML)

    # Day and night bounds exclude 1.50, so only the real rows match.
    assert tariffs.day_base < 1.0
    assert tariffs.night_base < tariffs.day_base


def test_parse_tariffs_raises_when_incomplete(api):
    """Missing a required row surfaces a parse error naming what is missing."""
    with pytest.raises(api.ElectroholdParseError) as excinfo:
        api.ElectroholdApiClient.parse_tariffs(INCOMPLETE_PAGE_HTML)

    assert "night" in str(excinfo.value)


def test_parse_tariffs_raises_on_empty_html(api):
    """A page with no tables is a parse error, not a crash."""
    with pytest.raises(api.ElectroholdParseError):
        api.ElectroholdApiClient.parse_tariffs("<html><body>No data</body></html>")


def test_extract_euro_value_handles_both_separators(api):
    """Comma and dot decimal separators both parse to the same float."""
    extract = api.ElectroholdApiClient._extract_euro_value
    assert extract(["0,12478 €"], 0.0, None) == pytest.approx(0.12478)
    assert extract(["0.12478 €"], 0.0, None) == pytest.approx(0.12478)


def test_extract_euro_value_respects_bounds(api):
    """Values outside the [min, max] range are skipped."""
    extract = api.ElectroholdApiClient._extract_euro_value
    assert extract(["0,30 €"], 0.0, 0.10) is None
    assert extract(["0,02 €"], 0.05, None) is None
