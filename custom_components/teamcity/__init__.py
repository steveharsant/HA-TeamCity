"""The TeamCity integration."""

from __future__ import annotations

from homeassistant.const import CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TeamCityAuthenticationError, TeamCityClient, TeamCityError
from .const import DOMAIN
from .coordinator import TeamCityConfigEntry, TeamCityCoordinator
from .entity import server_device_info

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR]


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
