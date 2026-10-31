"""Sensors for TeamCity."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import BuildType
from .coordinator import TeamCityConfigEntry, TeamCityCoordinator
from .entity import (
    TeamCityBuildTypeEntity,
    TeamCityServerEntity,
    async_add_build_type_entities,
)

BUILD_STATUSES = ["success", "failure", "unknown"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeamCityConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TeamCity sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        [QueuedBuildsSensor(coordinator), RunningBuildsSensor(coordinator)]
    )
    async_add_build_type_entities(
        coordinator,
        async_add_entities,
        lambda build_type: (
            LastBuildStatusSensor(coordinator, build_type),
            LastBuildFinishedSensor(coordinator, build_type),
        ),
    )


class QueuedBuildsSensor(TeamCityServerEntity, SensorEntity):
    """Number of builds waiting in the queue."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: TeamCityCoordinator) -> None:
        super().__init__(coordinator, "queued_builds")

    @property
    def native_value(self) -> int:
        return self.coordinator.data.queued_count


class RunningBuildsSensor(TeamCityServerEntity, SensorEntity):
    """Number of builds currently running."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: TeamCityCoordinator) -> None:
        super().__init__(coordinator, "running_builds")

    @property
    def native_value(self) -> int:
        return self.coordinator.data.running_count


class LastBuildStatusSensor(TeamCityBuildTypeEntity, SensorEntity):
    """Status of the last finished build on the default branch."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = BUILD_STATUSES

    def __init__(self, coordinator: TeamCityCoordinator, build_type: BuildType) -> None:
        super().__init__(coordinator, build_type, "last_build_status")

    @property
    def native_value(self) -> str | None:
        build = self.build_type.last_build
        if build is None or build.status is None:
            return None
        status = build.status.lower()
        return status if status in BUILD_STATUSES else "unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        build = self.build_type.last_build
        if build is None:
            return {}
        return {
            "build_id": build.id,
            "build_number": build.number,
            "status_text": build.status_text,
            "branch": build.branch_name,
            "started": build.start_date,
            "web_url": build.web_url,
        }


class LastBuildFinishedSensor(TeamCityBuildTypeEntity, SensorEntity):
    """When the last finished build on the default branch completed."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: TeamCityCoordinator, build_type: BuildType) -> None:
        super().__init__(coordinator, build_type, "last_build_finished")

    @property
    def native_value(self) -> datetime | None:
        build = self.build_type.last_build
        return build.finish_date if build else None
