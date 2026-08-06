"""Config flow for mirAIe integration."""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Optional
import aiohttp

from miraie_ac import MirAIeHub
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector

from .const import CONF_INSTALL_DATE, CONF_HALF_DEGREE_PRECISION, DOMAIN
from .utils import six_months_ago, eight_months_ago

_LOGGER = logging.getLogger(__name__)


class InvalidInstallDate(HomeAssistantError):
    """Error to indicate invalid install date."""


def parse_install_date(value: str) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise InvalidInstallDate from exc


def build_user_schema(default_install_date: str) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required("username"): str,
            vol.Required("password"): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
            vol.Optional(CONF_INSTALL_DATE, default=default_install_date): str,
        }
    )


async def validate_input(
    hass: HomeAssistant, data: dict[str, Any]
) -> tuple[dict[str, Any], Optional[date]]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    async with MirAIeHub() as hub:
        # pylint: disable=protected-access
        try:
            await hub._authenticate(data["username"], data["password"])
        except (aiohttp.ClientError, TimeoutError, OSError) as exc:
            raise CannotConnect from exc
        except Exception as exc:
            raise InvalidAuth from exc

    # If you cannot connect:
    # throw CannotConnect
    # If the authentication is wrong:
    # InvalidAuth

    # Return info that you want to store in the config entry.
    install_date = parse_install_date(data.get(CONF_INSTALL_DATE, ""))
    return {"title": "MirAIe"}, install_date


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for mirAIe."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            default_install = six_months_ago(date.today()).isoformat()
            return self.async_show_form(
                step_id="user", data_schema=build_user_schema(default_install)
            )

        errors = {}

        try:
            info, install_date = await validate_input(self.hass, user_input)
            today = date.today()
            min_date = six_months_ago(today)
            oldest_date = eight_months_ago(today)
            if install_date is None:
                install_date = min_date
            if install_date < oldest_date or install_date > today:
                errors[CONF_INSTALL_DATE] = "invalid_install_date"
                raise InvalidInstallDate
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except InvalidInstallDate:
            errors[CONF_INSTALL_DATE] = "invalid_install_date"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(user_input["username"].lower())
            self._abort_if_unique_id_configured()
            options = {CONF_INSTALL_DATE: install_date.isoformat()}
            data = {k: v for k, v in user_input.items() if k != CONF_INSTALL_DATE}
            return self.async_create_entry(title=info["title"], data=data, options=options)

        return self.async_show_form(
            step_id="user",
            data_schema=build_user_schema(user_input.get(CONF_INSTALL_DATE, "")),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return OptionsFlowHandler()


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidInstallDate(HomeAssistantError):
    """Error to indicate invalid installation date."""


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for mirAIe."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: Select which AC units to configure (one, multiple, or all)."""
        if not hasattr(self, "_selected_devices"):
            self._selected_devices = ["__all__"]

        hub: MirAIeHub | None = getattr(self.config_entry, "runtime_data", None)
        devices: list[Any] = hub.home.devices if (hub and getattr(hub, "home", None)) else []

        if user_input is not None:
            self._selected_devices = user_input.get("devices", ["__all__"])
            return await self.async_step_device_settings()

        device_options = [
            selector.SelectOptionDict(value="__all__", label="All AC Units (Global Default)")
        ]
        for dev in devices:
            device_options.append(
                selector.SelectOptionDict(value=dev.id, label=dev.friendly_name)
            )

        schema = vol.Schema(
            {
                vol.Required(
                    "devices", default=self._selected_devices
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=device_options,
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)

    async def async_step_device_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2: Configure precision and history date for the selected unit(s)."""
        today = date.today()
        default_install = six_months_ago(today).isoformat()

        # Determine pre-filled defaults
        current_options = dict(self.config_entry.options)
        devices_opt = current_options.get("devices", {})

        if len(self._selected_devices) == 1 and self._selected_devices[0] != "__all__":
            target_id = self._selected_devices[0]
            target_opt = devices_opt.get(target_id, {})
            current_install = target_opt.get(CONF_INSTALL_DATE, current_options.get(CONF_INSTALL_DATE, default_install))
            current_precision = target_opt.get(
                CONF_HALF_DEGREE_PRECISION, current_options.get(CONF_HALF_DEGREE_PRECISION, False)
            )
        else:
            current_install = current_options.get(CONF_INSTALL_DATE, default_install)
            current_precision = current_options.get(CONF_HALF_DEGREE_PRECISION, False)

        if user_input is None:
            schema = vol.Schema(
                {
                    vol.Optional(CONF_INSTALL_DATE, default=current_install): str,
                    vol.Optional(CONF_HALF_DEGREE_PRECISION, default=current_precision): bool,
                }
            )
            return self.async_show_form(step_id="device_settings", data_schema=schema)

        errors = {}
        try:
            install_date = parse_install_date(user_input.get(CONF_INSTALL_DATE, ""))
            min_date = six_months_ago(today)
            oldest_date = eight_months_ago(today)
            if install_date is None:
                install_date = min_date
            if install_date < oldest_date or install_date > today:
                errors[CONF_INSTALL_DATE] = "invalid_install_date"
                raise InvalidInstallDate
        except InvalidInstallDate:
            errors[CONF_INSTALL_DATE] = "invalid_install_date"
            schema = vol.Schema(
                {
                    vol.Optional(
                        CONF_INSTALL_DATE, default=user_input.get(CONF_INSTALL_DATE, "")
                    ): str,
                    vol.Optional(
                        CONF_HALF_DEGREE_PRECISION,
                        default=user_input.get(CONF_HALF_DEGREE_PRECISION, False),
                    ): bool,
                }
            )
            return self.async_show_form(
                step_id="device_settings", data_schema=schema, errors=errors
            )

        new_options = dict(current_options)
        new_devices = dict(new_options.get("devices", {}))
        half_degree_val = user_input.get(CONF_HALF_DEGREE_PRECISION, False)
        install_date_str = install_date.isoformat()

        if "__all__" in self._selected_devices:
            new_options[CONF_INSTALL_DATE] = install_date_str
            new_options[CONF_HALF_DEGREE_PRECISION] = half_degree_val
            # Clear specific overrides if applying globally to all
            for dev_id in list(new_devices.keys()):
                new_devices.pop(dev_id, None)
        else:
            for dev_id in self._selected_devices:
                new_devices[dev_id] = {
                    CONF_INSTALL_DATE: install_date_str,
                    CONF_HALF_DEGREE_PRECISION: half_degree_val,
                }

        new_options["devices"] = new_devices

        return self.async_create_entry(title="", data=new_options)

