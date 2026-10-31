"""Config and options flow."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import CannotConnect, InvalidAuth, list_devices
from .const import (
    CONF_COUNTRY,
    CONF_DEVICES,
    CONF_KEEP_AWAKE_INTERVAL,
    CONF_MAPPING,
    CONF_SCAN_INTERVAL,
    COUNTRIES,
    DEFAULT_COUNTRY,
    DEFAULT_KEEP_AWAKE_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .models import guess_kind, is_laundry, validate_overrides

_LOGGER = logging.getLogger(__name__)


def _credentials_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")
            ): TextSelector(
                TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username")
            ),
            vol.Required(CONF_PASSWORD): TextSelector(
                TextSelectorConfig(
                    type=TextSelectorType.PASSWORD, autocomplete="current-password"
                )
            ),
            vol.Required(
                CONF_COUNTRY, default=defaults.get(CONF_COUNTRY, DEFAULT_COUNTRY)
            ): SelectSelector(
                SelectSelectorConfig(
                    options=COUNTRIES,
                    translation_key="country",
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )


class DreameLaundryConfigFlow(ConfigFlow, domain=DOMAIN):
    """Dreamehome account -> pick the washer / dryer."""

    VERSION = 1

    def __init__(self) -> None:
        self._credentials: dict[str, Any] = {}
        self._devices: list[dict[str, Any]] = []

    async def _try_login(
        self, user_input: dict[str, Any]
    ) -> tuple[list[dict[str, Any]] | None, str | None]:
        try:
            devices = await self.hass.async_add_executor_job(
                list_devices,
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                user_input[CONF_COUNTRY],
            )
        except InvalidAuth:
            return None, "invalid_auth"
        except CannotConnect:
            return None, "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error while logging in to Dreamehome")
            return None, "unknown"
        return devices, None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            devices, error = await self._try_login(user_input)
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(
                    f"{user_input[CONF_USERNAME].lower()}_{user_input[CONF_COUNTRY]}"
                )
                self._abort_if_unique_id_configured()
                devices = [
                    d
                    for d in devices or []
                    if ".vacuum." not in d["model"] and ".mower." not in d["model"]
                ]
                if not devices:
                    return self.async_abort(reason="no_devices")
                self._credentials = user_input
                self._devices = devices
                return await self.async_step_devices()
        return self.async_show_form(
            step_id="user",
            data_schema=_credentials_schema(user_input or {}),
            errors=errors,
        )

    async def async_step_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            selected = [
                d for d in self._devices if d["did"] in user_input[CONF_DEVICES]
            ]
            if not selected:
                errors["base"] = "no_selection"
            else:
                for dev in selected:
                    dev["kind"] = guess_kind(dev["model"])
                return self.async_create_entry(
                    title=f"Dreame ({self._credentials[CONF_USERNAME]})",
                    data={**self._credentials, CONF_DEVICES: selected},
                    options={
                        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                        CONF_KEEP_AWAKE_INTERVAL: DEFAULT_KEEP_AWAKE_INTERVAL,
                        CONF_MAPPING: "",
                    },
                )
        options = [
            SelectOptionDict(value=d["did"], label=f"{d['name']} ({d['model']})")
            for d in self._devices
        ]
        default = [d["did"] for d in self._devices if is_laundry(d["model"])] or [
            d["did"] for d in self._devices
        ]
        return self.async_show_form(
            step_id="devices",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICES, default=default): SelectSelector(
                        SelectSelectorConfig(
                            options=options, multiple=True, mode=SelectSelectorMode.LIST
                        )
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]}
            _, error = await self._try_login(data)
            if error:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(entry, data=data)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    )
                }
            ),
            description_placeholders={"username": entry.data[CONF_USERNAME]},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return DreameLaundryOptionsFlow()


class DreameLaundryOptionsFlow(OptionsFlow):
    """Polling, keep-awake period and property mapping."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        placeholders = {"error": ""}
        current = dict(self.config_entry.options)
        if user_input is not None:
            text = (user_input.get(CONF_MAPPING) or "").strip()
            try:
                validate_overrides(json.loads(text) if text else {})
            except (
                ValueError
            ) as err:  # JSONDecodeError and MappingError are ValueErrors
                errors[CONF_MAPPING] = "invalid_mapping"
                placeholders["error"] = str(err)
            else:
                return self.async_create_entry(
                    data={
                        CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                        CONF_KEEP_AWAKE_INTERVAL: int(
                            user_input[CONF_KEEP_AWAKE_INTERVAL]
                        ),
                        CONF_MAPPING: text,
                    }
                )
            current.update(user_input)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=10,
                        max=600,
                        step=5,
                        unit_of_measurement="s",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_KEEP_AWAKE_INTERVAL,
                    default=current.get(
                        CONF_KEEP_AWAKE_INTERVAL, DEFAULT_KEEP_AWAKE_INTERVAL
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=30,
                        max=900,
                        step=10,
                        unit_of_measurement="s",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    CONF_MAPPING, default=current.get(CONF_MAPPING, "")
                ): TextSelector(TextSelectorConfig(multiline=True)),
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
            description_placeholders=placeholders,
        )
