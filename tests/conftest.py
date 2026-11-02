"""Shared fixtures for TeamCity tests."""

from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL, UrlManager
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teamcity.api import Build, BuildType, QueuedBuild, ServerInfo
from custom_components.teamcity.const import DOMAIN

URL = "https://teamcity.example.com"
CONFIG = {"url": URL, "token": "secret", "verify_ssl": True}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Allow loading custom_components in every test."""


@pytest.fixture(autouse=True)
def mock_frontend(hass: HomeAssistant) -> UrlManager:
    """Stand in for the frontend component, whose assets aren't installed in tests."""
    hass.config.components.add("frontend")
    extra_modules = UrlManager(lambda *_: None, [])
    hass.data[DATA_EXTRA_MODULE_URL] = extra_modules
    return extra_modules


@pytest.fixture(autouse=True)
def built_card(tmp_path: Path) -> Generator[Path]:
    """Point the integration at a built card file."""
    card = tmp_path / "teamcity-card.js"
    card.write_text("customElements.define('teamcity-card', class {});")
    with patch("custom_components.teamcity.CARD_PATH", card):
        yield card


def make_build_types() -> list[BuildType]:
    return [
        BuildType(
            id="App_Build",
            name="Build",
            project_id="App",
            project_name="App",
            web_url=f"{URL}/buildConfiguration/App_Build",
            paused=False,
            last_build=Build(
                id=101,
                number="42",
                status="SUCCESS",
                status_text="Tests passed: 10",
                branch_name="main",
                start_date=datetime(2026, 10, 30, 9, 0, tzinfo=UTC),
                finish_date=datetime(2026, 10, 30, 9, 5, tzinfo=UTC),
                web_url=f"{URL}/build/101",
            ),
        ),
        BuildType(
            id="App_Deploy",
            name="Deploy",
            project_id="App",
            project_name="App",
            web_url=f"{URL}/buildConfiguration/App_Deploy",
            paused=False,
            last_build=Build(
                id=102,
                number="7",
                status="FAILURE",
                status_text="Exit code 1",
                branch_name="main",
                start_date=datetime(2026, 10, 30, 10, 0, tzinfo=UTC),
                finish_date=datetime(2026, 10, 30, 10, 1, tzinfo=UTC),
                web_url=f"{URL}/build/102",
            ),
        ),
        BuildType(
            id="Lib_Build",
            name="Build",
            project_id="Lib",
            project_name="Lib",
            web_url=None,
            paused=False,
            last_build=None,
        ),
    ]


@pytest.fixture
def mock_client() -> Generator[AsyncMock]:
    """Patch the TeamCity client everywhere it is constructed."""
    with (
        patch("custom_components.teamcity.TeamCityClient", autospec=True) as client_cls,
        patch("custom_components.teamcity.config_flow.TeamCityClient", new=client_cls),
    ):
        client = client_cls.return_value
        client.get_server_info.return_value = ServerInfo(
            version="2025.07 (build 197242)", web_url=URL
        )
        client.get_build_types.return_value = make_build_types()
        client.get_running_builds.return_value = [
            (
                "App_Build",
                Build(
                    id=103,
                    number="43",
                    status="SUCCESS",
                    status_text=None,
                    branch_name="feature/x",
                    start_date=None,
                    finish_date=None,
                    web_url=f"{URL}/build/103",
                    percentage_complete=40,
                ),
            )
        ]
        client.get_queued_builds.return_value = [
            QueuedBuild(id=201, build_type_id="App_Build"),
            QueuedBuild(id=202, build_type_id="App_Deploy"),
        ]
        yield client


@pytest.fixture
def config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="TeamCity (teamcity.example.com)",
        unique_id=URL,
        data=CONFIG,
    )
