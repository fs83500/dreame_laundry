"""Coordinator: polling + MQTT push + keep-awake + property scan, one per appliance."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import CannotConnect, InvalidAuth, LaundryCloudDevice
from .const import (
    CONF_KEEP_AWAKE_INTERVAL,
    CONF_SCAN_INTERVAL,
    DEFAULT_KEEP_AWAKE_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    RAW_POLL_EVERY,
    SCAN_PIIDS,
    SCAN_SIIDS,
    SIGNAL_DISCOVERED,
)
from .models import PropSpec

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)


class LaundryCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Holds the raw property values of one appliance, keyed "siid.piid"."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device: dict[str, Any],
        client: LaundryCloudDevice,
        mapping: dict[str, PropSpec],
        guessed: set[str],
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {device['name']}",
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.device = device
        self.did: str = device["did"]
        self.client = client
        self.mapping = mapping
        self.guessed = guessed  # keys coming from default guesses, not from the user
        self.discovered: dict[str, Any] = {}
        self.online: bool = False
        self.keep_awake: bool = True
        self.last_keep_awake_action: str | None = None
        self.last_push: datetime | None = None
        self._poll_count = 0
        self._store: Store[dict[str, Any]] = Store(hass, 1, f"{DOMAIN}.{self.did}")

    # ------------------------------------------------------------------ helpers
    def value(self, key: str) -> Any:
        """Converted value of a mapped semantic key."""
        spec = self.mapping.get(key)
        if spec is None or not self.data:
            return None
        return spec.convert(self.data.get(spec.code))

    def raw(self, key: str) -> Any:
        spec = self.mapping.get(key)
        if spec is None or not self.data:
            return None
        return self.data.get(spec.code)

    @property
    def is_running(self) -> bool | None:
        status = self.mapping.get("status")
        running_states = status.extra.get("running_states") if status else None
        if running_states is not None and self.raw("status") is not None:
            return str(self.raw("status")) in {str(v) for v in running_states}
        remaining = self.value("remaining_time")
        if isinstance(remaining, (int, float)):
            return remaining > 0
        power = self.value("power_w")
        if isinstance(power, (int, float)):
            return power > 5
        return None

    # ------------------------------------------------------------------ lifecycle
    async def async_load_store(self) -> None:
        stored = await self._store.async_load() or {}
        self.discovered = stored.get("discovered", {})

    async def async_start_keep_awake(self) -> None:
        interval = self.config_entry.options.get(
            CONF_KEEP_AWAKE_INTERVAL, DEFAULT_KEEP_AWAKE_INTERVAL
        )
        self.config_entry.async_on_unload(
            async_track_time_interval(
                self.hass,
                self._async_keep_awake_tick,
                timedelta(seconds=interval),
                name=f"{self.name} keep awake",
            )
        )

    async def async_stop(self) -> None:
        await self.hass.async_add_executor_job(self.client.disconnect)

    # ------------------------------------------------------------------ polling
    def _codes_to_poll(self) -> list[tuple[int, int]]:
        codes = {(s.siid, s.piid) for s in self.mapping.values()}
        if self._poll_count % RAW_POLL_EVERY == 0:
            for code in self.discovered:
                siid, piid = code.split(".")
                codes.add((int(siid), int(piid)))
        return sorted(codes)

    def _sync_update(self) -> dict[str, Any]:
        self.client.ensure_connected(self._on_push_thread, None)
        return self.client.get_props(self._codes_to_poll())

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            values = await self.hass.async_add_executor_job(self._sync_update)
        except InvalidAuth as err:
            raise ConfigEntryAuthFailed("Dreamehome login refused") from err
        except CannotConnect as err:
            raise UpdateFailed("Dreamehome cloud unreachable") from err
        finally:
            self._poll_count += 1

        online = self.client.info.get("online")
        # The cloud answers but the appliance (asleep) does not: keep the last values.
        self.online = bool(values) if online is None else bool(online) and bool(values)
        merged = dict(self.data or {})
        merged.update(values)
        self._remember_discovered(values)
        return merged

    # ------------------------------------------------------------------ MQTT push
    def _on_push_thread(self, data: dict[str, Any]) -> None:
        self.hass.loop.call_soon_threadsafe(self._handle_push, data)

    @callback
    def _handle_push(self, data: dict[str, Any]) -> None:
        if not isinstance(data, dict) or data.get("method") != "properties_changed":
            _LOGGER.debug("%s push ignored: %s", self.name, data)
            return
        changed = {}
        for item in data.get("params") or []:
            if (
                isinstance(item, dict)
                and "siid" in item
                and "piid" in item
                and "value" in item
            ):
                changed[f"{item['siid']}.{item['piid']}"] = item["value"]
        if not changed:
            return
        _LOGGER.debug("%s push: %s", self.name, changed)
        self.online = True
        self.last_push = dt_util.utcnow()
        self._remember_discovered(changed, allow_new=True)
        self.async_set_updated_data({**(self.data or {}), **changed})

    def _remember_discovered(
        self, values: dict[str, Any], allow_new: bool = False
    ) -> None:
        """Refresh known raw props; with allow_new, unmapped props seen in a push become raw sensors."""
        mapped = {spec.code for spec in self.mapping.values()}
        new = False
        for code, val in values.items():
            if code in self.discovered:
                self.discovered[code] = val
            elif allow_new and code not in mapped:
                self.discovered[code] = val
                new = True
        if new:
            self._store.async_delay_save(lambda: {"discovered": self.discovered}, 5)
            async_dispatcher_send(self.hass, SIGNAL_DISCOVERED.format(self.did))

    # ------------------------------------------------------------------ writes
    async def async_set(self, key: str, value: Any) -> None:
        spec = self.mapping.get(key)
        if spec is None or not spec.writable:
            raise HomeAssistantError(
                f"'{key}' is not mapped as writable for {self.device['name']}"
            )
        try:
            ok = await self.hass.async_add_executor_job(
                self.client.set_prop, spec.siid, spec.piid, value
            )
        except CannotConnect as err:
            raise HomeAssistantError("Dreamehome cloud unreachable") from err
        if not ok:
            raise HomeAssistantError(f"The appliance refused {spec.code}={value}")
        self.async_set_updated_data({**(self.data or {}), spec.code: value})

    async def _async_keep_awake_tick(self, _now: datetime | None = None) -> None:
        """Wake the appliance up / keep auto power-off disabled / keep the session alive."""
        if not self.keep_awake:
            return
        try:
            await self.async_refresh()
            power = self.mapping.get("power")
            if power is not None and self.data is not None:
                on_value = power.extra.get("on", True)
                current = self.data.get(power.code)
                if current is not None and current != on_value:
                    _LOGGER.info(
                        "%s is off (%s), keep-awake turns it back on",
                        self.name,
                        current,
                    )
                    await self.async_set("power", on_value)
                    self.last_keep_awake_action = (
                        f"{dt_util.now().isoformat(timespec='seconds')} power on"
                    )
            auto_off = self.mapping.get("auto_power_off")
            if (
                auto_off is not None
                and "keep_value" in auto_off.extra
                and self.data is not None
            ):
                keep = auto_off.extra["keep_value"]
                if self.data.get(auto_off.code) not in (None, keep):
                    await self.async_set("auto_power_off", keep)
                    self.last_keep_awake_action = (
                        f"{dt_util.now().isoformat(timespec='seconds')} auto-off={keep}"
                    )
        except HomeAssistantError as err:
            _LOGGER.debug("%s keep-awake: %s", self.name, err)

    # ------------------------------------------------------------------ discovery
    async def async_scan(self) -> dict[str, Any]:
        """Brute-force read siid 1-16 / piid 1-40 and expose every answer as a raw sensor."""
        codes = [(s, p) for s in SCAN_SIIDS for p in SCAN_PIIDS]
        try:
            found = await self.hass.async_add_executor_job(self.client.get_props, codes)
        except InvalidAuth as err:
            raise ConfigEntryAuthFailed from err
        except CannotConnect as err:
            raise HomeAssistantError("Dreamehome cloud unreachable") from err
        if not found:
            raise HomeAssistantError(
                "No property answered: the appliance is probably asleep. Turn it on and scan again."
            )
        self.discovered.update(found)
        await self._store.async_save({"discovered": self.discovered})
        self.async_set_updated_data({**(self.data or {}), **found})
        async_dispatcher_send(self.hass, SIGNAL_DISCOVERED.format(self.did))

        lines = "\n".join(
            f"| `{code}` | `{json.dumps(val, ensure_ascii=False)[:60]}` |"
            for code, val in sorted(
                found.items(), key=lambda kv: tuple(map(int, kv[0].split(".")))
            )
        )
        persistent_notification.async_create(
            self.hass,
            f"**{self.device['name']}** (`{self.device['model']}`) : {len(found)} propriétés.\n\n"
            f"| siid.piid | valeur |\n|---|---|\n{lines}\n\n"
            "Lance un scan à l'arrêt puis pendant un cycle pour repérer état, temps restant et consommation.",
            title="Dreame Laundry : scan des propriétés",
            notification_id=f"{DOMAIN}_scan_{self.did}",
        )
        return found
