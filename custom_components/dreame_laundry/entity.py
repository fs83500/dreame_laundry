"""Base entity."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import LaundryCoordinator


class LaundryEntity(CoordinatorEntity[LaundryCoordinator]):
    """Entity bound to one appliance."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LaundryCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self.key = key
        dev = coordinator.device
        self._attr_unique_id = f"{dev['did']}_{key}"
        connections = (
            {(CONNECTION_NETWORK_MAC, dev["mac"].lower())} if dev.get("mac") else set()
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, dev["did"])},
            connections=connections,
            manufacturer=MANUFACTURER,
            model=dev["model"],
            name=dev["name"],
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        spec = self.coordinator.mapping.get(self.key)
        if spec is None:
            return None
        attrs: dict[str, Any] = {"property": spec.code}
        if self.key in self.coordinator.guessed:
            attrs["mapping"] = "guess, check with the property scan"
        raw = self.coordinator.raw(self.key)
        if spec.value_map or spec.scale is not None:
            attrs["raw_value"] = raw
        return attrs
