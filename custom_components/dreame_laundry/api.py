"""Thin synchronous wrapper around the Dreamehome cloud client (run in the executor)."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterable
from typing import Any

from .cloud.protocol import DreameHomeCloud
from .const import BATCH_SIZE

_LOGGER = logging.getLogger(__name__)


class CannotConnect(Exception):
    """Cloud unreachable or unexpected answer."""


class InvalidAuth(Exception):
    """Wrong credentials / session refused."""


def _login(proto: DreameHomeCloud) -> None:
    if proto.login():
        return
    if proto.auth_failed:
        raise InvalidAuth
    raise CannotConnect


def list_devices(username: str, password: str, country: str) -> list[dict[str, Any]]:
    """Return every device of the Dreamehome account."""
    proto = DreameHomeCloud(username, password, "dreame", country)
    try:
        _login(proto)
        data = proto.get_devices()
        if data is None:
            raise CannotConnect
        records = (data.get("page") or {}).get("records") or []
        devices = []
        for rec in records:
            info = rec.get("deviceInfo") or {}
            devices.append(
                {
                    "did": str(rec.get("did")),
                    "model": rec.get("model") or "",
                    "name": rec.get("customName")
                    or info.get("displayName")
                    or rec.get("model")
                    or str(rec.get("did")),
                    "mac": rec.get("mac"),
                }
            )
        return devices
    finally:
        proto.disconnect()


class LaundryCloudDevice:
    """One appliance on the Dreamehome cloud (HTTP commands + MQTT push)."""

    def __init__(self, username: str, password: str, country: str, did: str) -> None:
        self.did = str(did)
        self._proto = DreameHomeCloud(
            username, password, "dreame", country, did=self.did
        )
        self.info: dict[str, Any] = {}
        self._info_time = 0.0

    @property
    def logged_in(self) -> bool:
        return self._proto.logged_in

    @property
    def mqtt_connected(self) -> bool:
        return bool(self._proto._client_connected)

    def ensure_connected(
        self,
        on_message: Callable[[dict[str, Any]], None],
        on_connected: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        """Login if needed and (re)open the MQTT push channel (device info refreshed every 5 min)."""
        if not self._proto.logged_in:
            _login(self._proto)
        elif (
            self.info
            and self.mqtt_connected
            and time.monotonic() - self._info_time < 300
        ):
            return self.info
        info = self._proto.connect(on_message, on_connected or (lambda: None))
        if info is None:
            if self._proto.auth_failed:
                raise InvalidAuth
            raise CannotConnect
        self.info = info
        self._info_time = time.monotonic()
        return info

    def get_props(self, codes: Iterable[tuple[int, int]]) -> dict[str, Any]:
        """Read properties, returns {"siid.piid": value} for the ones that answered."""
        codes = list(codes)
        values: dict[str, Any] = {}
        for i in range(0, len(codes), BATCH_SIZE):
            batch = codes[i : i + BATCH_SIZE]
            params = [{"did": self.did, "siid": s, "piid": p} for s, p in batch]
            result = self._proto.send("get_properties", params)
            if result is None:
                if self._proto.auth_failed:
                    raise InvalidAuth
                raise CannotConnect
            for item in result:
                if (
                    isinstance(item, dict)
                    and item.get("code", 0) == 0
                    and "value" in item
                ):
                    values[f"{item['siid']}.{item['piid']}"] = item["value"]
        return values

    def set_prop(self, siid: int, piid: int, value: Any) -> bool:
        result = self._proto.send(
            "set_properties",
            [{"did": self.did, "siid": siid, "piid": piid, "value": value}],
        )
        if not result:
            raise CannotConnect
        ok = all(isinstance(r, dict) and r.get("code", 0) == 0 for r in result)
        if not ok:
            _LOGGER.warning(
                "set %s.%s=%s refused by the device: %s", siid, piid, value, result
            )
        return ok

    def disconnect(self) -> None:
        self._proto.disconnect()
