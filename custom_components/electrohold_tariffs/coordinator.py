"""Data update coordinator for the Electrohold Tariffs integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ElectroholdApiClient, ElectroholdApiError
from .const import DOMAIN, SCAN_INTERVAL
from .models import ElectroholdTariffs

_LOGGER = logging.getLogger(__name__)

# Config entry whose ``runtime_data`` holds the coordinator for this entry.
type ElectroholdConfigEntry = ConfigEntry["ElectroholdDataUpdateCoordinator"]


class ElectroholdDataUpdateCoordinator(DataUpdateCoordinator[ElectroholdTariffs]):
    """Fetch tariffs once per interval and share them with every sensor.

    Using a single coordinator means the provider's page is downloaded one
    time per update cycle regardless of how many sensors are configured,
    instead of once per sensor.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ElectroholdConfigEntry,
        client: ElectroholdApiClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self._client = client

    async def _async_update_data(self) -> ElectroholdTariffs:
        """Fetch the latest tariffs."""
        try:
            return await self._client.async_fetch_tariffs()
        except ElectroholdApiError as exc:
            raise UpdateFailed(str(exc)) from exc
