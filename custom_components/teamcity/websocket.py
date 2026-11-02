"""Websocket commands the TeamCity card uses for on-demand detail."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import asdict
from functools import wraps
from typing import Any

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
import voluptuous as vol

from .api import TeamCityError
from .const import CONF_ALLOW_NON_ADMIN_LOGS, DOMAIN
from .coordinator import TeamCityConfigEntry

MAX_HISTORY_COUNT = 100
MAX_LOG_LINES = 1000

type Handler = Callable[
    [
        HomeAssistant,
        websocket_api.ActiveConnection,
        dict[str, Any],
        TeamCityConfigEntry,
    ],
    Awaitable[None],
]


def _loaded_entries(hass: HomeAssistant) -> list[TeamCityConfigEntry]:
    return [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
    ]


def can_view_logs(entry: TeamCityConfigEntry, is_admin: bool) -> bool:
    """Whether a user may read build logs from this server."""
    return is_admin or bool(entry.options.get(CONF_ALLOW_NON_ADMIN_LOGS, False))


def _with_entry(handler: Handler) -> websocket_api.AsyncWebSocketCommandHandler:
    """Resolve msg['entry_id'] to a loaded entry and turn TeamCity errors into websocket errors."""

    @wraps(handler)
    async def wrapper(
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        msg: dict[str, Any],
    ) -> None:
        entry = hass.config_entries.async_get_entry(msg["entry_id"])
        if (
            entry is None
            or entry.domain != DOMAIN
            or entry.state is not ConfigEntryState.LOADED
        ):
            connection.send_error(
                msg["id"],
                websocket_api.ERR_NOT_FOUND,
                "TeamCity server not found or not loaded",
            )
            return
        try:
            await handler(hass, connection, msg, entry)
        except TeamCityError as err:
            connection.send_error(
                msg["id"], websocket_api.ERR_HOME_ASSISTANT_ERROR, str(err)
            )

    return wrapper


@websocket_api.websocket_command({vol.Required("type"): "teamcity/servers"})
@callback
def ws_servers(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """List loaded servers with their build configurations and entity ids."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    servers = []
    for entry in _loaded_entries(hass):
        data = entry.runtime_data.data
        build_types = []
        for build_type in data.build_types.values():
            device = device_registry.async_get_device(
                identifiers={(DOMAIN, f"{entry.entry_id}_{build_type.id}")}
            )
            entities = (
                {
                    registry_entry.translation_key: registry_entry.entity_id
                    for registry_entry in er.async_entries_for_device(
                        entity_registry, device.id
                    )
                    if registry_entry.translation_key
                }
                if device
                else {}
            )
            build_types.append(
                {
                    "id": build_type.id,
                    "name": build_type.name,
                    "project_id": build_type.project_id,
                    "project_name": build_type.project_name,
                    "web_url": build_type.web_url,
                    "device_id": device.id if device else None,
                    "entities": entities,
                }
            )
        servers.append(
            {
                "entry_id": entry.entry_id,
                "title": entry.title,
                "can_view_logs": can_view_logs(entry, connection.user.is_admin),
                "build_types": sorted(
                    build_types, key=lambda b: (b["project_name"], b["name"])
                ),
            }
        )
    connection.send_result(msg["id"], {"servers": servers})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "teamcity/build_history",
        vol.Required("entry_id"): str,
        vol.Required("build_type_id"): str,
        vol.Optional("count", default=10): vol.All(
            int, vol.Range(min=1, max=MAX_HISTORY_COUNT)
        ),
    }
)
@websocket_api.async_response
@_with_entry
async def ws_build_history(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    entry: TeamCityConfigEntry,
) -> None:
    """Return recent builds of one build configuration."""
    builds = await entry.runtime_data.client.get_build_history(
        msg["build_type_id"], msg["count"]
    )
    connection.send_result(msg["id"], {"builds": [asdict(build) for build in builds]})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "teamcity/build_changes",
        vol.Required("entry_id"): str,
        vol.Required("build_id"): vol.All(int, vol.Range(min=1)),
    }
)
@websocket_api.async_response
@_with_entry
async def ws_build_changes(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    entry: TeamCityConfigEntry,
) -> None:
    """Return the VCS changes in one build."""
    changes = await entry.runtime_data.client.get_build_changes(msg["build_id"])
    connection.send_result(
        msg["id"], {"changes": [asdict(change) for change in changes]}
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "teamcity/build_log",
        vol.Required("entry_id"): str,
        vol.Required("build_id"): vol.All(int, vol.Range(min=1)),
        vol.Optional("lines", default=100): vol.All(
            int, vol.Range(min=1, max=MAX_LOG_LINES)
        ),
    }
)
@websocket_api.async_response
@_with_entry
async def ws_build_log(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    entry: TeamCityConfigEntry,
) -> None:
    """Return the end of a build log, for admins or when the option allows everyone."""
    if not can_view_logs(entry, connection.user.is_admin):
        connection.send_error(
            msg["id"],
            websocket_api.ERR_UNAUTHORIZED,
            "Only administrators can view TeamCity build logs",
        )
        return
    lines = await entry.runtime_data.client.get_build_log_tail(
        msg["build_id"], msg["lines"]
    )
    connection.send_result(msg["id"], {"lines": lines})


@websocket_api.websocket_command(
    {vol.Required("type"): "teamcity/agents", vol.Required("entry_id"): str}
)
@websocket_api.async_response
@_with_entry
async def ws_agents(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    entry: TeamCityConfigEntry,
) -> None:
    """Return the server's build agents."""
    agents = await entry.runtime_data.client.get_agents()
    connection.send_result(msg["id"], {"agents": [asdict(agent) for agent in agents]})


@callback
def async_register_websocket_commands(hass: HomeAssistant) -> None:
    """Register the card's websocket commands."""
    for command in (
        ws_servers,
        ws_build_history,
        ws_build_changes,
        ws_build_log,
        ws_agents,
    ):
        websocket_api.async_register_command(hass, command)
