"""Tests for the TeamCity actions."""

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teamcity.api import (
    TeamCityBuildNotActiveError,
    TeamCityConnectionError,
)
from custom_components.teamcity.const import DOMAIN


@pytest.fixture
async def loaded_entry(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> MockConfigEntry:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


def _build_type_device_id(
    hass: HomeAssistant, entry: MockConfigEntry, build_type_id: str
) -> str:
    device = dr.async_get(hass).async_get_device(
        identifiers={(DOMAIN, f"{entry.entry_id}_{build_type_id}")}
    )
    assert device is not None
    return device.id


async def test_trigger_build(
    hass: HomeAssistant, mock_client: AsyncMock, loaded_entry: MockConfigEntry
) -> None:
    await hass.services.async_call(
        DOMAIN,
        "trigger_build",
        {"device_id": _build_type_device_id(hass, loaded_entry, "App_Deploy")},
        blocking=True,
    )
    mock_client.trigger_build.assert_awaited_once_with("App_Deploy")


async def test_set_paused(
    hass: HomeAssistant, mock_client: AsyncMock, loaded_entry: MockConfigEntry
) -> None:
    await hass.services.async_call(
        DOMAIN,
        "set_paused",
        {
            "device_id": _build_type_device_id(hass, loaded_entry, "App_Build"),
            "paused": True,
        },
        blocking=True,
    )
    mock_client.set_paused.assert_awaited_once_with("App_Build", True)


async def test_cancel_build_with_default_comment(
    hass: HomeAssistant, mock_client: AsyncMock, loaded_entry: MockConfigEntry
) -> None:
    await hass.services.async_call(
        DOMAIN,
        "cancel_build",
        {"config_entry_id": loaded_entry.entry_id, "build_id": 103},
        blocking=True,
    )
    mock_client.cancel_build.assert_awaited_once_with(
        103, "Cancelled from Home Assistant"
    )


async def test_cancel_finished_build_is_a_validation_error(
    hass: HomeAssistant, mock_client: AsyncMock, loaded_entry: MockConfigEntry
) -> None:
    mock_client.cancel_build.side_effect = TeamCityBuildNotActiveError("finished")
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "cancel_build",
            {"config_entry_id": loaded_entry.entry_id, "build_id": 101},
            blocking=True,
        )
    assert err.value.translation_key == "build_not_active"


async def test_api_failure_is_raised(
    hass: HomeAssistant, mock_client: AsyncMock, loaded_entry: MockConfigEntry
) -> None:
    mock_client.trigger_build.side_effect = TeamCityConnectionError("HTTP 403")
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN,
            "trigger_build",
            {"device_id": _build_type_device_id(hass, loaded_entry, "App_Build")},
            blocking=True,
        )
    assert err.value.translation_key == "action_failed"


async def test_server_device_is_not_a_build_configuration(
    hass: HomeAssistant, mock_client: AsyncMock, loaded_entry: MockConfigEntry
) -> None:
    server = dr.async_get(hass).async_get_device(
        identifiers={(DOMAIN, loaded_entry.entry_id)}
    )
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN, "trigger_build", {"device_id": server.id}, blocking=True
        )
    assert err.value.translation_key == "not_a_build_configuration"


async def test_unknown_entry(
    hass: HomeAssistant, mock_client: AsyncMock, loaded_entry: MockConfigEntry
) -> None:
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "cancel_build",
            {"config_entry_id": "nope", "build_id": 1},
            blocking=True,
        )
    assert err.value.translation_key == "entry_not_found"


async def test_unloaded_entry(
    hass: HomeAssistant, mock_client: AsyncMock, loaded_entry: MockConfigEntry
) -> None:
    device_id = _build_type_device_id(hass, loaded_entry, "App_Build")
    await hass.config_entries.async_unload(loaded_entry.entry_id)
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN, "trigger_build", {"device_id": device_id}, blocking=True
        )
    assert err.value.translation_key == "entry_not_loaded"
