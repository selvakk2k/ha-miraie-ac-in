"""The MirAIe climate platform."""

from __future__ import annotations

from miraie_ac import (
    Device as MirAIeDevice,
    MirAIeHub,
    DisplayMode,
)

from homeassistant.components.switch import (
    SwitchEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    supports_nanoe,
)

from .logger import LOGGER
from .utils import get_devices_for_entry

PARALLEL_UPDATES = 0



async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:

    """Set up the MirAIe Climate Hub."""
    hub: MirAIeHub = entry.runtime_data
    coordinators = getattr(hub, "coordinators", {})
    ent_reg = er.async_get(hass)

    entities = []
    devices = get_devices_for_entry(hub, entry)


    for device in devices:
        entities.append(MirAIeDisplaySwitch(device))
        
        # Untested: Expose Nanoe switch only if the model supports it
        model_number = getattr(getattr(device, "details", None), "model_number", None)
        if supports_nanoe(model_number):
            entities.append(MirAIeNanoeSwitch(device))

        coordinator = coordinators.get(device.id)
        if coordinator:
            entry_data = getattr(entry, "data", entry) if isinstance(getattr(entry, "data", entry), dict) else {}
            is_ir_only = entry_data.get("is_ir_only", False) or not coordinator.has_wifi
            if not is_ir_only and coordinator.blaster_entity_id:
                entities.append(MirAIeHybridSubmodeSwitch(device, coordinator))
                entities.append(MirAIeBackendSelectSwitch(device, coordinator))
            else:
                for suffix in ("_hybrid_submode", "_active_backend"):
                    unq_id = f"{device.id}{suffix}"
                    entity_id = ent_reg.async_get_entity_id("switch", DOMAIN, unq_id)
                    if entity_id:
                        ent_reg.async_remove(entity_id)
                        LOGGER.info("Cleaned up orphaned entity %s after IR blaster removal", entity_id)

    async_add_entities(entities)



class MirAIeDisplaySwitch(SwitchEntity):
    """Representation of a MirAIe Climate."""

    def __init__(self, device: MirAIeDevice) -> None:
        self._attr_should_poll: bool = False
        self._attr_has_entity_name = True
        self._attr_translation_key = "display"
        self._attr_unique_id = f"{device.id}_display"
        self.device = device

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        return "mdi:eye-outline" if self.is_on else "mdi:eye-off-outline"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.device.id)
            },
            name=self.device.friendly_name,
            manufacturer=self.device.details.brand,
            model=self.device.details.model_number,
            sw_version=self.device.details.firmware_version,
        )

    @property
    def is_on(self) -> bool:
        """Return True if display is on."""
        return self.device.status.display_mode == DisplayMode.ON

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.device.status.is_online

    async def async_turn_off(self) -> None:
        await self.device.set_display_mode(DisplayMode.OFF)

    async def async_turn_on(self) -> None:
        await self.device.set_display_mode(DisplayMode.ON)

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        LOGGER.debug("Successfully added display switch to HA")
        self._device_callback = lambda *args, **kwargs: self.async_write_ha_state()
        self.device.register_callback(self._device_callback)

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        LOGGER.debug("Successfully removed display switch from HA")
        if hasattr(self, "_device_callback"):
            self.device.remove_callback(self._device_callback)


class MirAIeNanoeSwitch(SwitchEntity):
    """Representation of a MirAIe Nanoe Air Purification switch.
    
    WARNING: Untested feature, added based on protocol structure but lacking a
    physical Nanoe-compatible device to verify active MQTT control.
    """

    def __init__(self, device: MirAIeDevice) -> None:
        self._attr_should_poll: bool = False
        self._attr_has_entity_name = True
        self._attr_translation_key = "nanoe"
        self._attr_unique_id = f"{device.id}_nanoe"
        self.device = device

    @property
    def icon(self) -> str | None:
        return "mdi:air-filter"

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
    def is_on(self) -> bool:
        """Return True if Nanoe is on."""
        return getattr(self.device.status, "nanoe_mode", "off") == "on"

    @property
    def available(self) -> bool:
        return self.device.status.is_online

    async def async_turn_off(self) -> None:
        await self.device.set_nanoe(False)

    async def async_turn_on(self) -> None:
        await self.device.set_nanoe(True)

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        LOGGER.debug("Successfully added Nanoe switch to HA")
        self._device_callback = lambda *args, **kwargs: self.async_write_ha_state()
        self.device.register_callback(self._device_callback)

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        LOGGER.debug("Successfully removed Nanoe switch from HA")
        if hasattr(self, "_device_callback"):
            self.device.remove_callback(self._device_callback)



from homeassistant.helpers.restore_state import RestoreEntity
from .const import (
    CONF_PRIMARY_BACKEND,
    CONF_HYBRID_SUBMODE,
)


class MirAIeHybridSubmodeSwitch(SwitchEntity, RestoreEntity):
    """Switch toggling between Hybrid Automatic and Manual control mode."""

    def __init__(self, device: MirAIeDevice, coordinator) -> None:
        self._attr_should_poll: bool = False
        self._attr_has_entity_name = True
        self._attr_name = "Hybrid Automatic Control"
        self._attr_unique_id = f"{device.id}_hybrid_submode"
        self.device = device
        self.coordinator = coordinator

    @property
    def icon(self) -> str:
        return "mdi:auto-fix" if self.is_on else "mdi:hand-back-right"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.id)},
            name=self.device.friendly_name,
            manufacturer=self.device.details.brand,
            model=self.device.details.model_number,
        )

    @property
    def is_on(self) -> bool:
        return self.coordinator.hybrid_submode == "auto"

    def _persist_option(self, option_key: str, option_val: str) -> None:
        entry = self.coordinator.hass.config_entries.async_get_entry(self.coordinator.entry_id)
        if not entry:
            return
        options = dict(entry.options)
        devices_opt = dict(options.get("devices", {}))
        dev_opt = dict(devices_opt.get(self.coordinator.device_id, {}))
        dev_opt[option_key] = option_val
        devices_opt[self.coordinator.device_id] = dev_opt
        options["devices"] = devices_opt
        self.coordinator.hass.config_entries.async_update_entry(entry, options=options)

    async def async_turn_on(self) -> None:
        self.coordinator.hybrid_submode = "auto"
        self._persist_option(CONF_HYBRID_SUBMODE, "auto")
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        self.coordinator.hybrid_submode = "manual"
        self._persist_option(CONF_HYBRID_SUBMODE, "manual")
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Restore state and subscribe to coordinator state updates."""
        await super().async_added_to_hass()
        if hasattr(self, "coordinator") and self.coordinator:
            self.async_on_remove(
                self.coordinator.async_add_listener(self.async_write_ha_state)
            )
        # Ensure switch state reflects current coordinator hybrid_submode
        self.async_write_ha_state()


class MirAIeBackendSelectSwitch(SwitchEntity, RestoreEntity):
    """Switch toggling active primary backend transport (Cloud vs IR)."""

    def __init__(self, device: MirAIeDevice, coordinator) -> None:
        self._attr_should_poll: bool = False
        self._attr_has_entity_name = True
        self._attr_name = "Primary Transport Backend"
        self._attr_unique_id = f"{device.id}_active_backend"
        self.device = device
        self.coordinator = coordinator

    @property
    def icon(self) -> str:
        return "mdi:cloud-sync" if self.is_on else "mdi:remote"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.id)},
            name=self.device.friendly_name,
            manufacturer=self.device.details.brand,
            model=self.device.details.model_number,
        )

    @property
    def is_on(self) -> bool:
        return self.coordinator.primary_backend == "cloud"

    def _persist_option(self, option_key: str, option_val: str) -> None:
        entry = self.coordinator.hass.config_entries.async_get_entry(self.coordinator.entry_id)
        if not entry:
            return
        options = dict(entry.options)
        devices_opt = dict(options.get("devices", {}))
        dev_opt = dict(devices_opt.get(self.coordinator.device_id, {}))
        dev_opt[option_key] = option_val
        devices_opt[self.coordinator.device_id] = dev_opt
        options["devices"] = devices_opt
        self.coordinator.hass.config_entries.async_update_entry(entry, options=options)

    async def async_turn_on(self) -> None:
        if self.coordinator.hybrid_submode == "auto":
            self.coordinator.hybrid_submode = "manual"
            self._persist_option(CONF_HYBRID_SUBMODE, "manual")
            LOGGER.info("External touch on backend switch: Flipped hybrid mode to Manual for %s", self.device.id)
        self.coordinator.primary_backend = "cloud"
        self._persist_option(CONF_PRIMARY_BACKEND, "cloud")
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        if self.coordinator.hybrid_submode == "auto":
            self.coordinator.hybrid_submode = "manual"
            self._persist_option(CONF_HYBRID_SUBMODE, "manual")
            LOGGER.info("External touch on backend switch: Flipped hybrid mode to Manual for %s", self.device.id)
        self.coordinator.primary_backend = "ir"
        self._persist_option(CONF_PRIMARY_BACKEND, "ir")
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Restore state and subscribe to coordinator state updates."""
        await super().async_added_to_hass()
        if hasattr(self, "coordinator") and self.coordinator:
            self.async_on_remove(
                self.coordinator.async_add_listener(self.async_write_ha_state)
            )
        # Ensure switch state reflects current coordinator primary_backend
        self.async_write_ha_state()


