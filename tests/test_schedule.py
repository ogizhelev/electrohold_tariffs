"""Tests for the regulated day/night schedule logic."""
from __future__ import annotations

from datetime import datetime

import pytest


def _zone(schedule, month: int, hour: int) -> str:
    return schedule.active_zone(datetime(2026, month, 1, hour, 30)).value


@pytest.mark.parametrize(
    ("month", "hour", "expected"),
    [
        # Summer (Apr–Oct): night 23:00–07:00
        (7, 23, "night"),
        (7, 2, "night"),
        (7, 6, "night"),
        (7, 7, "day"),  # 07:00 is day
        (7, 12, "day"),
        (7, 22, "day"),  # still day until 23:00
        # Winter (Nov–Mar): night 22:00–06:00
        (1, 22, "night"),
        (1, 2, "night"),
        (1, 5, "night"),
        (1, 6, "day"),  # 06:00 is day
        (1, 12, "day"),
        (1, 21, "day"),
    ],
)
def test_active_zone(schedule, month, hour, expected):
    """Each boundary hour maps to the correct seasonal tariff zone."""
    assert _zone(schedule, month, hour) == expected


@pytest.mark.parametrize(
    ("month", "is_summer"),
    [(1, False), (3, False), (4, True), (10, True), (11, False), (12, False)],
)
def test_is_summer_schedule(schedule, month, is_summer):
    """April–October use the summer window; the rest use winter."""
    assert schedule.is_summer_schedule(datetime(2026, month, 15, 12)) is is_summer


def test_zone_enum_values_are_stable(schedule):
    """The string values are part of the sensor attribute contract."""
    assert schedule.TariffZone.DAY.value == "day"
    assert schedule.TariffZone.NIGHT.value == "night"
