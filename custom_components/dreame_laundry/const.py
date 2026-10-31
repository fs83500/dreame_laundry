"""Constants for the Dreame Laundry integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "dreame_laundry"
MANUFACTURER: Final = "Dreame"

CONF_COUNTRY: Final = "country"
CONF_DEVICES: Final = "devices"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_KEEP_AWAKE_INTERVAL: Final = "keep_awake_interval"
CONF_MAPPING: Final = "mapping"

COUNTRIES: Final = ["eu", "cn", "us", "ru", "sg", "kr"]
DEFAULT_COUNTRY: Final = "eu"

DEFAULT_SCAN_INTERVAL: Final = 30  # seconds, MQTT push fills the gaps
DEFAULT_KEEP_AWAKE_INTERVAL: Final = 60  # seconds

# Property scan range used by the "Scan properties" button
SCAN_SIIDS: Final = range(1, 17)
SCAN_PIIDS: Final = range(1, 41)
BATCH_SIZE: Final = 20

# Raw (discovered) properties are polled once every N regular polls,
# MQTT push keeps them fresh in between.
RAW_POLL_EVERY: Final = 5

KIND_WASHER: Final = "washer"
KIND_DRYER: Final = "dryer"
KIND_OTHER: Final = "other"

SIGNAL_DISCOVERED: Final = f"{DOMAIN}_discovered_{{}}"
