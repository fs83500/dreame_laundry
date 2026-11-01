"""Property mapping (MIoT siid/piid -> semantic key) for Dreame laundry appliances.

Dreame does not publish the MIoT spec of its washers/dryers. Most defaults below are
read-only guesses following the usual MIoT "washer" service layout and MUST be checked
with the "Scan properties" button.
"remaining_time": "2.11" is CONFIRMED on washer hardware (2026-10-31); dryer defaults
come from a property survey on dreame.dryer.l9nacn (2026-11-01).
Writable keys (power, auto_power_off) are never guessed: they only exist once you
declare them in the integration options.

Override format (integration options, JSON), by appliance kind or by device id:

{
  "washer": {
    "status": {"prop": "2.2", "map": {"1": "Veille", "2": "Lavage"}, "running_states": [2, 3]},
    "remaining_time": "2.11",
    "power": {"prop": "2.1", "on": true},
    "auto_power_off": {"prop": "2.20", "keep_value": 0},
    "energy_cycle": {"prop": "2.12", "scale": 0.01}
  },
  "dryer": {...},
  "123456789": {...}          # device id, wins over the kind
}

A key set to null removes the default.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .const import KIND_DRYER, KIND_OTHER, KIND_WASHER

# Semantic keys understood by the platforms
SENSOR_KEYS = (
    "status",
    "fault",
    "program",
    "remaining_time",
    "progress",
    "power_w",
    "energy_total",
    "energy_cycle",
    "water",
    "temperature",
    "spin_speed",
    "drying_level",
)
BINARY_KEYS = ("door", "child_lock")
WRITABLE_KEYS = ("power", "auto_power_off")
ALL_KEYS = SENSOR_KEYS + BINARY_KEYS + WRITABLE_KEYS

_GUESS_WASHER = {
    "status": "2.2",
    "fault": "2.3",
    "program": "2.4",
    # Confirmed 2026-10-31 on a real washer: 2.11 = remaining minutes.
    "remaining_time": "2.11",
}
# From a property survey on dreame.dryer.l9nacn (2026-11-01): 2.3 = program
# (confirmed), 2.1 = state (1 = stopped, 3 = running, probable), 2.11 = remaining
# minutes (probable). No fault property identified yet.
_GUESS_DRYER = {
    "status": {
        "prop": "2.1",
        "map": {"1": "Arrêt", "3": "En cours"},
        "running_states": [3],
    },
    "program": "2.3",
    "remaining_time": "2.11",
}
DEFAULT_MAPPINGS: dict[str, dict[str, Any]] = {
    KIND_WASHER: dict(_GUESS_WASHER),
    KIND_DRYER: dict(_GUESS_DRYER),
    KIND_OTHER: {},
}

_PROP_RE = re.compile(r"^\s*(\d{1,3})\s*[.:/]\s*(\d{1,3})\s*$")


class MappingError(ValueError):
    """Invalid user mapping."""


def parse_prop(value: str) -> tuple[int, int]:
    """Parse "siid.piid"."""
    match = _PROP_RE.match(str(value))
    if not match:
        raise MappingError(f"invalid property '{value}', expected 'siid.piid'")
    return int(match.group(1)), int(match.group(2))


@dataclass(frozen=True)
class PropSpec:
    """One mapped property."""

    key: str
    siid: int
    piid: int
    scale: float | None = None
    offset: float = 0
    value_map: dict[str, str] | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def code(self) -> str:
        return f"{self.siid}.{self.piid}"

    @property
    def writable(self) -> bool:
        return self.key in WRITABLE_KEYS

    def convert(self, value: Any) -> Any:
        """Raw device value -> displayed value."""
        if value is None:
            return None
        if self.value_map:
            return self.value_map.get(str(value), str(value))
        if (
            (self.scale is not None or self.offset)
            and isinstance(value, (int, float))
            and not isinstance(value, bool)
        ):
            scale = 1 if self.scale is None else self.scale
            return round(value * scale + self.offset, 3)
        return value


def guess_kind(model: str) -> str:
    model = (model or "").lower()
    if "dryer" in model or ".dry" in model or "drying" in model:
        return KIND_DRYER
    if "wash" in model:
        return KIND_WASHER
    return KIND_OTHER


def is_laundry(model: str) -> bool:
    return guess_kind(model) != KIND_OTHER or bool(
        re.search(r"cloth|laundry", (model or "").lower())
    )


def _spec_from(key: str, raw: Any) -> PropSpec:
    if isinstance(raw, str):
        siid, piid = parse_prop(raw)
        return PropSpec(key, siid, piid)
    if not isinstance(raw, dict) or "prop" not in raw:
        raise MappingError(f'\'{key}\': expected "siid.piid" or an object with "prop"')
    siid, piid = parse_prop(raw["prop"])
    value_map = raw.get("map")
    if value_map is not None:
        if not isinstance(value_map, dict):
            raise MappingError(f"'{key}.map' must be an object")
        value_map = {str(k): str(v) for k, v in value_map.items()}
    scale = raw.get("scale")
    if scale is not None and not isinstance(scale, (int, float)):
        raise MappingError(f"'{key}.scale' must be a number")
    offset = raw.get("offset", 0)
    if isinstance(offset, bool) or not isinstance(offset, (int, float)):
        raise MappingError(f"'{key}.offset' must be a number")
    extra = {
        k: v for k, v in raw.items() if k not in ("prop", "map", "scale", "offset")
    }
    return PropSpec(key, siid, piid, scale, float(offset), value_map, extra)


def validate_overrides(overrides: Any) -> dict[str, Any]:
    """Validate the user JSON (already decoded). Raises MappingError."""
    if overrides in (None, ""):
        return {}
    if not isinstance(overrides, dict):
        raise MappingError("the mapping must be a JSON object")
    for scope, keys in overrides.items():
        if not isinstance(keys, dict):
            raise MappingError(f"'{scope}' must be an object")
        for key, raw in keys.items():
            if key not in ALL_KEYS:
                raise MappingError(
                    f"unknown key '{key}' (allowed: {', '.join(ALL_KEYS)})"
                )
            if raw is not None:
                _spec_from(key, raw)
    return overrides


def build_mapping(
    kind: str, did: str, overrides: dict[str, Any] | None
) -> dict[str, PropSpec]:
    """Defaults for the kind, then kind overrides, then device overrides."""
    merged: dict[str, Any] = dict(DEFAULT_MAPPINGS.get(kind, {}))
    overrides = overrides or {}
    for scope in (kind, str(did)):
        for key, raw in (overrides.get(scope) or {}).items():
            if raw is None:
                merged.pop(key, None)
            else:
                merged[key] = raw
    return {key: _spec_from(key, raw) for key, raw in merged.items()}


def user_defined(
    kind: str, did: str, overrides: dict[str, Any] | None, key: str
) -> bool:
    """True when the key comes from the user (not a default guess)."""
    overrides = overrides or {}
    return any(
        (overrides.get(scope) or {}).get(key) is not None for scope in (kind, str(did))
    )
