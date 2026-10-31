"""Tests for setting up TeamCity and its entities."""

from unittest.mock import AsyncMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teamcity.api import (
    BuildType,
    TeamCityAuthenticationError,
    TeamCityConnectionError,
)

from .conftest import make_build_types


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_entity_states(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    await _setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    status = hass.states.get("sensor.app_build_last_build_status")
    assert status.state == "success"
    assert status.attributes["build_number"] == "42"
    assert hass.states.get("sensor.app_deploy_last_build_status").state == "failure"
    assert hass.states.get("sensor.lib_build_last_build_status").state == STATE_UNKNOWN

    assert (
        hass.states.get("sensor.app_build_last_build_finished").state
        == "2026-10-30T09:05:00+00:00"
    )

    assert hass.states.get("binary_sensor.app_deploy_failing").state == STATE_ON
    assert hass.states.get("binary_sensor.app_build_failing").state == STATE_OFF
    assert hass.states.get("binary_sensor.lib_build_failing").state == STATE_UNKNOWN

    running = hass.states.get("binary_sensor.app_build_running")
    assert running.state == STATE_ON
    assert running.attributes["queued"] == 1
    assert running.attributes["builds"][0]["percentage_complete"] == 40
    assert hass.states.get("binary_sensor.app_deploy_running").state == STATE_OFF

    queued = hass.states.get("sensor.teamcity_teamcity_example_com_queued_builds")
    assert queued.state == "2"
    running_total = hass.states.get(
        "sensor.teamcity_teamcity_example_com_running_builds"
    )
    assert running_total.state == "1"


async def test_trigger_build_button(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    await _setup(hass, config_entry)

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.app_deploy_trigger_build"},
        blocking=True,
    )

    mock_client.trigger_build.assert_awaited_once_with("App_Deploy")


async def test_trigger_build_failure_is_raised(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    await _setup(hass, config_entry)
    mock_client.trigger_build.side_effect = TeamCityConnectionError("HTTP 403")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.app_deploy_trigger_build"},
            blocking=True,
        )


async def test_new_build_type_is_added(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    await _setup(hass, config_entry)
    assert hass.states.get("sensor.new_nightly_last_build_status") is None

    mock_client.get_build_types.return_value = [
        *make_build_types(),
        BuildType(
            id="New_Nightly",
            name="Nightly",
            project_id="New",
            project_name="New",
            web_url=None,
            paused=False,
            last_build=None,
        ),
    ]
    await config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("sensor.new_nightly_last_build_status") is not None


async def test_entities_unavailable_when_server_down(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    await _setup(hass, config_entry)

    mock_client.get_build_types.side_effect = TeamCityConnectionError("down")
    await config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.app_build_last_build_status").state == STATE_UNAVAILABLE
    )


async def test_setup_retries_when_unreachable(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    mock_client.get_server_info.side_effect = TeamCityConnectionError("down")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_starts_reauth_on_bad_token(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    mock_client.get_server_info.side_effect = TeamCityAuthenticationError("no")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert [flow["context"]["source"] for flow in flows] == ["reauth"]


async def test_unload(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    await _setup(hass, config_entry)
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED
