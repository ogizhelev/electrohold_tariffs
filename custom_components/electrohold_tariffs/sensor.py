# /config/custom_components/electrohold_tariffs/sensor.py
import logging
import requests
from bs4 import BeautifulSoup
from datetime import timedelta
import pytz
import voluptuous as vol
from homeassistant.components.sensor import SensorEntity, PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_UNIT_OF_MEASUREMENT
from homeassistant.util import dt as dt_util
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

# Configuration constants
CONF_TIMEZONE = "timezone"
DEFAULT_TIMEZONE = "Europe/Sofia"

# Configuration schema
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_TIMEZONE, default=DEFAULT_TIMEZONE): cv.string,
})

# Set to 5 minutes for initial testing, change back to timedelta(days=1) after first successful update
# Set the scan interval to update daily for base tariff sensors
# Current price sensors will use a shorter interval to switch between day/night
SCAN_INTERVAL = timedelta(days=1)
CURRENT_PRICE_SCAN_INTERVAL = timedelta(minutes=15)

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the electricity tariff sensors."""

    # Get timezone configuration, default to Europe/Sofia (Bulgaria)
    timezone = config.get(CONF_TIMEZONE, DEFAULT_TIMEZONE)
    
    day_sensor = ElectricityTariffSensor("day_tariff", "Day", "electrohold_tariff_day", "BGN/kWh")
    night_sensor = ElectricityTariffSensor("night_tariff", "Night", "electrohold_tariff_night", "BGN/kWh")
    day_euro_sensor = ElectricityTariffSensor("day_tariff_euro", "Day Euro", "electrohold_tariff_day_euro", "EUR/kWh")
    night_euro_sensor = ElectricityTariffSensor("night_tariff_euro", "Night Euro", "electrohold_tariff_night_euro", "EUR/kWh")
    
    # Current price sensors that automatically switch between day/night based on time and season
    current_price_bgn_sensor = ElectroholdCurrentPriceSensor(hass, "bgn", "Current Price BGN", "electrohold_current_price_bgn", "BGN/kWh", timezone)
    current_price_euro_sensor = ElectroholdCurrentPriceSensor(hass, "euro", "Current Price EURO", "electrohold_current_price_euro", "EUR/kWh", timezone)

    # Add all sensors at once - current price sensors will handle unavailable base sensors gracefully
    add_entities([day_sensor, night_sensor, day_euro_sensor, night_euro_sensor, current_price_bgn_sensor, current_price_euro_sensor])

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

            # Parse main tariffs (Дневна/Нощна)
            main_tariffs = self._parse_main_tariffs(soup)
            _LOGGER.info(f"Parsed tariffs: {main_tariffs}")

            if not main_tariffs:
                _LOGGER.error("Failed to parse tariffs - no data found")
                self._state = None
                return

            # Calculate final tariffs based on sensor type (final prices already include network services, just add VAT)
            if self._sensor_type == "day_tariff":
                # BGN day tariff: Дневна BGN * 1.2 (add VAT)
                day_bgn = main_tariffs.get('day_bgn', 0)
                self._state = round(day_bgn * 1.2, 5)
                _LOGGER.info(f"Day BGN tariff calculated: {day_bgn} * 1.2 = {self._state}")

            elif self._sensor_type == "night_tariff":
                # BGN night tariff: Нощна BGN * 1.2 (add VAT)
                night_bgn = main_tariffs.get('night_bgn', 0)
                self._state = round(night_bgn * 1.2, 5)
                _LOGGER.info(f"Night BGN tariff calculated: {night_bgn} * 1.2 = {self._state}")

            elif self._sensor_type == "day_tariff_euro":
                # EUR day tariff: Дневна EUR * 1.2 (add VAT)
                day_eur = main_tariffs.get('day_eur', 0)
                self._state = round(day_eur * 1.2, 5)
                _LOGGER.info(f"Day EUR tariff calculated: {day_eur} * 1.2 = {self._state}")

            elif self._sensor_type == "night_tariff_euro":
                # EUR night tariff: Нощна EUR * 1.2 (add VAT)
                night_eur = main_tariffs.get('night_eur', 0)
                self._state = round(night_eur * 1.2, 5)
                _LOGGER.info(f"Night EUR tariff calculated: {night_eur} * 1.2 = {self._state}")

            _LOGGER.info(f"Update completed successfully for {self._sensor_type}, final state: {self._state}")

        except Exception as e:
            _LOGGER.error(f"Error fetching electricity tariff data for {self._sensor_type}: {e}")
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


class ElectroholdCurrentPriceSensor(SensorEntity):
    """Representation of a Current Price Sensor that switches between day/night tariffs based on time and season."""

    def __init__(self, hass, currency_type, label, unique_id, unit_of_measurement, timezone='Europe/Sofia'):
        """Initialize the current price sensor."""
        self._hass = hass
        self._currency_type = currency_type  # "bgn" or "euro"
        self._label = label
        self._unique_id = unique_id
        self._state = None
        self._unit_of_measurement = unit_of_measurement
        self._attr_should_poll = True
        
        # Timezone handling
        try:
            self._timezone = pytz.timezone(timezone)
        except pytz.UnknownTimeZoneError:
            _LOGGER.warning(f"Unknown timezone '{timezone}', falling back to Europe/Sofia")
            self._timezone = pytz.timezone('Europe/Sofia')
        
        # Additional attributes
        self._tariff_type = None
        self._season = None
        self._day_tariff = None
        self._night_tariff = None
        self._last_valid_state = None  # Store last known good state
        self._initialization_complete = False  # Track if we've successfully initialized once
        
        # Override scan interval for current price sensors
        self._scan_interval = CURRENT_PRICE_SCAN_INTERVAL
        
        _LOGGER.info(f"Initializing current price sensor {self._currency_type} with timezone {self._timezone}")
        
        # Perform initial update to set up the sensor
        self.update()

    def update(self):
        """Update the sensor state based on current time and season."""
        try:
            # Get current time in the configured timezone
            utc_now = dt_util.utcnow()
            local_now = utc_now.astimezone(self._timezone)
            hour = local_now.hour
            month = local_now.month
            
            _LOGGER.debug(f"Current time in {self._timezone}: {local_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            
            # Determine if it's summer (April-October) or winter (November-March)
            is_summer = 4 <= month <= 10
            
            # Determine if it's night time based on season
            if is_summer:
                # Summer: Night rate 23:00-07:00
                is_night = hour >= 23 or hour < 7
            else:
                # Winter: Night rate 22:00-06:00
                is_night = hour >= 22 or hour < 6
            
            _LOGGER.debug(f"Season: {'Summer' if is_summer else 'Winter'}, Is night: {is_night}, Hour: {hour}, Month: {month}")
            
            # Get the appropriate sensor entity IDs based on currency type
            if self._currency_type == "bgn":
                day_sensor_id = "sensor.electrohold_tariff_day"
                night_sensor_id = "sensor.electrohold_tariff_night"
            else:  # euro
                day_sensor_id = "sensor.electrohold_tariff_day_euro"
                night_sensor_id = "sensor.electrohold_tariff_night_euro"
            
            # Debug: Check what we're getting from base sensors
            day_state_check = self._hass.states.get(day_sensor_id)
            night_state_check = self._hass.states.get(night_sensor_id)
            _LOGGER.debug(f"Base sensor check for {self._currency_type}: day={day_state_check.state if day_state_check else 'None'}, night={night_state_check.state if night_state_check else 'None'}")
            
            # Get the current tariff values from the base sensors
            base_sensors_available = True
            current_tariff_value = None
            
            if is_night:
                night_state = self._hass.states.get(night_sensor_id)
                _LOGGER.debug(f"Night time - checking {night_sensor_id}: state={night_state.state if night_state else 'None'}, exists={night_state is not None}")
                if night_state and night_state.state not in ['unknown', 'unavailable', None] and night_state.state is not None:
                    try:
                        current_tariff_value = float(night_state.state)
                        self._tariff_type = f"Night ({'Summer' if is_summer else 'Winter'})"
                        _LOGGER.debug(f"Successfully got night tariff: {current_tariff_value}")
                    except (ValueError, TypeError):
                        _LOGGER.warning(f"Invalid night tariff value: {night_state.state}")
                        base_sensors_available = False
                else:
                    _LOGGER.debug(f"Night sensor {night_sensor_id} not available: state={night_state.state if night_state else 'sensor not found'}")
                    base_sensors_available = False
            else:
                day_state = self._hass.states.get(day_sensor_id)
                _LOGGER.debug(f"Day time - checking {day_sensor_id}: state={day_state.state if day_state else 'None'}, exists={day_state is not None}")
                if day_state and day_state.state not in ['unknown', 'unavailable', None] and day_state.state is not None:
                    try:
                        current_tariff_value = float(day_state.state)
                        self._tariff_type = f"Day ({'Summer' if is_summer else 'Winter'})"
                        _LOGGER.debug(f"Successfully got day tariff: {current_tariff_value}")
                    except (ValueError, TypeError):
                        _LOGGER.warning(f"Invalid day tariff value: {day_state.state}")
                        base_sensors_available = False
                else:
                    _LOGGER.debug(f"Day sensor {day_sensor_id} not available: state={day_state.state if day_state else 'sensor not found'}")
                    base_sensors_available = False
            
            # Handle state assignment with fallback logic
            if base_sensors_available and current_tariff_value is not None:
                # Base sensors are available, use current value
                self._state = current_tariff_value
                self._last_valid_state = current_tariff_value
                self._initialization_complete = True
                _LOGGER.debug(f"Current price sensor {self._currency_type} updated with fresh data: {self._state} ({self._tariff_type})")
            elif self._last_valid_state is not None and self._initialization_complete:
                # Base sensors not available, but we have a previous valid state
                # Keep using the last known good value (this handles restart scenarios)
                self._state = self._last_valid_state
                _LOGGER.debug(f"Current price sensor {self._currency_type} using cached value while base sensors refresh: {self._state}")
            else:
                # No base sensors and no cached value - sensor is truly unavailable
                self._state = None
                _LOGGER.debug(f"Current price sensor {self._currency_type} waiting for base sensors to become available")
            
            # Set season attribute
            self._season = "Summer" if is_summer else "Winter"
            
            # Get day and night tariff values for attributes
            day_state = self._hass.states.get(day_sensor_id)
            night_state = self._hass.states.get(night_sensor_id)
            
            # Handle day tariff
            if day_state and day_state.state not in ['unknown', 'unavailable', None] and day_state.state is not None:
                try:
                    self._day_tariff = float(day_state.state)
                    _LOGGER.debug(f"Day tariff for attributes: {self._day_tariff}")
                except (ValueError, TypeError):
                    self._day_tariff = None
                    _LOGGER.debug(f"Failed to convert day tariff to float: {day_state.state}")
            else:
                self._day_tariff = None
                _LOGGER.debug(f"Day tariff not available for attributes: {day_state.state if day_state else 'sensor not found'}")
                
            # Handle night tariff
            if night_state and night_state.state not in ['unknown', 'unavailable', None] and night_state.state is not None:
                try:
                    self._night_tariff = float(night_state.state)
                    _LOGGER.debug(f"Night tariff for attributes: {self._night_tariff}")
                except (ValueError, TypeError):
                    self._night_tariff = None
                    _LOGGER.debug(f"Failed to convert night tariff to float: {night_state.state}")
            else:
                self._night_tariff = None
                _LOGGER.debug(f"Night tariff not available for attributes: {night_state.state if night_state else 'sensor not found'}")
            
            if self._state is not None:
                _LOGGER.debug(f"Current price sensor {self._currency_type} updated: {self._state} ({self._tariff_type})")
            else:
                _LOGGER.debug(f"Current price sensor {self._currency_type} waiting for base sensors to become available")
            
        except Exception as e:
            _LOGGER.error(f"Error updating current price sensor {self._currency_type}: {e}")
            # If we have a cached value, keep using it during errors
            if self._last_valid_state is not None and self._initialization_complete:
                self._state = self._last_valid_state
                _LOGGER.debug(f"Using cached value due to update error: {self._state}")

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"Electrohold {self._label}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self):
        """Return True if entity is available."""
        # If we have a current state (either fresh or cached), we're available
        if self._state is not None:
            return True
            
        # If we don't have a state, check if base sensors are available for initial setup
        if self._currency_type == "bgn":
            day_sensor_id = "sensor.electrohold_tariff_day"
            night_sensor_id = "sensor.electrohold_tariff_night"
        else:  # euro
            day_sensor_id = "sensor.electrohold_tariff_day_euro"
            night_sensor_id = "sensor.electrohold_tariff_night_euro"
            
        day_state = self._hass.states.get(day_sensor_id)
        night_state = self._hass.states.get(night_sensor_id)
        
        # Both base sensors must be available and have valid data for initial availability
        day_available = day_state and day_state.state not in ['unknown', 'unavailable', None]
        night_available = night_state and night_state.state not in ['unknown', 'unavailable', None]
        
        return day_available and night_available

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def device_class(self):
        """Return the class of the device."""
        return "monetary"

    @property
    def icon(self):
        """Return the icon for the sensor."""
        return "mdi:currency-eur"

    @property
    def unique_id(self):
        """Return a unique ID for the sensor."""
        return self._unique_id

    @property
    def scan_interval(self):
        """Return the scan interval for this sensor."""
        return self._scan_interval

    @property
    def extra_state_attributes(self):
        """Return additional state attributes."""
        # Get current time in the configured timezone
        utc_now = dt_util.utcnow()
        local_now = utc_now.astimezone(self._timezone)
        
        # Determine data source status
        data_source = "fresh"  # Default assumption
        if self._state == self._last_valid_state and not self._are_base_sensors_available():
            data_source = "cached"
        elif self._state is None:
            data_source = "unavailable"
        
        attributes = {
            "tariff_type": self._tariff_type,
            "season": self._season,
            "day_tariff": self._day_tariff,
            "night_tariff": self._night_tariff,
            "last_updated": local_now.strftime('%Y-%m-%d %H:%M:%S %Z'),
            "timezone": str(self._timezone),
            "data_source": data_source  # "fresh", "cached", or "unavailable"
        }
        
        # Get the appropriate sensor entity IDs based on currency type
        if self._currency_type == "bgn":
            day_sensor_id = "sensor.electrohold_tariff_day"
            night_sensor_id = "sensor.electrohold_tariff_night"
        else:  # euro
            day_sensor_id = "sensor.electrohold_tariff_day_euro"
            night_sensor_id = "sensor.electrohold_tariff_night_euro"
        
        # Add last updated timestamps for base sensors
        try:
            day_state = self._hass.states.get(day_sensor_id)
            night_state = self._hass.states.get(night_sensor_id)
            
            if day_state and hasattr(day_state, 'last_updated') and day_state.state not in ['unknown', 'unavailable', None] and day_state.state is not None:
                # Convert UTC timestamp to local timezone
                day_local_time = day_state.last_updated.astimezone(self._timezone)
                attributes["day_tariff_last_updated"] = day_local_time.strftime('%Y-%m-%d %H:%M:%S %Z')
            else:
                attributes["day_tariff_last_updated"] = "Not available yet"
                
            if night_state and hasattr(night_state, 'last_updated') and night_state.state not in ['unknown', 'unavailable', None] and night_state.state is not None:
                # Convert UTC timestamp to local timezone
                night_local_time = night_state.last_updated.astimezone(self._timezone)
                attributes["night_tariff_last_updated"] = night_local_time.strftime('%Y-%m-%d %H:%M:%S %Z')
            else:
                attributes["night_tariff_last_updated"] = "Not available yet"
            
            # Add current tariff last updated (whichever is currently active)
            utc_now_for_calc = dt_util.utcnow()
            local_now_for_calc = utc_now_for_calc.astimezone(self._timezone)
            hour = local_now_for_calc.hour
            month = local_now_for_calc.month
            is_summer = 4 <= month <= 10
            is_night = (hour >= 23 or hour < 7) if is_summer else (hour >= 22 or hour < 6)
            
            current_state = night_state if is_night else day_state
            if current_state and hasattr(current_state, 'last_updated') and current_state.state not in ['unknown', 'unavailable', None] and current_state.state is not None:
                current_local_time = current_state.last_updated.astimezone(self._timezone)
                attributes["current_tariff_last_updated"] = current_local_time.strftime('%Y-%m-%d %H:%M:%S %Z')
            else:
                attributes["current_tariff_last_updated"] = "Not available yet"
                
        except Exception as e:
            _LOGGER.warning(f"Error getting timestamps for current price sensor {self._currency_type}: {e}")
            # Set default values if there's an error
            attributes["day_tariff_last_updated"] = "Error getting timestamp"
            attributes["night_tariff_last_updated"] = "Error getting timestamp"
            attributes["current_tariff_last_updated"] = "Error getting timestamp"
        
        return attributes

    def _are_base_sensors_available(self):
        """Check if base sensors are currently available."""
        if self._currency_type == "bgn":
            day_sensor_id = "sensor.electrohold_tariff_day"
            night_sensor_id = "sensor.electrohold_tariff_night"
        else:  # euro
            day_sensor_id = "sensor.electrohold_tariff_day_euro"
            night_sensor_id = "sensor.electrohold_tariff_night_euro"
            
        day_state = self._hass.states.get(day_sensor_id)
        night_state = self._hass.states.get(night_sensor_id)
        
        day_available = day_state and day_state.state not in ['unknown', 'unavailable', None] and day_state.state is not None
        night_available = night_state and night_state.state not in ['unknown', 'unavailable', None] and night_state.state is not None
        
        return day_available and night_available
