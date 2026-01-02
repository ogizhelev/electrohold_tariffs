"""Constants for the Electrohold Tariffs integration."""
from typing import Final

DOMAIN: Final = "electrohold_tariffs"

# Configuration constants
CONF_TIMEZONE: Final = "timezone"
DEFAULT_TIMEZONE: Final = "Europe/Sofia"

# Electrohold website URL
ELECTROHOLD_URL: Final = "https://electrohold.bg/bg/sales/domakinstva/snabdyavane-po-regulirani-ceni/"

# VAT rate (20%)
VAT_RATE: Final = 1.2

# Sensor types
SENSOR_TYPE_DAY: Final = "day_tariff_euro"
SENSOR_TYPE_NIGHT: Final = "night_tariff_euro"
