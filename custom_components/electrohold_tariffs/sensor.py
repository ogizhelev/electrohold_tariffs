"""Sensor platform for the Electrohold Tariffs integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, tzinfo
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CURRENCY_EURO
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_ACTIVE_TARIFF,
    ATTR_BASE_PRICE,
    ATTR_DAY_PRICE,
    ATTR_NIGHT_PRICE,
    ATTR_SEASON,
    ATTR_SOURCE_URL,
    ATTR_VAT_RATE,
    DOMAIN,
    ELECTROHOLD_URL,
    MANUFACTURER,
    PRICE_PRECISION,
    SENSOR_KEY_CURRENT,
    SENSOR_KEY_DAY,
    SENSOR_KEY_NIGHT,
    TARIFF_TIMEZONE,
    VAT_MULTIPLIER,
    VAT_RATE,
)
from .coordinator import ElectroholdConfigEntry, ElectroholdDataUpdateCoordinator
from .models import ElectroholdTariffs
from .schedule import TariffZone, active_zone, is_summer_schedule

_UNIT = f"{CURRENCY_EURO}/kWh"
_DISPLAY_PRECISION = 5


def _with_vat(base_price: float) -> float:
    """Apply VAT to a base price and round to the configured precision."""
    return round(base_price * VAT_MULTIPLIER, PRICE_PRECISION)


@dataclass(frozen=True, kw_only=True)
class ElectroholdSensorEntityDescription(SensorEntityDescription):
    """Describes a fixed day/night Electrohold tariff sensor.

    ``base_fn`` selects the relevant base price from the shared data object;
    the entity handles the (identical) VAT math and rounding.
    """

    base_fn: Callable[[ElectroholdTariffs], float]


TARIFF_SENSOR_DESCRIPTIONS: tuple[ElectroholdSensorEntityDescription, ...] = (
    ElectroholdSensorEntityDescription(
        key=SENSOR_KEY_DAY,
        translation_key=SENSOR_KEY_DAY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=_UNIT,
        suggested_display_precision=_DISPLAY_PRECISION,
        base_fn=lambda tariffs: tariffs.day_base,
    ),
    ElectroholdSensorEntityDescription(
        key=SENSOR_KEY_NIGHT,
        translation_key=SENSOR_KEY_NIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=_UNIT,
        suggested_display_precision=_DISPLAY_PRECISION,
        base_fn=lambda tariffs: tariffs.night_base,
    ),
)

CURRENT_PRICE_DESCRIPTION = SensorEntityDescription(
    key=SENSOR_KEY_CURRENT,
    translation_key=SENSOR_KEY_CURRENT,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=_UNIT,
    suggested_display_precision=_DISPLAY_PRECISION,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElectroholdConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Electrohold tariff sensors from a config entry."""
    coordinator = entry.runtime_data
    entities: list[_ElectroholdSensorBase] = [
        ElectroholdTariffSensor(coordinator, entry.entry_id, description)
        for description in TARIFF_SENSOR_DESCRIPTIONS
    ]
    entities.append(
        ElectroholdCurrentPriceSensor(
            coordinator, entry.entry_id, CURRENT_PRICE_DESCRIPTION
        )
    )
    async_add_entities(entities)


class _ElectroholdSensorBase(
    CoordinatorEntity[ElectroholdDataUpdateCoordinator], SensorEntity
):
    """Common wiring for all Electrohold sensors (device, id, unit, VAT)."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ElectroholdDataUpdateCoordinator,
        entry_id: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize shared entity metadata from the description."""
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
    def _tariffs(self) -> ElectroholdTariffs | None:
        """Return the latest tariff data, if available."""
        return self.coordinator.data


class ElectroholdTariffSensor(_ElectroholdSensorBase):
    """A single fixed tariff value (day or night)."""

    entity_description: ElectroholdSensorEntityDescription

    @property
    def _base_price(self) -> float | None:
        """Return the base (pre-VAT) price for this sensor, if available."""
        if (tariffs := self._tariffs) is None:
            return None
        return self.entity_description.base_fn(tariffs)

    @property
    def native_value(self) -> float | None:
        """Return the final consumer price (VAT included)."""
        if (base_price := self._base_price) is None:
            return None
        return _with_vat(base_price)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the pre-VAT price and provenance for transparency."""
        attributes: dict[str, Any] = {
            ATTR_VAT_RATE: f"{round(VAT_RATE * 100)}%",
            ATTR_SOURCE_URL: ELECTROHOLD_URL,
        }
        if (base_price := self._base_price) is not None:
            attributes[ATTR_BASE_PRICE] = base_price
        return attributes


class ElectroholdCurrentPriceSensor(_ElectroholdSensorBase):
    """The price that applies right now, per the regulated day/night schedule.

    The value depends both on the daily tariff data (from the coordinator) and
    on the current time, so the entity re-evaluates on every coordinator update
    *and* at each wall-clock hour boundary (every regulated transition — 06, 07,
    22, 23 — and the seasonal switch all land on whole hours).
    """

    _tz: tzinfo | None = None

    async def async_added_to_hass(self) -> None:
        """Register coordinator and hourly time listeners."""
        await super().async_added_to_hass()
        # Resolve the tariff timezone without blocking the event loop.
        self._tz = await dt_util.async_get_time_zone(TARIFF_TIMEZONE)
        self.async_on_remove(
            async_track_time_change(
                self.hass, self._handle_time_change, minute=0, second=0
            )
        )

    @callback
    def _handle_time_change(self, _now: datetime) -> None:
        """Re-publish the state at an hour boundary (tariff zone may change)."""
        self.async_write_ha_state()

    def _now(self) -> datetime | None:
        """Return the current time in the tariff's local timezone."""
        if self._tz is None:
            return None
        return dt_util.utcnow().astimezone(self._tz)

    @property
    def native_value(self) -> float | None:
        """Return the currently applicable price (VAT included)."""
        tariffs = self._tariffs
        now = self._now()
        if tariffs is None or now is None:
            return None
        base = (
            tariffs.night_base
            if active_zone(now) is TariffZone.NIGHT
            else tariffs.day_base
        )
        return _with_vat(base)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the active zone, season and both rates for transparency."""
        attributes: dict[str, Any] = {ATTR_SOURCE_URL: ELECTROHOLD_URL}
        if (now := self._now()) is not None:
            attributes[ATTR_ACTIVE_TARIFF] = active_zone(now).value
            attributes[ATTR_SEASON] = "summer" if is_summer_schedule(now) else "winter"
        if (tariffs := self._tariffs) is not None:
            attributes[ATTR_DAY_PRICE] = _with_vat(tariffs.day_base)
            attributes[ATTR_NIGHT_PRICE] = _with_vat(tariffs.night_base)
        return attributes
