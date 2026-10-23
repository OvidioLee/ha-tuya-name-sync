"""Config flow for Tuya Name Sync."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback

from .const import (
    CONF_AUTO_SYNC,
    CONF_SYNC_ENTRY_TITLE,
    DEFAULT_AUTO_SYNC,
    DEFAULT_SYNC_ENTRY_TITLE,
    DOMAIN,
)


class TuyaNameSyncConfigFlow(ConfigFlow, domain=DOMAIN):
    """Single-instance setup; there is nothing to configure up front."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(title="Tuya Name Sync", data={})
        return self.async_show_form(step_id="user")

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return TuyaNameSyncOptionsFlow()


class TuyaNameSyncOptionsFlow(OptionsFlow):
    """Toggle automatic syncing and entry-title syncing."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_AUTO_SYNC,
                        default=options.get(CONF_AUTO_SYNC, DEFAULT_AUTO_SYNC),
                    ): bool,
                    vol.Required(
                        CONF_SYNC_ENTRY_TITLE,
                        default=options.get(
                            CONF_SYNC_ENTRY_TITLE, DEFAULT_SYNC_ENTRY_TITLE
                        ),
                    ): bool,
                }
            ),
        )
