"""Polls TeamCity and shares the result with every entity."""

from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass, field
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    Build,
    BuildType,
    TeamCityAuthenticationError,
    TeamCityClient,
    TeamCityError,
)
from .const import CONF_BUILD_TYPES, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type TeamCityConfigEntry = ConfigEntry[TeamCityCoordinator]


@dataclass(slots=True)
class TeamCityData:
    """Snapshot of the TeamCity server state."""

    build_types: dict[str, BuildType]
    running: dict[str, list[Build]] = field(default_factory=dict)
    queued: Counter[str] = field(default_factory=Counter)

    @property
    def running_count(self) -> int:
        return sum(len(builds) for builds in self.running.values())

    @property
    def queued_count(self) -> int:
        return sum(self.queued.values())


class TeamCityCoordinator(DataUpdateCoordinator[TeamCityData]):
    """Fetches build configurations, running builds and the queue together."""

    config_entry: TeamCityConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: TeamCityConfigEntry,
        client: TeamCityClient,
        server_version: str,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.client = client
        self.server_version = server_version

    async def _async_update_data(self) -> TeamCityData:
        try:
            build_types, running, queued = await asyncio.gather(
                self.client.get_build_types(),
                self.client.get_running_builds(),
                self.client.get_queued_build_type_ids(),
            )
        except TeamCityAuthenticationError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except TeamCityError as err:
            raise UpdateFailed(str(err)) from err

        selected: list[str] = self.config_entry.options.get(CONF_BUILD_TYPES, [])
        data = TeamCityData(
            build_types={
                build_type.id: build_type
                for build_type in build_types
                if not selected or build_type.id in selected
            }
        )
        for build_type_id, build in running:
            data.running.setdefault(build_type_id, []).append(build)
        data.queued.update(queued)
        return data
