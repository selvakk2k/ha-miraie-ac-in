"""Diagnostics logging switch for the MirAIe integration."""

from __future__ import annotations

import logging
from typing import Any

from miraie_ac import Device as MirAIeDevice, MirAIeHub

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .logger import LOGGER, enable_file_logger, disable_file_logger, is_file_logging_enabled

STORAGE_KEY = f"{DOMAIN}.diagnostics"
STORAGE_VERSION = 1

_ACTIVE_SWITCHES: set[MirAIeDiagnosticsSwitch] = set()


async def async_setup_diagnostics_switch(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the diagnostics switch for all devices."""
    hub: MirAIeHub = entry.runtime_data
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)

    entities = [
        MirAIeDiagnosticsSwitch(device, store)
        for device in hub.home.devices
    ]
    async_add_entities(entities)


class MirAIeDiagnosticsSwitch(SwitchEntity):
    """Switch to enable/disable integration-wide file logging."""

    _attr_has_entity_name = True
    _attr_translation_key = "diagnostics_logging"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = False

    def __init__(self, device: MirAIeDevice, store: Store) -> None:
        """Initialize the switch."""
        self.device = device
        self._store = store
        self._attr_unique_id = f"{device.id}_diagnostics_logging"

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend."""
        return "mdi:file-document-outline"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.id)},
            name=self.device.friendly_name,
            manufacturer=self.device.details.brand,
            model=self.device.details.model_number,
            sw_version=self.device.details.firmware_version,
        )

    @property
    def is_on(self) -> bool:
        """Return True if file logging is enabled."""
        return is_file_logging_enabled()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.hass.async_add_executor_job(
            enable_file_logger, self.hass.config.config_dir
        )
        await self._store.async_save({"enabled": True})
        for switch in _ACTIVE_SWITCHES:
            switch.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.hass.async_add_executor_job(disable_file_logger)
        await self._store.async_save({"enabled": False})
        for switch in _ACTIVE_SWITCHES:
            switch.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to HASS."""
        _ACTIVE_SWITCHES.add(self)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity is being removed from HASS."""
        _ACTIVE_SWITCHES.discard(self)
