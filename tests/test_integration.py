"""End-to-end tests with a fake Dreamehome cloud."""

from __future__ import annotations

import json
from typing import Any, ClassVar
from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dreame_laundry.api import InvalidAuth
from custom_components.dreame_laundry.const import (
    CONF_COUNTRY,
    CONF_DEVICES,
    CONF_KEEP_AWAKE_INTERVAL,
    CONF_MAPPING,
    CONF_SCAN_INTERVAL,
    DOMAIN,
)

DEVICES = [
    {
        "did": "111",
        "model": "dreame.washer.l9xx",
        "name": "Lave-linge",
        "mac": "AA:BB:CC:00:00:01",
    },
    {
        "did": "222",
        "model": "dreame.dryer.l9xx",
        "name": "Sèche-linge",
        "mac": "AA:BB:CC:00:00:02",
    },
    {"did": "333", "model": "dreame.vacuum.r2216", "name": "Robot", "mac": None},
]


class FakeDevice:
    """Stands for LaundryCloudDevice."""

    instances: ClassVar[dict[str, FakeDevice]] = {}

    def __init__(self, username, password, country, did) -> None:
        self.did = did
        self.info = {"online": True}
        self.props: dict[str, Any] = {
            "2.1": True,
            "2.2": 1,
            "2.3": 0,
            "2.4": 5,
            "2.5": 0,
            "2.11": 0,
            "4.1": 0,
            "4.2": 12,
        }
        self.on_message = None
        self.writes: list[tuple] = []
        self.mqtt_connected = True
        FakeDevice.instances[did] = self

    def ensure_connected(self, on_message, on_connected=None):
        self.on_message = on_message
        return self.info

    def get_props(self, codes):
        return {
            f"{s}.{p}": self.props[f"{s}.{p}"]
            for s, p in codes
            if f"{s}.{p}" in self.props
        }

    def set_prop(self, siid, piid, value):
        self.writes.append((siid, piid, value))
        self.props[f"{siid}.{piid}"] = value
        return True

    def disconnect(self):
        pass


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def fake_cloud():
    FakeDevice.instances.clear()
    with patch("custom_components.dreame_laundry.LaundryCloudDevice", FakeDevice):
        yield FakeDevice.instances


def _entry(mapping: str = "") -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="me@example.com_eu",
        data={
            CONF_USERNAME: "me@example.com",
            CONF_PASSWORD: "pw",
            CONF_COUNTRY: "eu",
            CONF_DEVICES: [
                {**DEVICES[0], "kind": "washer"},
                {**DEVICES[1], "kind": "dryer"},
            ],
        },
        options={
            CONF_SCAN_INTERVAL: 30,
            CONF_KEEP_AWAKE_INTERVAL: 60,
            CONF_MAPPING: mapping,
        },
    )


async def test_config_flow(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with patch(
        "custom_components.dreame_laundry.config_flow.list_devices",
        side_effect=InvalidAuth,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "me@example.com", CONF_PASSWORD: "bad", CONF_COUNTRY: "eu"},
        )
    assert result["errors"] == {"base": "invalid_auth"}

    with patch(
        "custom_components.dreame_laundry.config_flow.list_devices",
        return_value=[dict(d) for d in DEVICES],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "me@example.com", CONF_PASSWORD: "pw", CONF_COUNTRY: "eu"},
        )
    assert result["step_id"] == "devices"
    # the vacuum is filtered out, both laundry appliances pre-selected
    schema = result["data_schema"].schema
    default = next(iter(schema)).default()
    assert default == ["111", "222"]

    with patch("custom_components.dreame_laundry.LaundryCloudDevice", FakeDevice):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICES: ["111", "222"]}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    kinds = {d["did"]: d["kind"] for d in result["data"][CONF_DEVICES]}
    assert kinds == {"111": "washer", "222": "dryer"}


async def test_entities_push_scan(hass: HomeAssistant, fake_cloud) -> None:
    entry = _entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    states = {s.entity_id: s for s in hass.states.async_all()}
    assert states["sensor.lave_linge_etat"].state == "1"
    assert states["sensor.lave_linge_etat"].attributes["mapping"].startswith("guess")
    assert states["sensor.lave_linge_temps_restant"].state == "0"
    assert states["binary_sensor.lave_linge_cycle_en_cours"].state == "off"
    assert states["switch.lave_linge_maintenir_eveille"].state == "on"
    assert (
        "switch.lave_linge_alimentation" not in states
    )  # power not mapped -> no write
    assert states["binary_sensor.seche_linge_joignable"].state == "on"

    # MQTT push: cycle starts (washer remaining time is 2.11)
    fake_cloud["111"].on_message(
        {
            "method": "properties_changed",
            "params": [
                {"siid": 2, "piid": 11, "value": 87},
                {"siid": 6, "piid": 3, "value": 40},
            ],
        }
    )
    await hass.async_block_till_done()
    assert hass.states.get("sensor.lave_linge_temps_restant").state == "87"
    assert hass.states.get("binary_sensor.lave_linge_cycle_en_cours").state == "on"
    assert hass.states.get("sensor.lave_linge_fin_prevue").state not in (
        "unknown",
        "unavailable",
    )
    # unmapped pushed property becomes a raw diagnostic sensor
    assert hass.states.get("sensor.lave_linge_propriete_6_3").state == "40"

    # Scan
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.lave_linge_scanner_les_proprietes"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("sensor.lave_linge_propriete_4_2").state == "12"
    # the notification lives in its own registry on recent HA versions

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_keep_awake_and_power(hass: HomeAssistant, fake_cloud) -> None:
    mapping = json.dumps(
        {
            "washer": {
                "power": {"prop": "2.1", "on": True},
                "auto_power_off": {"prop": "4.1", "keep_value": 1},
                "status": {
                    "prop": "2.2",
                    "map": {"1": "Veille", "2": "Lavage"},
                    "running_states": [2],
                },
                "energy_cycle": {"prop": "4.2", "scale": 0.01},
            }
        }
    )
    entry = _entry(mapping)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    washer = fake_cloud["111"]
    assert hass.states.get("sensor.lave_linge_etat").state == "Veille"
    assert hass.states.get("sensor.lave_linge_energie_du_cycle").state == "0.12"

    # appliance went to sleep / off -> keep-awake turns it back on and fixes auto-off
    washer.props["2.1"] = False
    coordinator = entry.runtime_data["111"]
    await coordinator._async_keep_awake_tick()
    await hass.async_block_till_done()
    assert (2, 1, True) in washer.writes
    assert (4, 1, 1) in washer.writes

    # turning power off from HA pauses keep-awake
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.lave_linge_alimentation"},
        blocking=True,
    )
    assert (2, 1, False) in washer.writes
    assert hass.states.get("switch.lave_linge_maintenir_eveille").state == "off"
    washer.writes.clear()
    await coordinator._async_keep_awake_tick()
    assert washer.writes == []

    # dryer has no user mapping -> no writable entity
    assert hass.states.get("switch.seche_linge_alimentation") is None


async def test_options_invalid_mapping(hass: HomeAssistant, fake_cloud) -> None:
    entry = _entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_SCAN_INTERVAL: 30,
            CONF_KEEP_AWAKE_INTERVAL: 60,
            CONF_MAPPING: '{"washer": {"bogus": "2.1"}}',
        },
    )
    assert result["errors"] == {CONF_MAPPING: "invalid_mapping"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_SCAN_INTERVAL: 20,
            CONF_KEEP_AWAKE_INTERVAL: 60,
            CONF_MAPPING: '{"washer": {"progress": "2.9"}}',
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert hass.states.get("sensor.lave_linge_progression") is not None


async def test_diagnostics(hass: HomeAssistant, fake_cloud) -> None:
    from custom_components.dreame_laundry.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    entry = _entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["entry"][CONF_PASSWORD] == "**REDACTED**"
    assert diag["devices"][0]["mapping"]["status"] == "2.2"
