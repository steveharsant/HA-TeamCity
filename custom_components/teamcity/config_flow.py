"""Config flow for TeamCity."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
import voluptuous as vol

from .api import (
    ServerInfo,
    TeamCityAuthenticationError,
    TeamCityClient,
    TeamCityConnectionError,
)
from .const import CONF_ALLOW_NON_ADMIN_LOGS, CONF_BUILD_TYPES, DOMAIN
from .coordinator import TeamCityConfigEntry

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL)
        ),
        vol.Required(CONF_TOKEN): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        vol.Required(CONF_VERIFY_SSL, default=True): bool,
    }
)
REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TOKEN): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


async def _validate(
    hass: HomeAssistant, url: str, token: str, verify_ssl: bool
) -> tuple[ServerInfo | None, dict[str, str]]:
    client = TeamCityClient(
        async_get_clientsession(hass, verify_ssl=verify_ssl), url, token
    )
    try:
        return await client.get_server_info(), {}
    except TeamCityAuthenticationError:
        return None, {"base": "invalid_auth"}
    except TeamCityConnectionError as err:
        _LOGGER.debug("Could not connect to TeamCity at %s: %s", url, err)
        return None, {"base": "cannot_connect"}


class TeamCityConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TeamCity."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: TeamCityConfigEntry) -> OptionsFlow:
        return TeamCityOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            await self.async_set_unique_id(url.lower())
            self._abort_if_unique_id_configured()
            server, errors = await _validate(
                self.hass, url, user_input[CONF_TOKEN], user_input[CONF_VERIFY_SSL]
            )
            if server is not None:
                return self.async_create_entry(
                    title=f"TeamCity ({url.split('://', 1)[-1]})",
                    data={**user_input, CONF_URL: url},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            server, errors = await _validate(
                self.hass,
                entry.data[CONF_URL],
                user_input[CONF_TOKEN],
                entry.data[CONF_VERIFY_SSL],
            )
            if server is not None:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_TOKEN: user_input[CONF_TOKEN]}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            errors=errors,
            description_placeholders={"url": entry.data[CONF_URL]},
        )


class TeamCityOptionsFlow(OptionsFlow):
    """Choose which build configurations become entities, and who can read logs."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        entry: TeamCityConfigEntry = self.config_entry
        try:
            build_types = await entry.runtime_data.client.get_build_types()
        except TeamCityAuthenticationError:
            return self.async_abort(reason="invalid_auth")
        except TeamCityConnectionError:
            return self.async_abort(reason="cannot_connect")

        options = [
            SelectOptionDict(
                value=build_type.id,
                label=f"{build_type.project_name} / {build_type.name}",
            )
            for build_type in sorted(
                build_types, key=lambda b: (b.project_name, b.name)
            )
        ]
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_BUILD_TYPES,
                    default=entry.options.get(CONF_BUILD_TYPES, []),
                ): SelectSelector(SelectSelectorConfig(options=options, multiple=True)),
                vol.Optional(
                    CONF_ALLOW_NON_ADMIN_LOGS,
                    default=entry.options.get(CONF_ALLOW_NON_ADMIN_LOGS, False),
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
