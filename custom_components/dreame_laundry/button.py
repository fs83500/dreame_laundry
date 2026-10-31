"""Buttons: property scan and manual refresh."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LaundryConfigEntry
from .coordinator import LaundryCoordinator
from .entity import LaundryEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LaundryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    entities: list[ButtonEntity] = []
    for coordinator in entry.runtime_data.values():
        entities += [LaundryScanButton(coordinator), LaundryRefreshButton(coordinator)]
    async_add_entities(entities)


class LaundryScanButton(LaundryEntity, ButtonEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "scan"
    _attr_icon = "mdi:magnify-scan"

    def __init__(self, coordinator: LaundryCoordinator) -> None:
        super().__init__(coordinator, "scan")

    async def async_press(self) -> None:
        await self.coordinator.async_scan()


class LaundryRefreshButton(LaundryEntity, ButtonEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "refresh"
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: LaundryCoordinator) -> None:
        super().__init__(coordinator, "refresh")

    async def async_press(self) -> None:
        await self.coordinator.async_refresh()
