"""Buttons for TeamCity."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import BuildType, TeamCityError
from .const import DOMAIN
from .coordinator import TeamCityConfigEntry, TeamCityCoordinator
from .entity import TeamCityBuildTypeEntity, async_add_build_type_entities


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
        try:
            await self.coordinator.client.trigger_build(self.build_type_id)
        except TeamCityError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="trigger_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        await self.coordinator.async_request_refresh()
