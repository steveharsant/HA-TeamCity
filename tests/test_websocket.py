"""Tests for the card's websocket commands."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, MockUser
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.teamcity.api import (
    Agent,
    AgentBuild,
    Build,
    Change,
    TeamCityConnectionError,
)


@pytest.fixture
async def loaded_entry(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> MockConfigEntry:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


async def test_servers_lists_build_types_with_entities(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    loaded_entry: MockConfigEntry,
) -> None:
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "teamcity/servers"})
    response = await client.receive_json()

    assert response["success"]
    [server] = response["result"]["servers"]
    assert server["entry_id"] == loaded_entry.entry_id
    assert server["can_view_logs"] is True
    assert [b["id"] for b in server["build_types"]] == [
        "App_Build",
        "App_Deploy",
        "Lib_Build",
    ]
    app_build = server["build_types"][0]
    assert app_build["device_id"]
    assert app_build["entities"] == {
        "last_build_status": "sensor.app_build_last_build_status",
        "last_build_finished": "sensor.app_build_last_build_finished",
        "state": "binary_sensor.app_build_state",
        "status": "binary_sensor.app_build_status",
        "trigger_build": "button.app_build_trigger_build",
        "paused": "switch.app_build_paused",
    }


async def test_build_history(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_client: AsyncMock,
    loaded_entry: MockConfigEntry,
) -> None:
    mock_client.get_build_history.return_value = [
        Build(
            id=101,
            number="42",
            status="SUCCESS",
            status_text="Tests passed",
            branch_name="main",
            start_date=datetime(2026, 10, 30, 9, 0, tzinfo=UTC),
            finish_date=datetime(2026, 10, 30, 9, 5, tzinfo=UTC),
            web_url="https://teamcity.example.com/build/101",
            state="finished",
            triggered_by="Steve",
        )
    ]
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "teamcity/build_history",
            "entry_id": loaded_entry.entry_id,
            "build_type_id": "App_Build",
            "count": 5,
        }
    )
    response = await client.receive_json()

    assert response["success"]
    [build] = response["result"]["builds"]
    assert build["number"] == "42"
    assert build["triggered_by"] == "Steve"
    assert build["finish_date"] == "2026-10-30T09:05:00+00:00"
    mock_client.get_build_history.assert_awaited_once_with("App_Build", 5)


async def test_build_changes(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_client: AsyncMock,
    loaded_entry: MockConfigEntry,
) -> None:
    mock_client.get_build_changes.return_value = [
        Change(
            id=1,
            version="abc123",
            username="steve",
            date=None,
            comment="Fix tests",
            web_url=None,
        )
    ]
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "teamcity/build_changes",
            "entry_id": loaded_entry.entry_id,
            "build_id": 101,
        }
    )
    response = await client.receive_json()

    assert response["result"]["changes"][0]["comment"] == "Fix tests"


async def test_agents(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_client: AsyncMock,
    loaded_entry: MockConfigEntry,
) -> None:
    mock_client.get_agents.return_value = [
        Agent(
            id=1,
            name="agent-1",
            connected=True,
            enabled=True,
            authorized=True,
            running_build=AgentBuild(
                id=103, build_type_id="App_Build", number="43", web_url=None
            ),
        )
    ]
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "teamcity/agents", "entry_id": loaded_entry.entry_id}
    )
    response = await client.receive_json()

    assert response["result"]["agents"][0]["running_build"]["id"] == 103


async def test_build_log_for_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_client: AsyncMock,
    loaded_entry: MockConfigEntry,
) -> None:
    mock_client.get_build_log_tail.return_value = ["step 1", "step 2"]
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "teamcity/build_log",
            "entry_id": loaded_entry.entry_id,
            "build_id": 101,
        }
    )
    response = await client.receive_json()

    assert response["result"]["lines"] == ["step 1", "step 2"]
    mock_client.get_build_log_tail.assert_awaited_once_with(101, 100)


@pytest.mark.parametrize(
    ("allow_non_admin_logs", "expected_success"), [(False, False), (True, True)]
)
async def test_build_log_for_non_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_admin_user: MockUser,
    mock_client: AsyncMock,
    config_entry: MockConfigEntry,
    allow_non_admin_logs: bool,
    expected_success: bool,
) -> None:
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry, options={"allow_non_admin_logs": allow_non_admin_logs}
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    hass_admin_user.groups = []
    mock_client.get_build_log_tail.return_value = ["secret"]

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "teamcity/servers"})
    servers = await client.receive_json()
    assert servers["result"]["servers"][0]["can_view_logs"] is expected_success

    await client.send_json_auto_id(
        {
            "type": "teamcity/build_log",
            "entry_id": config_entry.entry_id,
            "build_id": 101,
        }
    )
    response = await client.receive_json()

    assert response["success"] is expected_success
    if not expected_success:
        assert response["error"]["code"] == "unauthorized"
        mock_client.get_build_log_tail.assert_not_awaited()


async def test_unknown_entry(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    loaded_entry: MockConfigEntry,
) -> None:
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "teamcity/agents", "entry_id": "nope"})
    response = await client.receive_json()

    assert response["error"]["code"] == "not_found"


async def test_teamcity_error_is_reported(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_client: AsyncMock,
    loaded_entry: MockConfigEntry,
) -> None:
    mock_client.get_agents.side_effect = TeamCityConnectionError("down")
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "teamcity/agents", "entry_id": loaded_entry.entry_id}
    )
    response = await client.receive_json()

    assert response["error"] == {"code": "home_assistant_error", "message": "down"}


async def test_history_count_is_bounded(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    loaded_entry: MockConfigEntry,
) -> None:
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "teamcity/build_history",
            "entry_id": loaded_entry.entry_id,
            "build_type_id": "App_Build",
            "count": 1000,
        }
    )
    response = await client.receive_json()

    assert response["error"]["code"] == "invalid_format"
