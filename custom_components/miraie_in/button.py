"""The MirAIe button platform."""

from __future__ import annotations

from miraie_ac import (
    Device as MirAIeDevice,
    MirAIeHub,
    PresetMode,
)

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .logger import LOGGER


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the MirAIe Button Entities."""
    hub: MirAIeHub = hass.data[DOMAIN][entry.entry_id]

    entities = [MirAIeCoilCleanButton(device) for device in hub.home.devices]

    async_add_entities(entities)


class MirAIeCoilCleanButton(ButtonEntity):
    """Representation of the Coil Clean trigger button entity."""

    def __init__(self, device: MirAIeDevice) -> None:
        self._attr_should_poll = False
        self._attr_has_entity_name = True
        self._attr_translation_key = "start_coil_clean"
        self._attr_unique_id = f"button.{device.name.lower()}_{device.id}_start_coil_clean"
        self.device = device



    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        return "mdi:sparkles"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                (DOMAIN, self.device.id)
            },
            name=self.device.friendly_name,
            manufacturer=self.device.details.brand,
            model=self.device.details.model_number,
            sw_version=self.device.details.firmware_version,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.device.status.is_online

    async def async_press(self) -> None:
        """Press the button."""
        LOGGER.debug("Triggering coil clean cycle")
        await self.device.set_preset_mode(PresetMode.CLEAN)
