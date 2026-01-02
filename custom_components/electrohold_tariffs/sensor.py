# /config/custom_components/electrohold_tariffs/sensor.py
import logging
import requests
from bs4 import BeautifulSoup
from datetime import timedelta
import voluptuous as vol
from homeassistant.components.sensor import SensorEntity, PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

# Configuration constants
CONF_TIMEZONE = "timezone"
DEFAULT_TIMEZONE = "Europe/Sofia"

# Configuration schema
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_TIMEZONE, default=DEFAULT_TIMEZONE): cv.string,
})

# Set the scan interval to update daily
SCAN_INTERVAL = timedelta(days=1)

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the electricity tariff sensors."""

    # Get timezone configuration, default to Europe/Sofia (Bulgaria)
    timezone = config.get(CONF_TIMEZONE, DEFAULT_TIMEZONE)
    
    # Create only 2 Euro sensors (day and night electricity price)
    day_euro_sensor = ElectricityTariffSensor("day_tariff_euro", "Day Euro", "electrohold_tariff_day_euro", "EUR/kWh")
    night_euro_sensor = ElectricityTariffSensor("night_tariff_euro", "Night Euro", "electrohold_tariff_night_euro", "EUR/kWh")

    # Add sensors
    add_entities([day_euro_sensor, night_euro_sensor])

class ElectricityTariffSensor(SensorEntity):
    """Representation of a Sensor to expose electricity tariff data."""

    def __init__(self, sensor_type, label, unique_id, unit_of_measurement):
        """Initialize the sensor."""
        self._sensor_type = sensor_type
        self._label = label
        self._unique_id = unique_id
        self._state = None
        self._unit_of_measurement = unit_of_measurement
        self._attr_should_poll = True  # Enable polling for regular updates
        
        # Perform initial update to get data immediately
        _LOGGER.info(f"Initializing sensor {self._sensor_type}, performing initial update")
        self.update()

    def update(self):
        """Fetch the current value from the website and update the sensor state."""
        _LOGGER.info(f"Starting update for sensor {self._sensor_type}")
        try:
            url = "https://electrohold.bg/bg/sales/domakinstva/snabdyavane-po-regulirani-ceni/"
            _LOGGER.info(f"Fetching data from: {url}")
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            _LOGGER.info(f"Successfully fetched webpage, status code: {response.status_code}")

            soup = BeautifulSoup(response.text, 'html.parser')

            # Parse tariff components from the webpage
            tariff_data = self._parse_tariff_components(soup)
            _LOGGER.info(f"Parsed tariff components: {tariff_data}")

            if not tariff_data:
                _LOGGER.error("Failed to parse tariff components - no data found")
                self._state = None
                return

            # Calculate final tariffs based on sensor type
            if self._sensor_type == "day_tariff_euro":
                # Day EUR tariff: Sum all components and apply VAT
                # Components: base_day + fee1 + fee2 + fee3 + fee4
                base_day = tariff_data.get('day_base', 0)
                fee1 = tariff_data.get('fee1', 0)  # 0,0076 €/кВтч
                fee2 = tariff_data.get('fee2', 0)  # 0,00018 €/кВтч
                fee3 = tariff_data.get('fee3', 0)  # 0,02374 €/кВтч
                fee4 = tariff_data.get('fee4', 0)  # 0,00371 €/кВтч
                
                total_before_vat = base_day + fee1 + fee2 + fee3 + fee4
                self._state = round(total_before_vat * 1.2, 5)
                _LOGGER.info(f"Day EUR tariff calculated: ({base_day} + {fee1} + {fee2} + {fee3} + {fee4}) * 1.2 = {self._state}")

            elif self._sensor_type == "night_tariff_euro":
                # Night EUR tariff: Sum all components and apply VAT
                base_night = tariff_data.get('night_base', 0)  # 0,07381 €/кВтч
                fee1 = tariff_data.get('fee1', 0)
                fee2 = tariff_data.get('fee2', 0)
                fee3 = tariff_data.get('fee3', 0)
                fee4 = tariff_data.get('fee4', 0)
                
                total_before_vat = base_night + fee1 + fee2 + fee3 + fee4
                self._state = round(total_before_vat * 1.2, 5)
                _LOGGER.info(f"Night EUR tariff calculated: ({base_night} + {fee1} + {fee2} + {fee3} + {fee4}) * 1.2 = {self._state}")

            _LOGGER.info(f"Update completed successfully for {self._sensor_type}, final state: {self._state}")

        except Exception as e:
            _LOGGER.error(f"Error fetching electricity tariff data for {self._sensor_type}: {e}")
            # Keep the previous state if available, otherwise set to None
            if self._state is None:
                self._state = None  # This will make the entity unavailable
            # Don't change _state if we already have a valid value from previous update

    def _parse_tariff_components(self, soup):
        """Parse the tariff components from the webpage."""
        components = {}

        try:
            # Find all table cells
            all_text = soup.get_text()
            
            # Target values to search for (with both comma and dot variations)
            # Map fee keys to human-readable descriptions
            target_values = {
                'fee1': {
                    'values': ['0,0076', '0.0076'],
                    'description': 'Public Service Obligation (PSO)'
                },
                'fee2': {
                    'values': ['0,00018', '0.00018'],
                    'description': 'Energy Security Fund'
                },
                'fee3': {
                    'values': ['0,02374', '0.02374'],
                    'description': 'Network Access Fee'
                },
                'fee4': {
                    'values': ['0,00371', '0.00371'],
                    'description': 'Excise Duty'
                },
                'day_base': {
                    'values': ['0,12478', '0.12478'],
                    'description': 'Day Base Tariff (Energy + Supply)'
                },
                'night_base': {
                    'values': ['0,07381', '0.07381'],
                    'description': 'Night Base Tariff (Energy + Supply)'
                }
            }
            
            _LOGGER.info("Starting to parse tariff components from webpage...")
            
            # Extract each component by searching for the specific values in Euro
            for key, config in target_values.items():
                found = False
                for value_str in config['values']:
                    if value_str in all_text:
                        # Convert to float (replace comma with dot)
                        numeric_value = float(value_str.replace(',', '.'))
                        components[key] = numeric_value
                        _LOGGER.info(f"✓ Found {config['description']}: {numeric_value} €/kWh (key: {key})")
                        found = True
                        break
                
                if not found:
                    _LOGGER.warning(f"✗ Could not find {config['description']} (key: {key}) - setting to 0")
                    components[key] = 0

            _LOGGER.info(f"Tariff parsing complete. Total components found: {len([v for v in components.values() if v > 0])}/{len(target_values)}")
            _LOGGER.debug(f"All parsed components: {components}")
            return components

        except Exception as e:
            _LOGGER.error(f"Error parsing tariff components: {e}")
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
