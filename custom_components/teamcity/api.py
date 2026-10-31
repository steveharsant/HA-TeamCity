"""Minimal async client for the TeamCity REST API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import aiohttp

BUILD_TYPE_FIELDS = (
    "buildType(id,name,projectId,projectName,webUrl,paused,"
    "builds($locator(count:1),"
    "build(id,number,status,statusText,branchName,startDate,finishDate,webUrl)))"
)
RUNNING_BUILD_FIELDS = (
    "build(id,buildTypeId,number,branchName,percentageComplete,webUrl)"
)
QUEUED_BUILD_FIELDS = "count,build(id,buildTypeId)"


class TeamCityError(Exception):
    """Base error for TeamCity API failures."""


class TeamCityConnectionError(TeamCityError):
    """The server could not be reached or returned an unexpected response."""


class TeamCityAuthenticationError(TeamCityError):
    """The access token was rejected."""


@dataclass(frozen=True, slots=True)
class Build:
    """A single TeamCity build."""

    id: int
    number: str | None
    status: str | None
    status_text: str | None
    branch_name: str | None
    start_date: datetime | None
    finish_date: datetime | None
    web_url: str | None
    percentage_complete: int | None = None


@dataclass(frozen=True, slots=True)
class BuildType:
    """A TeamCity build configuration and its most recent finished build."""

    id: str
    name: str
    project_id: str
    project_name: str
    web_url: str | None
    paused: bool
    last_build: Build | None


@dataclass(frozen=True, slots=True)
class ServerInfo:
    """Identity of a TeamCity server."""

    version: str
    web_url: str


def parse_teamcity_datetime(value: str | None) -> datetime | None:
    """Parse TeamCity's compact timestamp format, e.g. 20261031T053400+1100."""
    if not value:
        return None
    return datetime.strptime(value, "%Y%m%dT%H%M%S%z")


def _parse_build(data: dict[str, Any]) -> Build:
    return Build(
        id=int(data["id"]),
        number=data.get("number"),
        status=data.get("status"),
        status_text=data.get("statusText"),
        branch_name=data.get("branchName"),
        start_date=parse_teamcity_datetime(data.get("startDate")),
        finish_date=parse_teamcity_datetime(data.get("finishDate")),
        web_url=data.get("webUrl"),
        percentage_complete=data.get("percentageComplete"),
    )


def _parse_build_type(data: dict[str, Any]) -> BuildType:
    builds = data.get("builds", {}).get("build", [])
    return BuildType(
        id=data["id"],
        name=data["name"],
        project_id=data["projectId"],
        project_name=data["projectName"],
        web_url=data.get("webUrl"),
        paused=bool(data.get("paused", False)),
        last_build=_parse_build(builds[0]) if builds else None,
    )


class TeamCityClient:
    """Talks to a TeamCity server using an access token."""

    def __init__(self, session: aiohttp.ClientSession, url: str, token: str) -> None:
        self._session = session
        self._base_url = url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            async with self._session.request(
                method,
                f"{self._base_url}/app/rest/{path}",
                headers=self._headers,
                params=params,
                json=json,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status in (401, 403):
                    raise TeamCityAuthenticationError(
                        f"TeamCity rejected the access token (HTTP {response.status})"
                    )
                if response.status >= 400:
                    body = await response.text()
                    raise TeamCityConnectionError(
                        f"TeamCity returned HTTP {response.status} for {path}: {body[:200]}"
                    )
                result: dict[str, Any] = await response.json(content_type=None)
                return result
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise TeamCityConnectionError(
                f"Error communicating with TeamCity: {err}"
            ) from err

    async def get_server_info(self) -> ServerInfo:
        """Return the server version; also validates the URL and token."""
        data = await self._request("GET", "server", params={"fields": "version,webUrl"})
        return ServerInfo(
            version=data["version"], web_url=data.get("webUrl", self._base_url)
        )

    async def get_build_types(self) -> list[BuildType]:
        """Return every build configuration with its last finished default-branch build."""
        data = await self._request(
            "GET", "buildTypes", params={"fields": BUILD_TYPE_FIELDS}
        )
        return [_parse_build_type(item) for item in data.get("buildType", [])]

    async def get_running_builds(self) -> list[tuple[str, Build]]:
        """Return (build type id, build) for every running build on any branch."""
        data = await self._request(
            "GET",
            "builds",
            params={
                "locator": "running:true,defaultFilter:false,personal:false",
                "fields": RUNNING_BUILD_FIELDS,
            },
        )
        return [
            (item["buildTypeId"], _parse_build(item)) for item in data.get("build", [])
        ]

    async def get_queued_build_type_ids(self) -> list[str]:
        """Return the build type id of every build waiting in the queue."""
        data = await self._request(
            "GET", "buildQueue", params={"fields": QUEUED_BUILD_FIELDS}
        )
        return [item["buildTypeId"] for item in data.get("build", [])]

    async def trigger_build(self, build_type_id: str) -> None:
        """Queue a new build of the given build configuration."""
        await self._request(
            "POST", "buildQueue", json={"buildType": {"id": build_type_id}}
        )
