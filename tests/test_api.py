"""Tests for the TeamCity REST client."""

from datetime import UTC, datetime, timedelta, timezone

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.teamcity.api import (
    TeamCityAuthenticationError,
    TeamCityClient,
    TeamCityConnectionError,
    parse_teamcity_datetime,
)

URL = "https://teamcity.example.com"


@pytest.fixture
async def client(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> TeamCityClient:
    return TeamCityClient(async_get_clientsession(hass), f"{URL}/", "secret")


def test_parse_teamcity_datetime() -> None:
    assert parse_teamcity_datetime("20261031T053400+1100") == datetime(
        2026, 10, 31, 5, 34, tzinfo=timezone(timedelta(hours=11))
    )
    assert parse_teamcity_datetime(None) is None
    assert parse_teamcity_datetime("") is None


async def test_get_build_types(
    aioclient_mock: AiohttpClientMocker, client: TeamCityClient
) -> None:
    aioclient_mock.get(
        f"{URL}/app/rest/buildTypes",
        json={
            "buildType": [
                {
                    "id": "App_Build",
                    "name": "Build",
                    "projectId": "App",
                    "projectName": "App",
                    "webUrl": f"{URL}/buildConfiguration/App_Build",
                    "builds": {
                        "build": [
                            {
                                "id": 101,
                                "number": "42",
                                "status": "FAILURE",
                                "statusText": "Tests failed: 1",
                                "branchName": "main",
                                "startDate": "20261030T090000+0000",
                                "finishDate": "20261030T090500+0000",
                                "webUrl": f"{URL}/build/101",
                            }
                        ]
                    },
                },
                {
                    "id": "Lib_Build",
                    "name": "Build",
                    "projectId": "Lib",
                    "projectName": "Lib",
                    "paused": True,
                    "builds": {},
                },
            ]
        },
    )

    build_types = await client.get_build_types()

    assert [b.id for b in build_types] == ["App_Build", "Lib_Build"]
    assert build_types[0].last_build is not None
    assert build_types[0].last_build.status == "FAILURE"
    assert build_types[0].last_build.finish_date == datetime(
        2026, 10, 30, 9, 5, tzinfo=UTC
    )
    assert build_types[1].paused is True
    assert build_types[1].last_build is None
    _, url, _, headers = aioclient_mock.mock_calls[0]
    assert str(url).startswith(f"{URL}/app/rest/buildTypes")
    assert headers["Authorization"] == "Bearer secret"


async def test_running_and_queued(
    aioclient_mock: AiohttpClientMocker, client: TeamCityClient
) -> None:
    aioclient_mock.get(
        f"{URL}/app/rest/builds",
        json={
            "build": [{"id": 5, "buildTypeId": "App_Build", "percentageComplete": 30}]
        },
    )
    aioclient_mock.get(
        f"{URL}/app/rest/buildQueue",
        json={
            "count": 2,
            "build": [{"id": 6, "buildTypeId": "A"}, {"id": 7, "buildTypeId": "A"}],
        },
    )

    running = await client.get_running_builds()
    queued = await client.get_queued_build_type_ids()

    assert running[0][0] == "App_Build"
    assert running[0][1].percentage_complete == 30
    assert queued == ["A", "A"]


async def test_trigger_build_posts_build_type(
    aioclient_mock: AiohttpClientMocker, client: TeamCityClient
) -> None:
    aioclient_mock.post(f"{URL}/app/rest/buildQueue", json={"id": 9})

    await client.trigger_build("App_Build")

    _, _, body, _ = aioclient_mock.mock_calls[0]
    assert body == {"buildType": {"id": "App_Build"}}


@pytest.mark.parametrize("status", [401, 403])
async def test_auth_error(
    aioclient_mock: AiohttpClientMocker, client: TeamCityClient, status: int
) -> None:
    aioclient_mock.get(f"{URL}/app/rest/server", status=status)
    with pytest.raises(TeamCityAuthenticationError):
        await client.get_server_info()


async def test_server_error(
    aioclient_mock: AiohttpClientMocker, client: TeamCityClient
) -> None:
    aioclient_mock.get(f"{URL}/app/rest/server", status=500, text="boom")
    with pytest.raises(TeamCityConnectionError, match="HTTP 500"):
        await client.get_server_info()


async def test_network_error(
    aioclient_mock: AiohttpClientMocker, client: TeamCityClient
) -> None:
    aioclient_mock.get(f"{URL}/app/rest/server", exc=aiohttp.ClientConnectionError())
    with pytest.raises(TeamCityConnectionError):
        await client.get_server_info()
