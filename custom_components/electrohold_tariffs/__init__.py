"""The Electrohold Tariffs integration."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "electrohold_tariffs"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Electrohold Tariffs component."""
    _LOGGER.info("Setting up Electrohold Tariffs integration")
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the Electrohold Tariffs integration."""
    _LOGGER.info("Reloading Electrohold Tariffs integration")
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Electrohold Tariffs from a config entry."""
    _LOGGER.info("Setting up Electrohold Tariffs from config entry")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Electrohold Tariffs config entry")
    return True