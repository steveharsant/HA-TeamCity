"""Binary sensors for TeamCity."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import BuildType
from .coordinator import TeamCityConfigEntry, TeamCityCoordinator
from .entity import TeamCityBuildTypeEntity, async_add_build_type_entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeamCityConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TeamCity binary sensors."""
    coordinator = entry.runtime_data
    async_add_build_type_entities(
        coordinator,
        async_add_entities,
        lambda build_type: (
            StateBinarySensor(coordinator, build_type),
            StatusBinarySensor(coordinator, build_type),
        ),
    )


class StateBinarySensor(TeamCityBuildTypeEntity, BinarySensorEntity):
    """On while any build of this configuration is running, on any branch."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator: TeamCityCoordinator, build_type: BuildType) -> None:
        super().__init__(coordinator, build_type, "state")

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.running.get(self.build_type_id))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        builds = self.coordinator.data.running.get(self.build_type_id, [])
        return {
            "queued": self.coordinator.data.queued[self.build_type_id],
            "builds": [
                {
                    "build_id": build.id,
                    "build_number": build.number,
                    "branch": build.branch_name,
                    "percentage_complete": build.percentage_complete,
                    "web_url": build.web_url,
                }
                for build in builds
            ],
        }


class StatusBinarySensor(TeamCityBuildTypeEntity, BinarySensorEntity):
    """On when the last finished build on the default branch failed."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: TeamCityCoordinator, build_type: BuildType) -> None:
        super().__init__(coordinator, build_type, "status")

    @property
    def is_on(self) -> bool | None:
        build = self.build_type.last_build
        if build is None or build.status is None:
            return None
        return build.status == "FAILURE"
