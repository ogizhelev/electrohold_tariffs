"""Constants for the Electrohold Tariffs integration."""
from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "electrohold_tariffs"
MANUFACTURER: Final = "Electrohold"

# --- Data source -----------------------------------------------------------
ELECTROHOLD_URL: Final = (
    "https://electrohold.bg/bg/sales/domakinstva/snabdyavane-po-regulirani-ceni/"
)
# Tariff data changes very rarely; one fetch per day is more than enough.
SCAN_INTERVAL: Final = timedelta(days=1)
DEFAULT_TIMEOUT: Final = 10

# --- Parsing ---------------------------------------------------------------
# Bulgarian labels used to locate the day/night rows on the source page.
DAY_KEYWORD: Final = "Дневна"
NIGHT_KEYWORD: Final = "Нощна"

# Generous sanity bounds (EUR/kWh, before VAT) used to pick the right value out
# of a row that may contain several numbers (e.g. a fee column). They are wide
# enough to tolerate years of regulated price changes while still rejecting
# obviously-wrong figures such as a standing-charge in whole euros. They guard
# against *structure* surprises, not against the current price level.
DAY_MIN_PRICE: Final[float] = 0.10
DAY_MAX_PRICE: Final[float | None] = 0.60
NIGHT_MIN_PRICE: Final[float] = 0.05
NIGHT_MAX_PRICE: Final[float | None] = 0.40

# --- Pricing ---------------------------------------------------------------
# Bulgarian VAT is 20%. We keep the rate and derive the multiplier from it so
# there is a single source of truth.
VAT_RATE: Final = 0.20
VAT_MULTIPLIER: Final = 1.0 + VAT_RATE
# Number of decimals to keep on the final per-kWh price.
PRICE_PRECISION: Final = 6

# --- Entity keys -----------------------------------------------------------
SENSOR_KEY_DAY: Final = "day_euro"
SENSOR_KEY_NIGHT: Final = "night_euro"

# --- Extra state attribute keys -------------------------------------------
ATTR_BASE_PRICE: Final = "base_price_excl_vat"
ATTR_VAT_RATE: Final = "vat_rate"
ATTR_SOURCE_URL: Final = "source_url"
