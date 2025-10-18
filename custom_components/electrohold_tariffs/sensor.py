# /config/custom_components/electrohold_tariffs/sensor.py
import logging
import requests
from bs4 import BeautifulSoup
from datetime import timedelta
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_NAME, CONF_UNIT_OF_MEASUREMENT

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(days=1)

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the electricity tariff sensors."""

    day_sensor = ElectricityTariffSensor("day_tariff", "Day", "electrohold_tariff_day", "BGN/kWh")
    night_sensor = ElectricityTariffSensor("night_tariff", "Night", "electrohold_tariff_night", "BGN/kWh")
    day_euro_sensor = ElectricityTariffSensor("day_tariff_euro", "Day Euro", "electrohold_tariff_day_euro", "EUR/kWh")
    night_euro_sensor = ElectricityTariffSensor("night_tariff_euro", "Night Euro", "electrohold_tariff_night_euro", "EUR/kWh")

    # Don't update during setup - let Home Assistant handle the update cycle
    add_entities([day_sensor, night_sensor, day_euro_sensor, night_euro_sensor])

class ElectricityTariffSensor(SensorEntity):
    """Representation of a Sensor to expose electricity tariff data."""

    def __init__(self, sensor_type, label, unique_id, unit_of_measurement):
        """Initialize the sensor."""
        self._sensor_type = sensor_type
        self._label = label
        self._unique_id = unique_id
        self._state = None
        self._unit_of_measurement = unit_of_measurement

    def update(self):
        """Fetch the current value from the website and update the sensor state."""
        try:
            url = "https://electrohold.bg/bg/sales/domakinstva/snabdyavane-po-regulirani-ceni/"
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Parse main tariffs (Дневна/Нощна)
            main_tariffs = self._parse_main_tariffs(soup)

            if not main_tariffs:
                _LOGGER.error("Failed to parse tariffs")
                self._state = None
                return

            # Calculate final tariffs based on sensor type (final prices already include network services, just add VAT)
            if self._sensor_type == "day_tariff":
                # BGN day tariff: Дневна BGN * 1.2 (add VAT)
                day_bgn = main_tariffs.get('day_bgn', 0)
                self._state = round(day_bgn * 1.2, 5)

            elif self._sensor_type == "night_tariff":
                # BGN night tariff: Нощна BGN * 1.2 (add VAT)
                night_bgn = main_tariffs.get('night_bgn', 0)
                self._state = round(night_bgn * 1.2, 5)

            elif self._sensor_type == "day_tariff_euro":
                # EUR day tariff: Дневна EUR * 1.2 (add VAT)
                day_eur = main_tariffs.get('day_eur', 0)
                self._state = round(day_eur * 1.2, 5)

            elif self._sensor_type == "night_tariff_euro":
                # EUR night tariff: Нощна EUR * 1.2 (add VAT)
                night_eur = main_tariffs.get('night_eur', 0)
                self._state = round(night_eur * 1.2, 5)

        except Exception as e:
            _LOGGER.error(f"Error fetching electricity tariff data: {e}")
            # Keep the previous state if available, otherwise set to None
            if self._state is None:
                self._state = None  # This will make the entity unavailable
            # Don't change _state if we already have a valid value from previous update

    def _parse_main_tariffs(self, soup):
        """Parse the main tariffs (Дневна/Нощна) from the webpage."""
        tariffs = {}

        try:
            # Find all table rows
            rows = soup.find_all('tr')

            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 6:  # Need at least 6 columns for the final prices
                    # Check if this row contains Дневна or Нощна
                    first_cell_text = cells[1].get_text(strip=True) if len(cells) > 1 else ""

                    if "Дневна" in first_cell_text:
                        # Extract the final prices (Крайни цени) which are in columns 4 and 5
                        # Column 4: BGN final price, Column 5: EUR final price
                        bgn_text = cells[4].get_text(strip=True) if len(cells) > 4 else ""
                        eur_text = cells[5].get_text(strip=True) if len(cells) > 5 else ""

                        tariffs['day_bgn'] = self._extract_numeric_value(bgn_text)
                        tariffs['day_eur'] = self._extract_numeric_value(eur_text)

                    elif "Нощна" in first_cell_text:
                        # Extract the final prices (Крайни цени) which are in columns 4 and 5
                        bgn_text = cells[4].get_text(strip=True) if len(cells) > 4 else ""
                        eur_text = cells[5].get_text(strip=True) if len(cells) > 5 else ""

                        tariffs['night_bgn'] = self._extract_numeric_value(bgn_text)
                        tariffs['night_eur'] = self._extract_numeric_value(eur_text)

            _LOGGER.debug(f"Parsed main tariffs: {tariffs}")
            return tariffs

        except Exception as e:
            _LOGGER.error(f"Error parsing main tariffs: {e}")
            return {}

    def _extract_numeric_value(self, text):
        """Extract numeric value from text."""
        try:
            import re
            # Replace comma with dot for decimal separator
            text = text.replace(',', '.')
            # Extract numeric part (including decimal)
            match = re.search(r'(\d+(?:\.\d+)?)', text)
            if match:
                return float(match.group(1))
            return None
        except Exception as e:
            _LOGGER.error(f"Error extracting numeric value from '{text}': {e}")
            return None

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"Electrohold Tariff {self._label}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state
    
    @property
    def available(self):
        """Return True if entity is available."""
        return self._state is not None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def device_class(self):
        """Return the class of the device."""
        return "monetary"

    @property
    def unique_id(self):
        """Return a unique ID for the sensor."""
        return self._unique_id
