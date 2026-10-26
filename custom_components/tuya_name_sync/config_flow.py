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
    CONF_PREFIX,
    CONF_SYNC_ENTITY_NAMES,
    CONF_SYNC_ENTRY_TITLE,
    DEFAULT_AUTO_SYNC,
    DEFAULT_PREFIX,
    DEFAULT_SYNC_ENTITY_NAMES,
    DEFAULT_SYNC_ENTRY_TITLE,
    DOMAIN,
)


def _prefix_schema(prefix: str) -> dict[Any, Any]:
    # suggested_value rather than default, so clearing the field really saves
    # an empty prefix instead of falling back to "TL_".
    return {vol.Optional(CONF_PREFIX, description={"suggested_value": prefix}): str}


def _prefix_from_input(user_input: dict[str, Any]) -> str:
    # The frontend omits an emptied text field entirely.
    return user_input.get(CONF_PREFIX, "")


class TuyaNameSyncConfigFlow(ConfigFlow, domain=DOMAIN):
    """Single-instance setup; only the name prefix is asked up front."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(
                title="Tuya Name Sync",
                data={},
                options={CONF_PREFIX: _prefix_from_input(user_input)},
            )
        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(_prefix_schema(DEFAULT_PREFIX))
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return TuyaNameSyncOptionsFlow()


class TuyaNameSyncOptionsFlow(OptionsFlow):
    """Name prefix, automatic syncing and entry-title syncing."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                data={**user_input, CONF_PREFIX: _prefix_from_input(user_input)}
            )

        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    **_prefix_schema(options.get(CONF_PREFIX, DEFAULT_PREFIX)),
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
                    vol.Required(
                        CONF_SYNC_ENTITY_NAMES,
                        default=options.get(
                            CONF_SYNC_ENTITY_NAMES, DEFAULT_SYNC_ENTITY_NAMES
                        ),
                    ): bool,
                }
            ),
        )
