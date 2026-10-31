"""Base entities for TeamCity."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from homeassistant.const import CONF_URL
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import BuildType
from .const import DOMAIN
from .coordinator import TeamCityConfigEntry, TeamCityCoordinator


def server_device_info(entry: TeamCityConfigEntry, server_version: str) -> DeviceInfo:
    """Device info for the TeamCity server that build configurations hang off."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="JetBrains",
        model="TeamCity",
        sw_version=server_version,
        configuration_url=entry.data[CONF_URL],
        entry_type=DeviceEntryType.SERVICE,
    )


class TeamCityServerEntity(CoordinatorEntity[TeamCityCoordinator]):
    """An entity describing the TeamCity server as a whole."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TeamCityCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = server_device_info(entry, coordinator.server_version)


class TeamCityBuildTypeEntity(CoordinatorEntity[TeamCityCoordinator]):
    """An entity belonging to one build configuration."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: TeamCityCoordinator, build_type: BuildType, key: str
    ) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id
        self.build_type_id = build_type.id
        self._attr_unique_id = f"{entry_id}_{build_type.id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_{build_type.id}")},
            name=f"{build_type.project_name} / {build_type.name}",
            manufacturer="JetBrains",
            model="Build configuration",
            configuration_url=build_type.web_url,
            entry_type=DeviceEntryType.SERVICE,
            via_device=(DOMAIN, entry_id),
        )

    @property
    def build_type(self) -> BuildType:
        return self.coordinator.data.build_types[self.build_type_id]

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.build_type_id in self.coordinator.data.build_types
        )


def async_add_build_type_entities(
    coordinator: TeamCityCoordinator,
    async_add_entities: AddConfigEntryEntitiesCallback,
    create_entities: Callable[[BuildType], Iterable[Entity]],
) -> None:
    """Add entities for current build configurations and any that appear later."""
    known: set[str] = set()

    @callback
    def _add_new() -> None:
        new = [
            build_type
            for build_type_id, build_type in coordinator.data.build_types.items()
            if build_type_id not in known
        ]
        if not new:
            return
        known.update(build_type.id for build_type in new)
        async_add_entities(
            entity for build_type in new for entity in create_entities(build_type)
        )

    _add_new()
    coordinator.config_entry.async_on_unload(coordinator.async_add_listener(_add_new))
