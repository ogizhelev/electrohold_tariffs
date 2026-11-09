"""Sensor platform for the Electrohold Tariffs integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CURRENCY_EURO
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_BASE_PRICE,
    ATTR_SOURCE_URL,
    ATTR_VAT_RATE,
    DOMAIN,
    ELECTROHOLD_URL,
    MANUFACTURER,
    PRICE_PRECISION,
    SENSOR_KEY_DAY,
    SENSOR_KEY_NIGHT,
    VAT_MULTIPLIER,
    VAT_RATE,
)
from .coordinator import ElectroholdConfigEntry, ElectroholdDataUpdateCoordinator
from .models import ElectroholdTariffs


def _with_vat(base_price: float) -> float:
    """Apply VAT to a base price and round to the configured precision."""
    return round(base_price * VAT_MULTIPLIER, PRICE_PRECISION)


@dataclass(frozen=True, kw_only=True)
class ElectroholdSensorEntityDescription(SensorEntityDescription):
    """Describes an Electrohold tariff sensor.

    ``base_fn`` selects the relevant base price from the shared data object;
    the entity itself handles the (identical) VAT math and rounding.
    """

    base_fn: Callable[[ElectroholdTariffs], float]


SENSOR_DESCRIPTIONS: tuple[ElectroholdSensorEntityDescription, ...] = (
    ElectroholdSensorEntityDescription(
        key=SENSOR_KEY_DAY,
        translation_key=SENSOR_KEY_DAY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=f"{CURRENCY_EURO}/kWh",
        suggested_display_precision=5,
        base_fn=lambda tariffs: tariffs.day_base,
    ),
    ElectroholdSensorEntityDescription(
        key=SENSOR_KEY_NIGHT,
        translation_key=SENSOR_KEY_NIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=f"{CURRENCY_EURO}/kWh",
        suggested_display_precision=5,
        base_fn=lambda tariffs: tariffs.night_base,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElectroholdConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Electrohold tariff sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        ElectroholdTariffSensor(coordinator, entry.entry_id, description)
        for description in SENSOR_DESCRIPTIONS
    )


class ElectroholdTariffSensor(
    CoordinatorEntity[ElectroholdDataUpdateCoordinator], SensorEntity
):
    """A single tariff value (day or night) backed by the shared coordinator."""

    entity_description: ElectroholdSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ElectroholdDataUpdateCoordinator,
        entry_id: str,
        description: ElectroholdSensorEntityDescription,
    ) -> None:
        """Initialize the sensor from its description."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Electrohold Tariffs",
            manufacturer=MANUFACTURER,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=ELECTROHOLD_URL,
        )

    @property
    def _base_price(self) -> float | None:
        """Return the base (pre-VAT) price for this sensor, if available."""
        data = self.coordinator.data
        if data is None:
            return None
        return self.entity_description.base_fn(data)

    @property
    def native_value(self) -> float | None:
        """Return the final consumer price (VAT included)."""
        base_price = self._base_price
        if base_price is None:
            return None
        return _with_vat(base_price)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the pre-VAT price and provenance for transparency."""
        attributes: dict[str, Any] = {
            ATTR_VAT_RATE: f"{round(VAT_RATE * 100)}%",
            ATTR_SOURCE_URL: ELECTROHOLD_URL,
        }
        base_price = self._base_price
        if base_price is not None:
            attributes[ATTR_BASE_PRICE] = base_price
        return attributes
