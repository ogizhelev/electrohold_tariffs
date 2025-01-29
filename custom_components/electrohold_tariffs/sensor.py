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

    day_sensor = ElectricityTariffSensor("day_tarrif", "day", "electrohold_day_tariff")
    night_sensor = ElectricityTariffSensor("night_tarrif", "night", "electrohold_night_tariff")

    day_sensor.update()
    night_sensor.update()

    add_entities([day_sensor, night_sensor])

class ElectricityTariffSensor(SensorEntity):
    """Representation of a Sensor to expose electricity tariff data."""

    def __init__(self, sensor_type, label, unique_id):
        """Initialize the sensor."""
        self._sensor_type = sensor_type
        self._label = label
        self._unique_id = unique_id
        self._state = None
        self._unit_of_measurement = "BGN/kWh"

    def update(self):
        """Fetch the current value from the website and update the sensor state."""
        try:
            url = "https://electrohold.bg/bg/sales/domakinstva/snabdyavane-po-regulirani-ceni/"
            response = requests.get(url, timeout=5)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            night = None
            day = None

            value_elements = soup.find_all(string=["Дневна", "Нощна"])

            for element in value_elements:
                if "Дневна" in element.strip():
                    next_element = element.find_parent('td').find_next_sibling('td')
                    if next_element:
                        day_value = next_element.text.strip().replace(',', '.')
                        try:
                            day = float(day_value)
                        except ValueError:
                            _LOGGER.error(f"Error converting day value: {day_value}")

                if "Нощна" in element.strip():
                    next_element = element.find_parent('td').find_next_sibling('td')
                    if next_element:
                        night_value = next_element.text.strip().replace(',', '.')
                        try:
                            night = float(night_value)
                        except ValueError:
                            _LOGGER.error(f"Error converting night value: {night_value}")

            day_tarrif = round((day + 0.06424) * 1.2, 5) if day is not None else None
            night_tarrif = round((night + 0.06424) * 1.2, 5) if night is not None else None

            if self._sensor_type == "day_tarrif":
                self._state = day_tarrif
            elif self._sensor_type == "night_tarrif":
                self._state = night_tarrif

        except Exception as e:
            _LOGGER.error(f"Error fetching electricity tariff data: {e}")
            self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"Electrohold Tariff {self._label}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

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
