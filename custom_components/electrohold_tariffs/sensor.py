"""Electrohold tariff sensor platform for Home Assistant."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Final

import requests
from bs4 import BeautifulSoup
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_EURO
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_validation import string
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_TIMEZONE,
    DEFAULT_TIMEZONE,
    ELECTROHOLD_URL,
    SENSOR_TYPE_DAY,
    SENSOR_TYPE_NIGHT,
    VAT_RATE,
)

_LOGGER: Final = logging.getLogger(__name__)

# Configuration schema for YAML setup (backward compatibility)
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_TIMEZONE, default=DEFAULT_TIMEZONE): string,
})

# Set the scan interval to update daily
SCAN_INTERVAL: Final = timedelta(days=1)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Electrohold Tariff sensors from a config entry."""
    # Create day and night Euro sensors
    sensors = [
        ElectricityTariffSensor(
            sensor_type=SENSOR_TYPE_DAY,
            label="Day Euro",
            unique_id=f"{entry.entry_id}_day_euro",
            unit_of_measurement=f"{CURRENCY_EURO}/kWh",
        ),
        ElectricityTariffSensor(
            sensor_type=SENSOR_TYPE_NIGHT,
            label="Night Euro",
            unique_id=f"{entry.entry_id}_night_euro",
            unit_of_measurement=f"{CURRENCY_EURO}/kWh",
        ),
    ]
    
    async_add_entities(sensors, True)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the electricity tariff sensors from YAML (deprecated)."""
    _LOGGER.warning(
        "Configuration via YAML is deprecated. "
        "Please remove it from configuration.yaml and set up the integration via the UI."
    )
    
    # Create day and night Euro sensors
    day_euro_sensor = ElectricityTariffSensor(
        sensor_type=SENSOR_TYPE_DAY,
        label="Day Euro",
        unique_id="electrohold_tariff_day_euro_yaml",
        unit_of_measurement=f"{CURRENCY_EURO}/kWh",
    )
    night_euro_sensor = ElectricityTariffSensor(
        sensor_type=SENSOR_TYPE_NIGHT,
        label="Night Euro",
        unique_id="electrohold_tariff_night_euro_yaml",
        unit_of_measurement=f"{CURRENCY_EURO}/kWh",
    )

    # Add sensors
    add_entities([day_euro_sensor, night_euro_sensor], True)




class ElectricityTariffSensor(SensorEntity):
    """Representation of a Sensor to expose electricity tariff data."""

    def __init__(
        self,
        sensor_type: str,
        label: str,
        unique_id: str,
        unit_of_measurement: str,
    ) -> None:
        """Initialize the sensor."""
        self._sensor_type = sensor_type
        self._label = label
        self._attr_unique_id = unique_id
        self._attr_state = None
        self._attr_native_unit_of_measurement = unit_of_measurement
        self._attr_should_poll = True
        self._attr_device_class = "monetary"
        self._last_update: datetime | None = None
        self._base_price: float | None = None
        
        _LOGGER.info(
            "Initializing sensor %s, performing initial update",
            self._sensor_type,
        )

    def update(self) -> None:
        """Fetch the current value from the website and update the sensor state."""
        _LOGGER.info("Starting update for sensor %s", self._sensor_type)
        
        try:
            _LOGGER.info("Fetching data from: %s", ELECTROHOLD_URL)
            response = requests.get(ELECTROHOLD_URL, timeout=10)
            response.raise_for_status()
            _LOGGER.info(
                "Successfully fetched webpage, status code: %d",
                response.status_code,
            )

            soup = BeautifulSoup(response.text, "html.parser")

            # Parse tariff components from the webpage
            tariff_data = self._parse_tariff_components(soup)
            _LOGGER.info("Parsed tariff components: %s", tariff_data)

            if not tariff_data:
                _LOGGER.error("Failed to parse tariff components - no data found")
                self._attr_state = None
                return

            # Calculate final tariffs based on sensor type
            if self._sensor_type == SENSOR_TYPE_DAY:
                base_day = tariff_data.get("day_base", 0)
                self._base_price = base_day
                self._attr_state = round(base_day * VAT_RATE, 6)
                _LOGGER.info(
                    "Day EUR tariff calculated: %s * %s = %s",
                    base_day,
                    VAT_RATE,
                    self._attr_state,
                )
            elif self._sensor_type == SENSOR_TYPE_NIGHT:
                base_night = tariff_data.get("night_base", 0)
                self._base_price = base_night
                self._attr_state = round(base_night * VAT_RATE, 6)
                _LOGGER.info(
                    "Night EUR tariff calculated: %s * %s = %s",
                    base_night,
                    VAT_RATE,
                    self._attr_state,
                )

            # Update last update timestamp
            self._last_update = datetime.now()

            _LOGGER.info(
                "Update completed successfully for %s, final state: %s",
                self._sensor_type,
                self._attr_state,
            )

        except requests.RequestException as exc:
            _LOGGER.error(
                "Error fetching electricity tariff data for %s: %s",
                self._sensor_type,
                exc,
            )
        except Exception as exc:  # pylint: disable=broad-except
            _LOGGER.error(
                "Unexpected error updating %s: %s",
                self._sensor_type,
                exc,
                exc_info=True,
            )

    def _parse_tariff_components(self, soup: BeautifulSoup) -> dict[str, float]:
        """Parse the tariff components from the webpage dynamically."""
        components: dict[str, float] = {}

        try:
            _LOGGER.info("Starting to parse tariff components from webpage...")
            
            # Find all table rows to extract prices
            tables = soup.find_all("table")
            _LOGGER.info("Found %d tables on the page", len(tables))
            
            # Parse main tariff table (day/night prices)
            for table in tables:
                rows = table.find_all("tr")
                for row in rows:
                    cells = row.find_all(["td", "th"])
                    cell_texts = [cell.get_text(strip=True) for cell in cells]
                    
                    # Look for day tariff row (contains "Дневна")
                    if any("Дневна" in text for text in cell_texts):
                        _LOGGER.info("Found day tariff row: %s", cell_texts)
                        value = self._extract_euro_value(cell_texts, min_value=0.1)
                        if value:
                            components["day_base"] = value
                            _LOGGER.info(
                                "✓ Found Day Base Tariff (with all fees, before VAT): %s €/kWh",
                                value,
                            )
                    
                    # Look for night tariff row (contains "Нощна")
                    elif any("Нощна" in text for text in cell_texts):
                        _LOGGER.info("Found night tariff row: %s", cell_texts)
                        value = self._extract_euro_value(
                            cell_texts, min_value=0.05, max_value=0.1
                        )
                        if value:
                            components["night_base"] = value
                            _LOGGER.info(
                                "✓ Found Night Base Tariff (with all fees, before VAT): %s €/kWh",
                                value,
                            )
            
            # Verify required components were found
            expected_keys = ["day_base", "night_base"]
            missing_keys = [
                key for key in expected_keys
                if key not in components or components[key] == 0
            ]
            
            if missing_keys:
                _LOGGER.warning("Could not find some components: %s", missing_keys)
                # Set missing components to 0
                for key in missing_keys:
                    if key not in components:
                        components[key] = 0
            
            found_count = len([v for v in components.values() if v > 0])
            _LOGGER.info(
                "Tariff parsing complete. Components found: %d/%d",
                found_count,
                len(expected_keys),
            )
            _LOGGER.info("All parsed components: %s", components)
            return components

        except Exception as exc:  # pylint: disable=broad-except
            _LOGGER.error(
                "Error parsing tariff components: %s",
                exc,
                exc_info=True,
            )
            return {}

    def _extract_euro_value(
        self,
        cell_texts: list[str],
        min_value: float = 0.0,
        max_value: float | None = None,
    ) -> float | None:
        """Extract Euro value from cell texts with optional range validation."""
        for text in cell_texts:
            # Match pattern like "0,12478 €/кВтч" or "0.12478"
            match = re.search(r"(\d+[,\.]\d+)\s*€", text)
            if match:
                value_str = match.group(1).replace(",", ".")
                value = float(value_str)
                
                # Apply range validation
                if value < min_value:
                    continue
                if max_value is not None and value > max_value:
                    continue
                    
                return value
        return None

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"Electrohold Tariff {self._label}"

    @property
    def state(self) -> float | None:
        """Return the state of the sensor."""
        return self._attr_state
    
    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._attr_state is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attributes = {}
        
        if self._last_update:
            attributes["last_updated"] = self._last_update.isoformat()
        
        if self._base_price is not None:
            attributes["base_price_excl_vat"] = self._base_price
            attributes["vat_rate"] = f"{round((VAT_RATE - 1) * 100)}%"
        
        attributes["source_url"] = ELECTROHOLD_URL


        
        return attributes

