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
# The source page lays each tariff out in a table whose columns are roughly:
#   [metering method] [day/night zone] [energy price] [FINAL price incl.
#   network services]
# Both price columns are published WITHOUT VAT. We want the FINAL column.
#
# The parser selects that value *semantically* — by matching the column header —
# rather than by price magnitude or cell position, so it keeps working when
# prices change, when label/rowspan cells shift the columns, or when a
# VAT-inclusive column is added later.

# Row labels identifying the two-rate day and night zones.
DAY_KEYWORD: Final = "Дневна"
NIGHT_KEYWORD: Final = "Нощна"

# Header matching (compared case-insensitively). A "price column" header
# contains one of PRICE_COLUMN_HINTS; the target column additionally matches
# FINAL_PRICE_HINTS (the end price with network services) and must NOT match
# VAT_HINTS (such a column already includes VAT and would be double-counted).
PRICE_COLUMN_HINTS: Final = ("цена", "цени")
FINAL_PRICE_HINTS: Final = ("крайн",)
VAT_HINTS: Final = ("ддс",)

# Pure sanity range (EUR/kWh, before VAT): rejects only absurd values such as a
# zero, a parsing glitch, or a standing charge in whole euros. It is NEVER used
# to choose between columns, only to reject a nonsensical final selection.
PRICE_SANITY_MIN: Final[float] = 0.01
PRICE_SANITY_MAX: Final[float] = 2.00

# --- Pricing ---------------------------------------------------------------
# Bulgarian VAT is 20%. We keep the rate and derive the multiplier from it so
# there is a single source of truth.
VAT_RATE: Final = 0.20
VAT_MULTIPLIER: Final = 1.0 + VAT_RATE
# Number of decimals to keep on the final per-kWh price.
PRICE_PRECISION: Final = 6

# --- Day/night schedule ----------------------------------------------------
# Regulated two-rate windows, expressed in local Europe/Sofia wall-clock time.
#   Night zone: 01.04–31.10 -> 23:00–07:00 ; 01.11–31.03 -> 22:00–06:00
#   Day zone:   the complement of the night zone
# The hours are half-open [start, end): e.g. 23:00 is night, 07:00 is day.
TARIFF_TIMEZONE: Final = "Europe/Sofia"
SUMMER_START_MONTH: Final = 4  # April, inclusive
SUMMER_END_MONTH: Final = 10  # October, inclusive
SUMMER_NIGHT_START_HOUR: Final = 23
SUMMER_NIGHT_END_HOUR: Final = 7
WINTER_NIGHT_START_HOUR: Final = 22
WINTER_NIGHT_END_HOUR: Final = 6

# --- Entity keys -----------------------------------------------------------
SENSOR_KEY_DAY: Final = "day_euro"
SENSOR_KEY_NIGHT: Final = "night_euro"
SENSOR_KEY_CURRENT: Final = "current_euro"

# --- Extra state attribute keys -------------------------------------------
ATTR_BASE_PRICE: Final = "base_price_excl_vat"
ATTR_VAT_RATE: Final = "vat_rate"
ATTR_SOURCE_URL: Final = "source_url"
ATTR_ACTIVE_TARIFF: Final = "active_tariff"
ATTR_SEASON: Final = "season"
ATTR_DAY_PRICE: Final = "day_price"
ATTR_NIGHT_PRICE: Final = "night_price"
