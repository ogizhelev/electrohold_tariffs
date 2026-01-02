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
                # Day EUR tariff: Base price already includes all network fees, just apply 20% VAT
                base_day = tariff_data.get('day_base', 0)
                
                self._state = round(base_day * 1.2, 6)  # Apply 20% VAT
                _LOGGER.info(f"Day EUR tariff calculated: {base_day} * 1.2 = {self._state}")

            elif self._sensor_type == "night_tariff_euro":
                # Night EUR tariff: Base price already includes all network fees, just apply 20% VAT
                base_night = tariff_data.get('night_base', 0)
                
                self._state = round(base_night * 1.2, 6)  # Apply 20% VAT
                _LOGGER.info(f"Night EUR tariff calculated: {base_night} * 1.2 = {self._state}")

            _LOGGER.info(f"Update completed successfully for {self._sensor_type}, final state: {self._state}")

        except Exception as e:
            _LOGGER.error(f"Error fetching electricity tariff data for {self._sensor_type}: {e}")
            # Keep the previous state if available, otherwise set to None
            if self._state is None:
                self._state = None  # This will make the entity unavailable
            # Don't change _state if we already have a valid value from previous update

    def _parse_tariff_components(self, soup):
        """Parse the tariff components from the webpage dynamically."""
        components = {}

        try:
            import re
            
            _LOGGER.info("Starting to parse tariff components from webpage...")
            
            # Find all table rows to extract prices
            tables = soup.find_all('table')
            _LOGGER.info(f"Found {len(tables)} tables on the page")
            
            # Parse main tariff table (day/night prices)
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    cell_texts = [cell.get_text(strip=True) for cell in cells]
                    
                    # Look for day tariff row (contains "Дневна")
                    if any('Дневна' in text for text in cell_texts):
                        _LOGGER.info(f"Found day tariff row: {cell_texts}")
                        # Extract the Euro value from the appropriate column
                        for text in cell_texts:
                            # Match pattern like "0,12478 €/кВтч" or "0.12478"
                            match = re.search(r'(\d+[,\.]\d+)\s*€', text)
                            if match:
                                value_str = match.group(1).replace(',', '.')
                                value = float(value_str)
                                # The 4th column should be the final price with all network fees included (without VAT)
                                if value > 0.1:  # Day price should be > 0.1
                                    components['day_base'] = value
                                    _LOGGER.info(f"✓ Found Day Base Tariff (with all fees, before VAT): {value} €/kWh")
                                    break
                    
                    # Look for night tariff row (contains "Нощна")
                    elif any('Нощна' in text for text in cell_texts):
                        _LOGGER.info(f"Found night tariff row: {cell_texts}")
                        for text in cell_texts:
                            match = re.search(r'(\d+[,\.]\d+)\s*€', text)
                            if match:
                                value_str = match.group(1).replace(',', '.')
                                value = float(value_str)
                                # Night price should be between 0.05 and 0.1
                                if 0.05 < value < 0.1:
                                    components['night_base'] = value
                                    _LOGGER.info(f"✓ Found Night Base Tariff (with all fees, before VAT): {value} €/kWh")
                                    break
            
            # Verify required components were found
            expected_keys = ['day_base', 'night_base']
            missing_keys = [key for key in expected_keys if key not in components or components[key] == 0]
            
            if missing_keys:
                _LOGGER.warning(f"Could not find some components: {missing_keys}")
                # Set missing components to 0
                for key in missing_keys:
                    if key not in components:
                        components[key] = 0
            
            _LOGGER.info(f"Tariff parsing complete. Components found: {len([v for v in components.values() if v > 0])}/{len(expected_keys)}")
            _LOGGER.info(f"All parsed components: {components}")
            return components

        except Exception as e:
            _LOGGER.error(f"Error parsing tariff components: {e}", exc_info=True)
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
