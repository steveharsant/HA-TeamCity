"""Minimal async client for the TeamCity REST API."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

import aiohttp

BUILD_FIELDS = (
    "id,number,status,state,statusText,branchName,startDate,finishDate,webUrl,"
    "percentageComplete,buildTypeId,triggered(type,user(username,name))"
)
BUILD_TYPE_FIELDS = (
    "buildType(id,name,projectId,projectName,webUrl,paused,"
    f"builds($locator(count:1),build({BUILD_FIELDS})))"
)
QUEUED_BUILD_FIELDS = "build(id,buildTypeId)"
CHANGE_FIELDS = "change(id,version,username,date,comment,webUrl)"
AGENT_FIELDS = (
    "agent(id,name,connected,enabled,authorized,build(id,buildTypeId,number,webUrl))"
)
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)


class TeamCityError(Exception):
    """Base error for TeamCity API failures."""


class TeamCityConnectionError(TeamCityError):
    """The server could not be reached or returned an unexpected response."""


class TeamCityAuthenticationError(TeamCityError):
    """The access token was rejected."""


class TeamCityBuildNotActiveError(TeamCityError):
    """A cancel was requested for a build that is neither running nor queued."""


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
    state: str | None = None
    triggered_by: str | None = None


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
class QueuedBuild:
    """A build waiting in the queue."""

    id: int
    build_type_id: str


@dataclass(frozen=True, slots=True)
class Change:
    """A VCS change included in a build."""

    id: int
    version: str | None
    username: str | None
    date: datetime | None
    comment: str | None
    web_url: str | None


@dataclass(frozen=True, slots=True)
class AgentBuild:
    """The build an agent is currently running."""

    id: int
    build_type_id: str
    number: str | None
    web_url: str | None


@dataclass(frozen=True, slots=True)
class Agent:
    """A TeamCity build agent."""

    id: int
    name: str
    connected: bool
    enabled: bool
    authorized: bool
    running_build: AgentBuild | None


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


def _describe_trigger(data: dict[str, Any] | None) -> str | None:
    if not data:
        return None
    user = data.get("user")
    if user:
        return user.get("name") or user.get("username")
    return data.get("type")


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
        state=data.get("state"),
        triggered_by=_describe_trigger(data.get("triggered")),
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


def _parse_agent(data: dict[str, Any]) -> Agent:
    build = data.get("build")
    return Agent(
        id=int(data["id"]),
        name=data["name"],
        connected=bool(data.get("connected", False)),
        enabled=bool(data.get("enabled", False)),
        authorized=bool(data.get("authorized", False)),
        running_build=AgentBuild(
            id=int(build["id"]),
            build_type_id=build["buildTypeId"],
            number=build.get("number"),
            web_url=build.get("webUrl"),
        )
        if build
        else None,
    )


class TeamCityClient:
    """Talks to a TeamCity server using an access token."""

    def __init__(self, session: aiohttp.ClientSession, url: str, token: str) -> None:
        self._session = session
        self._base_url = url.rstrip("/")
        self._token = token

    def _headers(self, accept: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}", "Accept": accept}

    @staticmethod
    async def _raise_for_status(response: aiohttp.ClientResponse, path: str) -> None:
        if response.status in (401, 403):
            raise TeamCityAuthenticationError(
                f"TeamCity rejected the access token (HTTP {response.status})"
            )
        if response.status >= 400:
            body = await response.text()
            raise TeamCityConnectionError(
                f"TeamCity returned HTTP {response.status} for {path}: {body[:200]}"
            )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        text: str | None = None,
        accept: Literal["application/json", "text/plain"] = "application/json",
    ) -> Any:
        headers = self._headers(accept)
        if text is not None:
            headers["Content-Type"] = "text/plain"
        try:
            async with self._session.request(
                method,
                f"{self._base_url}/app/rest/{path}",
                headers=headers,
                params=params,
                json=json,
                data=text,
                timeout=REQUEST_TIMEOUT,
            ) as response:
                await self._raise_for_status(response, path)
                if accept == "text/plain":
                    return await response.text()
                return await response.json(content_type=None)
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
                "fields": f"build({BUILD_FIELDS})",
            },
        )
        return [
            (item["buildTypeId"], _parse_build(item)) for item in data.get("build", [])
        ]

    async def get_queued_builds(self) -> list[QueuedBuild]:
        """Return every build waiting in the queue."""
        data = await self._request(
            "GET", "buildQueue", params={"fields": QUEUED_BUILD_FIELDS}
        )
        return [
            QueuedBuild(id=int(item["id"]), build_type_id=item["buildTypeId"])
            for item in data.get("build", [])
        ]

    async def get_build_history(self, build_type_id: str, count: int) -> list[Build]:
        """Return the most recent builds of a configuration on any branch, newest first."""
        data = await self._request(
            "GET",
            "builds",
            params={
                "locator": (
                    f"buildType:(id:{build_type_id}),defaultFilter:false,"
                    f"personal:false,running:any,count:{count}"
                ),
                "fields": f"build({BUILD_FIELDS})",
            },
        )
        return [_parse_build(item) for item in data.get("build", [])]

    async def get_build_changes(self, build_id: int) -> list[Change]:
        """Return the VCS changes included in a build."""
        data = await self._request(
            "GET",
            "changes",
            params={"locator": f"build:(id:{build_id})", "fields": CHANGE_FIELDS},
        )
        return [
            Change(
                id=int(item["id"]),
                version=item.get("version"),
                username=item.get("username"),
                date=parse_teamcity_datetime(item.get("date")),
                comment=item.get("comment"),
                web_url=item.get("webUrl"),
            )
            for item in data.get("change", [])
        ]

    async def get_agents(self) -> list[Agent]:
        """Return every authorized build agent, connected or not."""
        data = await self._request(
            "GET",
            "agents",
            params={
                "locator": "defaultFilter:false,authorized:true",
                "fields": AGENT_FIELDS,
            },
        )
        return [_parse_agent(item) for item in data.get("agent", [])]

    async def get_build_log_tail(self, build_id: int, lines: int) -> list[str]:
        """Return the last lines of a build log, streaming so large logs stay bounded in memory."""
        path = "downloadBuildLog.html"
        tail: deque[str] = deque(maxlen=lines)
        try:
            async with self._session.get(
                f"{self._base_url}/{path}",
                headers=self._headers("text/plain"),
                params={"buildId": str(build_id), "plain": "true"},
                timeout=aiohttp.ClientTimeout(total=120),
            ) as response:
                await self._raise_for_status(response, path)
                async for raw_line in response.content:
                    tail.append(
                        raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                    )
        except (aiohttp.ClientError, TimeoutError) as err:
            raise TeamCityConnectionError(
                f"Error communicating with TeamCity: {err}"
            ) from err
        return list(tail)

    async def trigger_build(self, build_type_id: str) -> None:
        """Queue a new build of the given build configuration."""
        await self._request(
            "POST", "buildQueue", json={"buildType": {"id": build_type_id}}
        )

    async def cancel_build(self, build_id: int, comment: str) -> None:
        """Stop a running build or remove a queued one."""
        build = await self._request(
            "GET", f"builds/id:{build_id}", params={"fields": "id,state"}
        )
        state = build.get("state")
        if state == "queued":
            path = f"buildQueue/id:{build_id}"
        elif state == "running":
            path = f"builds/id:{build_id}"
        else:
            raise TeamCityBuildNotActiveError(
                f"Build {build_id} is {state or 'in an unknown state'}, not running or queued"
            )
        await self._request(
            "POST", path, json={"comment": comment, "readdIntoQueue": False}
        )

    async def set_paused(self, build_type_id: str, paused: bool) -> None:
        """Pause or unpause a build configuration."""
        await self._request(
            "PUT",
            f"buildTypes/id:{build_type_id}/paused",
            text="true" if paused else "false",
            accept="text/plain",
        )
