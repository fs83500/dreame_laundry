"""api.py against a fake Dreamehome protocol object."""

from unittest.mock import patch

import pytest

from custom_components.dreame_laundry.api import CannotConnect, LaundryCloudDevice
from custom_components.dreame_laundry.models import (
    MappingError,
    build_mapping,
    validate_overrides,
)


class FakeProto:
    def __init__(self, *a, **k):
        self.logged_in = False
        self.auth_failed = False
        self._client_connected = False
        self.calls = []

    def login(self):
        self.logged_in = True
        return True

    def connect(self, cb, ccb):
        self.calls.append("connect")
        self._client_connected = True
        return {"online": True, "model": "x"}

    def send(self, method, params, retry_count=2, timeout=None):
        self.calls.append((method, len(params), timeout))
        if method == "get_properties":
            return [
                {
                    "did": "1",
                    "siid": p["siid"],
                    "piid": p["piid"],
                    "code": 0 if p["piid"] < 3 else -4004,
                    "value": p["piid"],
                }
                for p in params
            ]
        return [{"code": 0}]

    def disconnect(self):
        pass


def test_get_props_batches_and_filters():
    with patch("custom_components.dreame_laundry.api.DreameHomeCloud", FakeProto):
        dev = LaundryCloudDevice("u", "p", "eu", "1")
        dev.ensure_connected(lambda d: None)
        dev.ensure_connected(lambda d: None)  # cached, no second connect
        assert dev._proto.calls.count("connect") == 1
        values = dev.get_props([(2, p) for p in range(1, 46)])
        assert values == {"2.1": 1, "2.2": 2}
        assert [c for c in dev._proto.calls if c != "connect"] == [
            ("get_properties", 20, None),
            ("get_properties", 20, None),
            ("get_properties", 5, None),
        ]
        # explicit timeout is forwarded to the vendored client
        dev._proto.calls.clear()
        dev.get_props([(2, 1)], timeout=15)
        assert dev._proto.calls == [("get_properties", 1, 15)]
        assert dev.set_prop(2, 1, True) is True
        dev._proto.send = lambda *a, **kw: None
        with pytest.raises(CannotConnect):
            dev.get_props([(2, 1)])


def test_mapping():
    m = build_mapping(
        "washer",
        "9",
        {
            "washer": {"fault": None, "power_w": {"prop": "3.4", "scale": 0.1}},
            "9": {"program": "7.1"},
        },
    )
    assert "fault" not in m and m["status"].code == "2.2" and m["program"].code == "7.1"
    assert m["power_w"].convert(1234) == 123.4
    with pytest.raises(MappingError):
        validate_overrides({"washer": {"status": "abc"}})


def test_offset_without_scale():
    m = build_mapping(
        "washer", "9", {"washer": {"temperature": {"prop": "2.7", "offset": -40}}}
    )
    assert m["temperature"].convert(70) == 30
    assert m["status"].convert(3) == 3  # no scale, no offset: untouched
    with pytest.raises(MappingError):
        validate_overrides({"washer": {"temperature": {"prop": "2.7", "offset": "x"}}})


def test_dryer_defaults_from_survey():
    m = build_mapping("dryer", "1", {})
    assert m["program"].code == "2.3"
    assert m["remaining_time"].code == "2.11"
    assert m["status"].code == "2.1"
    assert m["status"].convert(1) == "Arrêt"
    assert m["status"].convert(3) == "En cours"
    assert m["status"].extra["running_states"] == [3]
    assert "fault" not in m
