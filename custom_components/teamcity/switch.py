"""Switches for TeamCity."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import BuildType
from .coordinator import TeamCityConfigEntry, TeamCityCoordinator
from .entity import TeamCityBuildTypeEntity, async_add_build_type_entities
from .services import async_set_paused


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeamCityConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TeamCity switches."""
    coordinator = entry.runtime_data
    async_add_build_type_entities(
        coordinator,
        async_add_entities,
        lambda build_type: (PausedSwitch(coordinator, build_type),),
    )


class PausedSwitch(TeamCityBuildTypeEntity, SwitchEntity):
    """On while the build configuration is paused in TeamCity."""

    def __init__(self, coordinator: TeamCityCoordinator, build_type: BuildType) -> None:
        super().__init__(coordinator, build_type, "paused")

    @property
    def is_on(self) -> bool:
        return self.build_type.paused

    async def async_turn_on(self, **kwargs: Any) -> None:
        await async_set_paused(self.coordinator, self.build_type_id, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await async_set_paused(self.coordinator, self.build_type_id, False)
