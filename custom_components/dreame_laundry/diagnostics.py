"""Diagnostics: everything needed to finish the property mapping, credentials redacted."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import LaundryConfigEntry

TO_REDACT = {
    CONF_PASSWORD,
    CONF_USERNAME,
    "mac",
    "masterUid",
    "bindDomain",
    "uid",
    "property",
    "sn",
    "did",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: LaundryConfigEntry
) -> dict[str, Any]:
    devices = []
    for coordinator in entry.runtime_data.values():
        devices.append(
            {
                "model": coordinator.device["model"],
                "kind": coordinator.device["kind"],
                "online": coordinator.online,
                "mqtt_connected": coordinator.client.mqtt_connected,
                "mapping": {k: s.code for k, s in coordinator.mapping.items()},
                "guessed_keys": sorted(coordinator.guessed),
                "values": coordinator.data,
                "discovered": coordinator.discovered,
                "cloud_info": async_redact_data(
                    coordinator.client.info or {}, TO_REDACT
                ),
            }
        )
    return {
        "entry": async_redact_data({**entry.data, "devices": None}, TO_REDACT),
        "options": dict(entry.options),
        "devices": devices,
    }
