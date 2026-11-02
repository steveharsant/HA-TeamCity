"""Buttons for TeamCity."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import BuildType
from .coordinator import TeamCityConfigEntry, TeamCityCoordinator
from .entity import TeamCityBuildTypeEntity, async_add_build_type_entities
from .services import async_trigger_build


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeamCityConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TeamCity buttons."""
    coordinator = entry.runtime_data
    async_add_build_type_entities(
        coordinator,
        async_add_entities,
        lambda build_type: (TriggerBuildButton(coordinator, build_type),),
    )


class TriggerBuildButton(TeamCityBuildTypeEntity, ButtonEntity):
    """Queues a new build of the configuration's default branch."""

    def __init__(self, coordinator: TeamCityCoordinator, build_type: BuildType) -> None:
        super().__init__(coordinator, build_type, "trigger_build")

    async def async_press(self) -> None:
        await async_trigger_build(self.coordinator, self.build_type_id)
