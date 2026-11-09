"""The Electrohold Tariffs integration."""
from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ElectroholdApiClient
from .coordinator import ElectroholdConfigEntry, ElectroholdDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: ElectroholdConfigEntry
) -> bool:
    """Set up Electrohold Tariffs from a config entry."""
    client = ElectroholdApiClient(async_get_clientsession(hass))
    coordinator = ElectroholdDataUpdateCoordinator(hass, entry, client)

    # Fetch once up front so entities have data as soon as they are added and
    # setup fails loudly (and retries) if the source is unreachable.
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ElectroholdConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(
    hass: HomeAssistant, entry: ElectroholdConfigEntry
) -> None:
    """Reload the config entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
