"""Binary sensors: cycle running, door, child lock, appliance reachable."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LaundryConfigEntry
from .coordinator import LaundryCoordinator
from .entity import LaundryEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LaundryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    entities: list[BinarySensorEntity] = []
    for coordinator in entry.runtime_data.values():
        entities.append(LaundryRunningSensor(coordinator))
        entities.append(LaundryOnlineSensor(coordinator))
        if "door" in coordinator.mapping:
            entities.append(
                LaundryFlagSensor(coordinator, "door", BinarySensorDeviceClass.DOOR)
            )
        if "child_lock" in coordinator.mapping:
            entities.append(
                LaundryFlagSensor(
                    coordinator, "child_lock", BinarySensorDeviceClass.LOCK
                )
            )
    async_add_entities(entities)


class LaundryRunningSensor(LaundryEntity, BinarySensorEntity):
    """Cycle in progress (status in running_states, else remaining time > 0, else power > 5 W)."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_translation_key = "running"

    def __init__(self, coordinator: LaundryCoordinator) -> None:
        super().__init__(coordinator, "running")

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.is_running


class LaundryOnlineSensor(LaundryEntity, BinarySensorEntity):
    """The appliance answers through the cloud (False = asleep / offline)."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "online"

    def __init__(self, coordinator: LaundryCoordinator) -> None:
        super().__init__(coordinator, "online")

    @property
    def is_on(self) -> bool:
        return self.coordinator.online

    @property
    def extra_state_attributes(self) -> dict:
        c = self.coordinator
        return {
            "mqtt_connected": c.client.mqtt_connected,
            "last_push": c.last_push.isoformat() if c.last_push else None,
            "last_keep_awake_action": c.last_keep_awake_action,
        }


class LaundryFlagSensor(LaundryEntity, BinarySensorEntity):
    """Boolean-ish mapped property. Mapping option "invert": true flips it."""

    def __init__(
        self,
        coordinator: LaundryCoordinator,
        key: str,
        device_class: BinarySensorDeviceClass,
    ) -> None:
        super().__init__(coordinator, key)
        self._attr_device_class = device_class
        self._attr_translation_key = key

    @property
    def is_on(self) -> bool | None:
        raw = self.coordinator.raw(self.key)
        if raw is None:
            return None
        value = raw not in (0, False, "0", "false", "off")
        if self.coordinator.mapping[self.key].extra.get("invert"):
            value = not value
        # HA: lock "on" = unlocked
        return not value if self.key == "child_lock" else value
