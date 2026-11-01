"""Sensors: state, program, remaining time, consumption, raw discovered properties."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import LaundryConfigEntry
from .const import SIGNAL_DISCOVERED
from .coordinator import LaundryCoordinator
from .entity import LaundryEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class LaundrySensorDescription(SensorEntityDescription):
    """Mapped sensor."""


DESCRIPTIONS: tuple[LaundrySensorDescription, ...] = (
    LaundrySensorDescription(key="status", translation_key="status"),
    LaundrySensorDescription(key="fault", translation_key="fault"),
    LaundrySensorDescription(key="program", translation_key="program"),
    LaundrySensorDescription(
        key="remaining_time",
        translation_key="remaining_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    LaundrySensorDescription(
        key="progress",
        translation_key="progress",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    LaundrySensorDescription(
        key="power_w",
        translation_key="power_w",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    LaundrySensorDescription(
        key="energy_total",
        translation_key="energy_total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    # Per-cycle counters reset at each cycle: TOTAL_INCREASING handles the reset,
    # so this entity can be used as-is in the Energy dashboard.
    LaundrySensorDescription(
        key="energy_cycle",
        translation_key="energy_cycle",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    LaundrySensorDescription(
        key="water",
        translation_key="water",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    LaundrySensorDescription(
        key="temperature",
        translation_key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    LaundrySensorDescription(
        key="spin_speed",
        translation_key="spin_speed",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
    ),
    LaundrySensorDescription(key="drying_level", translation_key="drying_level"),
)

_TEXT_KEYS = {"status", "fault", "program", "drying_level"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LaundryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    for coordinator in entry.runtime_data.values():
        entities: list[SensorEntity] = [
            LaundryMappedSensor(coordinator, desc)
            for desc in DESCRIPTIONS
            if desc.key in coordinator.mapping
        ]
        if "remaining_time" in coordinator.mapping:
            entities.append(LaundryEndTimeSensor(coordinator))
        if (
            "power_w" in coordinator.mapping
            and "energy_total" not in coordinator.mapping
            and "energy_cycle" not in coordinator.mapping
        ):
            entities.append(LaundryIntegratedEnergySensor(coordinator))
        async_add_entities(entities)
        _setup_raw_sensors(hass, entry, coordinator, async_add_entities)


def _setup_raw_sensors(
    hass: HomeAssistant,
    entry: LaundryConfigEntry,
    coordinator: LaundryCoordinator,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    known: set[str] = set()

    @callback
    def _add_new() -> None:
        new = [code for code in coordinator.discovered if code not in known]
        known.update(new)
        if new:
            async_add_entities(
                LaundryRawSensor(coordinator, code) for code in sorted(new)
            )

    _add_new()
    entry.async_on_unload(
        async_dispatcher_connect(
            hass, SIGNAL_DISCOVERED.format(coordinator.did), _add_new
        )
    )


class LaundryMappedSensor(LaundryEntity, SensorEntity):
    """Sensor bound to a mapped property."""

    entity_description: LaundrySensorDescription

    def __init__(
        self, coordinator: LaundryCoordinator, description: LaundrySensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        value = self.coordinator.value(self.key)
        if value is None:
            return None
        if self.key in _TEXT_KEYS:
            return str(value)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return value


class LaundryEndTimeSensor(LaundryEntity, SensorEntity):
    """Expected end of cycle (now + remaining time), handy for notifications."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_translation_key = "end_time"

    def __init__(self, coordinator: LaundryCoordinator) -> None:
        super().__init__(coordinator, "end_time")
        self._end: datetime | None = None

    @callback
    def _handle_coordinator_update(self) -> None:
        remaining = self.coordinator.value("remaining_time")
        if (
            isinstance(remaining, (int, float))
            and remaining > 0
            and self.coordinator.is_running is not False
        ):
            end = dt_util.utcnow().replace(second=0, microsecond=0) + timedelta(
                minutes=remaining
            )
            # avoid flapping by one minute between two polls
            if self._end is None or abs((end - self._end).total_seconds()) > 90:
                self._end = end
        else:
            self._end = None
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> datetime | None:
        return self._end

    @property
    def extra_state_attributes(self) -> None:
        return None


class LaundryIntegratedEnergySensor(LaundryEntity, RestoreSensor):
    """kWh integrated from the instantaneous power when the appliance gives no energy counter."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 3
    _attr_translation_key = "energy_integrated"

    def __init__(self, coordinator: LaundryCoordinator) -> None:
        super().__init__(coordinator, "energy_integrated")
        self._total = 0.0
        self._last_power: float | None = None
        self._last_time: datetime | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (
            last := await self.async_get_last_sensor_data()
        ) is not None and last.native_value is not None:
            try:
                self._total = float(last.native_value)
            except (TypeError, ValueError):
                self._total = 0.0

    @callback
    def _handle_coordinator_update(self) -> None:
        power = self.coordinator.value("power_w")
        now = dt_util.utcnow()
        if isinstance(power, (int, float)) and not isinstance(power, bool):
            if self._last_power is not None and self._last_time is not None:
                hours = (now - self._last_time).total_seconds() / 3600
                if (
                    0 < hours < 0.25
                ):  # ignore gaps (asleep / offline) longer than 15 min
                    self._total += (self._last_power + power) / 2 * hours / 1000
            self._last_power, self._last_time = float(power), now
        else:
            self._last_power, self._last_time = None, None
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> float:
        return round(self._total, 4)

    @property
    def extra_state_attributes(self) -> None:
        return None


class LaundryRawSensor(LaundryEntity, SensorEntity):
    """Raw value of a property found by the scan or pushed by MQTT."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "raw"

    def __init__(self, coordinator: LaundryCoordinator, code: str) -> None:
        super().__init__(coordinator, f"raw_{code.replace('.', '_')}")
        self.code = code
        self._attr_translation_placeholders = {"code": code}

    @property
    def native_value(self) -> Any:
        value = (self.coordinator.data or {}).get(
            self.code, self.coordinator.discovered.get(self.code)
        )
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)[:255]
        if isinstance(value, str):
            return value[:255]
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"property": self.code}
