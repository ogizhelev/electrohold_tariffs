"""Config flow for the Electrohold Tariffs integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    ElectroholdApiClient,
    ElectroholdConnectionError,
    ElectroholdParseError,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_TITLE = "Electrohold Tariffs"


class ElectroholdConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Electrohold Tariffs."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial (and only) step.

        The integration has no user-facing options, so confirming the form
        simply verifies that the provider's page can be fetched and parsed
        before the entry is created.
        """
        # Only a single instance makes sense: all entries would scrape the
        # same page and expose identical sensors.
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._async_validate_source()
            if not errors:
                return self.async_create_entry(title=_TITLE, data={})

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
            errors=errors,
        )

    async def _async_validate_source(self) -> dict[str, str]:
        """Return a mapping of form errors; empty when the source is valid."""
        client = ElectroholdApiClient(async_get_clientsession(self.hass))
        try:
            await client.async_fetch_tariffs()
        except ElectroholdConnectionError:
            return {"base": "cannot_connect"}
        except ElectroholdParseError:
            return {"base": "invalid_data"}
        except Exception:  # noqa: BLE001 - surface anything unexpected as "unknown"
            _LOGGER.exception("Unexpected error validating Electrohold source")
            return {"base": "unknown"}
        return {}
