"""Tests for the TeamCity config and options flows."""

from unittest.mock import AsyncMock

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teamcity.api import (
    TeamCityAuthenticationError,
    TeamCityConnectionError,
)
from custom_components.teamcity.const import DOMAIN

from .conftest import CONFIG, URL


async def test_user_flow_creates_entry(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**CONFIG, "url": f"{URL}/"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "TeamCity (teamcity.example.com)"
    assert result["data"] == CONFIG
    assert result["result"].unique_id == URL


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (TeamCityAuthenticationError("no"), "invalid_auth"),
        (TeamCityConnectionError("down"), "cannot_connect"),
    ],
)
async def test_user_flow_errors_then_recovers(
    hass: HomeAssistant, mock_client: AsyncMock, error: Exception, expected: str
) -> None:
    server_info = mock_client.get_server_info.return_value
    mock_client.get_server_info.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], CONFIG)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}

    mock_client.get_server_info.side_effect = None
    mock_client.get_server_info.return_value = server_info
    result = await hass.config_entries.flow.async_configure(result["flow_id"], CONFIG)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], CONFIG)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_updates_token(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"token": "new-secret"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data["token"] == "new-secret"


async def test_options_flow_selects_build_types(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.lib_build_last_build_status") is not None

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"build_types": ["App_Build"]}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {"build_types": ["App_Build"]}
    assert hass.states.get("sensor.app_build_last_build_status") is not None
    assert hass.states.get("sensor.lib_build_last_build_status") is None
    assert hass.states.get("sensor.app_deploy_last_build_status") is None
