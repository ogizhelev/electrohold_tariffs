"""Day/night tariff schedule logic for the regulated Electrohold windows.

Pure and Home-Assistant-free so the seasonal window rules can be unit tested in
isolation. A moment is classified into the DAY or NIGHT zone according to the
regulated schedule:

    Night zone: 01.04–31.10 -> 23:00–07:00 ; 01.11–31.03 -> 22:00–06:00
    Day zone:   the complement of the night zone

All comparisons use the *local wall-clock* time of the supplied ``datetime``,
which must therefore already be expressed in Europe/Sofia time.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from .const import (
    SUMMER_END_MONTH,
    SUMMER_NIGHT_END_HOUR,
    SUMMER_NIGHT_START_HOUR,
    SUMMER_START_MONTH,
    WINTER_NIGHT_END_HOUR,
    WINTER_NIGHT_START_HOUR,
)


class TariffZone(str, Enum):
    """Which regulated tariff applies at a given moment."""

    DAY = "day"
    NIGHT = "night"


def is_summer_schedule(moment: datetime) -> bool:
    """Return True when the summer night window (23:00–07:00) is in effect."""
    return SUMMER_START_MONTH <= moment.month <= SUMMER_END_MONTH


def active_zone(moment: datetime) -> TariffZone:
    """Return the tariff zone in effect at ``moment`` (local Sofia time)."""
    if is_summer_schedule(moment):
        night_start, night_end = SUMMER_NIGHT_START_HOUR, SUMMER_NIGHT_END_HOUR
    else:
        night_start, night_end = WINTER_NIGHT_START_HOUR, WINTER_NIGHT_END_HOUR

    # Night wraps across midnight, so it is "at/after start" OR "before end".
    is_night = moment.hour >= night_start or moment.hour < night_end
    return TariffZone.NIGHT if is_night else TariffZone.DAY
