"""Actions for TeamCity, shared by the entities and callable from automations."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr
import voluptuous as vol

from .api import TeamCityBuildNotActiveError, TeamCityError
from .const import DOMAIN
from .coordinator import TeamCityConfigEntry, TeamCityCoordinator

ATTR_DEVICE_ID = "device_id"
ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_BUILD_ID = "build_id"
ATTR_COMMENT = "comment"
ATTR_PAUSED = "paused"

DEFAULT_CANCEL_COMMENT = "Cancelled from Home Assistant"

SERVICE_TRIGGER_BUILD = "trigger_build"
SERVICE_CANCEL_BUILD = "cancel_build"
SERVICE_SET_PAUSED = "set_paused"

TRIGGER_BUILD_SCHEMA = vol.Schema({vol.Required(ATTR_DEVICE_ID): cv.string})
SET_PAUSED_SCHEMA = vol.Schema(
    {vol.Required(ATTR_DEVICE_ID): cv.string, vol.Required(ATTR_PAUSED): cv.boolean}
)
CANCEL_BUILD_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_BUILD_ID): cv.positive_int,
        vol.Optional(ATTR_COMMENT, default=DEFAULT_CANCEL_COMMENT): cv.string,
    }
)


def _action_failed(err: TeamCityError) -> HomeAssistantError:
    return HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="action_failed",
        translation_placeholders={"error": str(err)},
    )


async def async_trigger_build(
    coordinator: TeamCityCoordinator, build_type_id: str
) -> None:
    """Queue a build and refresh so the queue shows it."""
    try:
        await coordinator.client.trigger_build(build_type_id)
    except TeamCityError as err:
        raise _action_failed(err) from err
    await coordinator.async_refresh()


async def async_set_paused(
    coordinator: TeamCityCoordinator, build_type_id: str, paused: bool
) -> None:
    """Pause or unpause a build configuration and refresh its state."""
    try:
        await coordinator.client.set_paused(build_type_id, paused)
    except TeamCityError as err:
        raise _action_failed(err) from err
    await coordinator.async_refresh()


async def async_cancel_build(
    coordinator: TeamCityCoordinator, build_id: int, comment: str
) -> None:
    """Cancel a running or queued build and refresh."""
    try:
        await coordinator.client.cancel_build(build_id, comment)
    except TeamCityBuildNotActiveError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="build_not_active",
            translation_placeholders={"build_id": str(build_id)},
        ) from err
    except TeamCityError as err:
        raise _action_failed(err) from err
    await coordinator.async_refresh()


def get_loaded_entry(hass: HomeAssistant, entry_id: str) -> TeamCityConfigEntry:
    """Return a loaded TeamCity config entry or raise a validation error."""
    entry: TeamCityConfigEntry | None = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entry_not_found",
            translation_placeholders={"entry_id": entry_id},
        )
    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entry_not_loaded",
            translation_placeholders={"title": entry.title},
        )
    return entry


def _resolve_build_type_device(
    hass: HomeAssistant, device_id: str
) -> tuple[TeamCityCoordinator, str]:
    device = dr.async_get(hass).async_get(device_id)
    if device is not None:
        for domain, identifier in device.identifiers:
            if domain != DOMAIN:
                continue
            for entry_id in device.config_entries:
                prefix = f"{entry_id}_"
                if identifier.startswith(prefix):
                    entry = get_loaded_entry(hass, entry_id)
                    return entry.runtime_data, identifier.removeprefix(prefix)
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="not_a_build_configuration",
        translation_placeholders={"device_id": device_id},
    )


def async_setup_services(hass: HomeAssistant) -> None:
    """Register the TeamCity actions."""

    async def trigger_build(call: ServiceCall) -> None:
        coordinator, build_type_id = _resolve_build_type_device(
            hass, call.data[ATTR_DEVICE_ID]
        )
        await async_trigger_build(coordinator, build_type_id)

    async def set_paused(call: ServiceCall) -> None:
        coordinator, build_type_id = _resolve_build_type_device(
            hass, call.data[ATTR_DEVICE_ID]
        )
        await async_set_paused(coordinator, build_type_id, call.data[ATTR_PAUSED])

    async def cancel_build(call: ServiceCall) -> None:
        entry = get_loaded_entry(hass, call.data[ATTR_CONFIG_ENTRY_ID])
        await async_cancel_build(
            entry.runtime_data, call.data[ATTR_BUILD_ID], call.data[ATTR_COMMENT]
        )

    hass.services.async_register(
        DOMAIN, SERVICE_TRIGGER_BUILD, trigger_build, schema=TRIGGER_BUILD_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_PAUSED, set_paused, schema=SET_PAUSED_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CANCEL_BUILD, cancel_build, schema=CANCEL_BUILD_SCHEMA
    )
