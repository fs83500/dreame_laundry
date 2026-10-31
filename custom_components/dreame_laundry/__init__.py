"""Dreame Laundry: Dreame washing machines and dryers through the Dreamehome cloud."""

from __future__ import annotations

import json
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from .api import LaundryCloudDevice
from .const import CONF_COUNTRY, CONF_DEVICES, CONF_MAPPING
from .coordinator import LaundryCoordinator
from .models import (
    DEFAULT_MAPPINGS,
    MappingError,
    build_mapping,
    user_defined,
    validate_overrides,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SWITCH, Platform.BUTTON]

type LaundryConfigEntry = ConfigEntry[dict[str, LaundryCoordinator]]


def _overrides(entry: ConfigEntry) -> dict:
    raw = entry.options.get(CONF_MAPPING) or ""
    try:
        return validate_overrides(json.loads(raw) if raw.strip() else {})
    except (ValueError, MappingError) as err:
        _LOGGER.error("Ignoring invalid property mapping in the options: %s", err)
        return {}


async def async_setup_entry(hass: HomeAssistant, entry: LaundryConfigEntry) -> bool:
    overrides = _overrides(entry)
    coordinators: dict[str, LaundryCoordinator] = {}
    try:
        for dev in entry.data[CONF_DEVICES]:
            client = LaundryCloudDevice(
                entry.data[CONF_USERNAME],
                entry.data[CONF_PASSWORD],
                entry.data[CONF_COUNTRY],
                dev["did"],
            )
            mapping = build_mapping(dev["kind"], dev["did"], overrides)
            guessed = {
                key
                for key in mapping
                if key in DEFAULT_MAPPINGS.get(dev["kind"], {})
                and not user_defined(dev["kind"], dev["did"], overrides, key)
            }
            coordinator = LaundryCoordinator(hass, entry, dev, client, mapping, guessed)
            coordinators[dev["did"]] = coordinator
            await coordinator.async_load_store()
            await coordinator.async_config_entry_first_refresh()
    except Exception:
        for coordinator in coordinators.values():
            await coordinator.async_stop()
        raise

    entry.runtime_data = coordinators
    for coordinator in coordinators.values():
        await coordinator.async_start_keep_awake()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: LaundryConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: LaundryConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        for coordinator in entry.runtime_data.values():
            await coordinator.async_stop()
    return unloaded
