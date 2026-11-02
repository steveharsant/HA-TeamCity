"""The TeamCity integration."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .api import TeamCityAuthenticationError, TeamCityClient, TeamCityError
from .const import CARD_FILENAME, CARD_URL_PATH, DOMAIN
from .coordinator import TeamCityConfigEntry, TeamCityCoordinator
from .entity import server_device_info
from .services import async_setup_services
from .websocket import async_register_websocket_commands

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SENSOR,
    Platform.SWITCH,
]

CARD_PATH = Path(__file__).parent / "frontend" / CARD_FILENAME


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the actions, websocket commands and dashboard card."""
    async_setup_services(hass)
    async_register_websocket_commands(hass)
    await _async_register_card(hass)
    return True


async def _async_register_card(hass: HomeAssistant) -> None:
    """Serve the bundled card and load it into every dashboard."""
    if not await hass.async_add_executor_job(CARD_PATH.is_file):
        _LOGGER.error(
            "The TeamCity card is missing at %s; install the integration from a "
            "release, or build it with 'npm run build' in frontend/",
            CARD_PATH,
        )
        return
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL_PATH, str(CARD_PATH), cache_headers=True)]
    )
    integration = await async_get_integration(hass, DOMAIN)
    add_extra_js_url(hass, f"{CARD_URL_PATH}?v={integration.version}")


async def async_setup_entry(hass: HomeAssistant, entry: TeamCityConfigEntry) -> bool:
    """Set up TeamCity from a config entry."""
    client = TeamCityClient(
        async_get_clientsession(hass, verify_ssl=entry.data[CONF_VERIFY_SSL]),
        entry.data[CONF_URL],
        entry.data[CONF_TOKEN],
    )
    try:
        server = await client.get_server_info()
    except TeamCityAuthenticationError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except TeamCityError as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = TeamCityCoordinator(hass, entry, client, server.version)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, **server_device_info(entry, server.version)
    )
    _async_remove_stale_devices(hass, entry, coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TeamCityConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(hass: HomeAssistant, entry: TeamCityConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _async_remove_stale_devices(
    hass: HomeAssistant, entry: TeamCityConfigEntry, coordinator: TeamCityCoordinator
) -> None:
    """Drop devices for build configurations that were deleted or deselected."""
    device_registry = dr.async_get(hass)
    current = {entry.entry_id} | {
        f"{entry.entry_id}_{build_type_id}"
        for build_type_id in coordinator.data.build_types
    }
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        if not any(
            domain == DOMAIN and identifier in current
            for domain, identifier in device.identifiers
        ):
            device_registry.async_update_device(
                device.id, remove_config_entry_id=entry.entry_id
            )
