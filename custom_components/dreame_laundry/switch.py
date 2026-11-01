"""Switches: keep-awake (always available) and power (once mapped)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import STATE_OFF, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import LaundryConfigEntry
from .coordinator import LaundryCoordinator
from .entity import LaundryEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LaundryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    entities: list[SwitchEntity] = []
    for coordinator in entry.runtime_data.values():
        entities.append(LaundryKeepAwakeSwitch(coordinator))
        if "power" in coordinator.mapping:
            entities.append(LaundryPowerSwitch(coordinator))
    async_add_entities(entities)


class LaundryKeepAwakeSwitch(LaundryEntity, SwitchEntity, RestoreEntity):
    """Keeps the cloud session/MQTT alive, turns the appliance back on and disables auto power-off."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "keep_awake"

    def __init__(self, coordinator: LaundryCoordinator) -> None:
        super().__init__(coordinator, "keep_awake")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        self.coordinator.keep_awake = not (last is not None and last.state == STATE_OFF)

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self.coordinator.keep_awake

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        mapping = self.coordinator.mapping
        return {
            "wakes_up_appliance": "power" in mapping,
            "disables_auto_power_off": "auto_power_off" in mapping
            and "keep_value" in mapping["auto_power_off"].extra,
            "last_action": self.coordinator.last_keep_awake_action,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        self.coordinator.keep_awake = True
        self.async_write_ha_state()
        await self.coordinator._async_keep_awake_tick()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self.coordinator.keep_awake = False
        self.async_write_ha_state()


class LaundryPowerSwitch(LaundryEntity, SwitchEntity):
    """Appliance power. Turning it off also pauses keep-awake, otherwise it would turn it back on."""

    _attr_translation_key = "power"

    def __init__(self, coordinator: LaundryCoordinator) -> None:
        super().__init__(coordinator, "power")

    @property
    def is_on(self) -> bool | None:
        raw = self.coordinator.raw("power")
        if raw is None:
            return None
        return raw == self.coordinator.mapping["power"].extra.get("on", True)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set(
            "power", self.coordinator.mapping["power"].extra.get("on", True)
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        spec = self.coordinator.mapping["power"]
        on_value = spec.extra.get("on", True)
        off_value = spec.extra.get(
            "off", (not on_value) if isinstance(on_value, bool) else 0
        )
        self.coordinator.keep_awake = False
        await self.coordinator.async_set("power", off_value)
        self.coordinator.async_update_listeners()
