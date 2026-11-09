"""Data models for the Electrohold Tariffs integration."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ElectroholdTariffs:
    """Immutable snapshot of the Electrohold electricity tariffs.

    Prices are the *base* prices in EUR/kWh. They already include every
    regulated fee published by the provider but **exclude** VAT. Converting
    to the final consumer price is the responsibility of the presentation
    layer (the sensors), keeping this model a pure data carrier.
    """

    day_base: float
    night_base: float
