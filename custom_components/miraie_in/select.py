"""The MirAIe select platform."""

from __future__ import annotations

from miraie_ac import (
    Device as MirAIeDevice,
    MirAIeHub,
    ConvertiMode,
)

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    get_converti_preset_modes,
)
from .logger import LOGGER


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the MirAIe Select Entities."""
    hub: MirAIeHub = hass.data[DOMAIN][entry.entry_id]

    entities = [MirAIeConvertiSelect(device) for device in hub.home.devices]

    async_add_entities(entities)


class MirAIeConvertiSelect(SelectEntity):
    """Representation of the Convertible Mode select entity."""

    def __init__(self, device: MirAIeDevice) -> None:
        self._attr_should_poll = False
        self._attr_has_entity_name = True
        self._attr_unique_id = f"select.{device.name.lower()}_{device.id}_convertible_mode"
        self.device = device
        self._attr_translation_key = "convertible_mode"
        self._attr_entity_category = EntityCategory.CONFIG

        model_number = getattr(getattr(device, "details", None), "model_number", None)
        self._attr_options = get_converti_preset_modes(model_number)

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
    def current_option(self) -> str | None:
        """Return the selected option."""
        status = getattr(self.device, "status", None)
        if not status:
            return "cv 0"
        mode = getattr(status, "converti_mode", ConvertiMode.OFF)
        if mode == ConvertiMode.NS:
            return "cv 0"
        return f"cv {mode.value}"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.device.status.is_online

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        try:
            val = int(option.split(" ")[1])
        except (ValueError, IndexError) as err:
            LOGGER.error(f"Invalid option selected: {option} - {err}")
            return

        LOGGER.debug(f"Setting convertible mode to {val} ({option})")
        await self.device.set_converti_mode(ConvertiMode(val))

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        LOGGER.debug("Successfully added convertible mode select to HA")
        self.device.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        LOGGER.debug("Successfully removed convertible mode select from HA")
        self.device.remove_callback(self.async_write_ha_state)
