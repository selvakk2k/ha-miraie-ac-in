"""The MirAIe binary sensor platform."""

from __future__ import annotations

from miraie_ac import (
    Device as MirAIeDevice,
    MirAIeHub,
    PresetMode,
)

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .logger import LOGGER


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the MirAIe Binary Sensors."""
    hub: MirAIeHub = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for device in hub.home.devices:
        entities.append(MirAIeFilterCleanBinarySensor(device))
        entities.append(MirAIeCoilCleanBinarySensor(device))

    async_add_entities(entities)


class MirAIeFilterCleanBinarySensor(BinarySensorEntity):
    """Representation of the Filter Clean alert sensor."""

    def __init__(self, device: MirAIeDevice) -> None:
        self._attr_should_poll: bool = False
        self._attr_has_entity_name = True
        self._attr_translation_key = "filter_clean_alert"
        self._attr_unique_id = f"binary_sensor.{device.name.lower()}_{device.id}_filter_clean_alert"
        self.device = device
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def icon(self) -> str | None:
        return "mdi:air-filter"

    @property
    def is_on(self) -> bool:
        """Return True if filter clean alert is active (dirty filter)."""
        return getattr(self.device.status, "filter_clean_alert", False)

    @property
    def available(self) -> bool:
        return self.device.status.is_online

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

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        LOGGER.debug("Successfully added filter clean alert binary sensor to HA")
        self.device.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        LOGGER.debug("Successfully removed filter clean alert binary sensor from HA")
        self.device.remove_callback(self.async_write_ha_state)


class MirAIeCoilCleanBinarySensor(BinarySensorEntity):
    """Representation of the Coil Clean active sensor."""

    def __init__(self, device: MirAIeDevice) -> None:
        self._attr_should_poll: bool = False
        self._attr_has_entity_name = True
        self._attr_translation_key = "coil_cleaning"
        self._attr_unique_id = f"binary_sensor.{device.name.lower()}_{device.id}_coil_cleaning"
        self.device = device
        self._attr_device_class = BinarySensorDeviceClass.RUNNING

    @property
    def icon(self) -> str | None:
        return "mdi:spray-bottle"

    @property
    def is_on(self) -> bool:
        """Return True if coil clean is running."""
        return self.device.status.preset_mode == PresetMode.CLEAN

    @property
    def available(self) -> bool:
        return self.device.status.is_online

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

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        LOGGER.debug("Successfully added coil cleaning binary sensor to HA")
        self.device.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        LOGGER.debug("Successfully removed coil cleaning binary sensor from HA")
        self.device.remove_callback(self.async_write_ha_state)

