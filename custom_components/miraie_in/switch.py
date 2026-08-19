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
        coordinator = coordinators.get(device.id)
        entities.append(MirAIeDisplaySwitch(device, coordinator))
        
        # Untested: Expose Nanoe switch only if the model supports it
        model_number = getattr(getattr(device, "details", None), "model_number", None)
        if supports_nanoe(model_number):
            entities.append(MirAIeNanoeSwitch(device, coordinator))

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
    """Representation of a MirAIe Display LED switch."""

    def __init__(self, device: MirAIeDevice, coordinator=None) -> None:
        self._attr_should_poll: bool = False
        self._attr_has_entity_name = True
        self._attr_translation_key = "display"
        self._attr_unique_id = f"{device.id}_display"
        self.device = device
        self.coordinator = coordinator

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
        if self.coordinator and "display" in self.coordinator.state:
            return self.coordinator.state.get("display") == "on"
        return self.device.status.display_mode == DisplayMode.ON

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if self.coordinator:
            if not self.coordinator.has_wifi or getattr(self.coordinator, "primary_backend", "cloud") == "ir" or getattr(self.coordinator, "blaster_entity_id", None):
                return True
        return self.device.status.is_online

    async def _send_display_command(self, turn_on: bool) -> None:
        target_mode = DisplayMode.ON if turn_on else DisplayMode.OFF
        coord = self.coordinator
        hub = getattr(coord, "hub", None) if coord else None
        broker = getattr(hub, "broker", None) if hub else None
        broker_connected = broker.connected.is_set() if (broker and hasattr(broker, "connected")) else True
        is_cloud_offline = (not getattr(getattr(self.device, "status", None), "is_online", True)) or (not broker_connected)
        use_ir_first = (
            coord and (
                getattr(coord, "primary_backend", "cloud") == "ir"
                or (is_cloud_offline and getattr(coord, "hybrid_submode", "auto") == "auto" and getattr(coord, "blaster_entity_id", None))
            )
        )

        if coord:
            coord.async_optimistic_update(
                display=turn_on,
                origin="IR" if use_ir_first else "Cloud",
            )
            if hasattr(self, "async_write_ha_state"):
                try:
                    self.async_write_ha_state()
                except Exception:
                    pass

        if use_ir_first:
            success = await coord.async_dispatch_ir_command(
                mode="display",
                origin="IR" if getattr(coord, "primary_backend", "cloud") == "ir" else "IR Failover (Offline)",
            )
            if success:
                return
            LOGGER.warning("IR display command failed for %s, falling back to Cloud", self.device.id)

        try:
            await self.device.set_display_mode(target_mode)
        except Exception as err:
            LOGGER.warning("Cloud display command failed for %s: %s", self.device.id, err)
            if coord and getattr(coord, "hybrid_submode", "auto") == "auto" and getattr(coord, "blaster_entity_id", None):
                LOGGER.info("Auto Failover triggered: Transmitting IR display command for %s", self.device.id)
                await coord.async_dispatch_ir_command(mode="display", origin="IR Failover")

    async def async_turn_off(self) -> None:
        await self._send_display_command(False)

    async def async_turn_on(self) -> None:
        await self._send_display_command(True)

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        LOGGER.debug("Successfully added display switch to HA")
        if self.coordinator:
            self.async_on_remove(
                self.coordinator.async_add_listener(self.async_write_ha_state)
            )
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

    def __init__(self, device: MirAIeDevice, coordinator=None) -> None:
        self._attr_should_poll: bool = False
        self._attr_has_entity_name = True
        self._attr_translation_key = "nanoe"
        self._attr_unique_id = f"{device.id}_nanoe"
        self.device = device
        self.coordinator = coordinator

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
        if self.coordinator and "nanoe" in self.coordinator.state:
            return bool(self.coordinator.state.get("nanoe"))
        return getattr(self.device.status, "nanoe_mode", "off") == "on"

    @property
    def available(self) -> bool:
        if self.coordinator:
            if not self.coordinator.has_wifi or getattr(self.coordinator, "primary_backend", "cloud") == "ir" or getattr(self.coordinator, "blaster_entity_id", None):
                return True
        return self.device.status.is_online

    async def _send_nanoe_command(self, turn_on: bool) -> None:
        coord = self.coordinator
        hub = getattr(coord, "hub", None) if coord else None
        broker = getattr(hub, "broker", None) if hub else None
        broker_connected = broker.connected.is_set() if (broker and hasattr(broker, "connected")) else True
        is_cloud_offline = (not getattr(getattr(self.device, "status", None), "is_online", True)) or (not broker_connected)
        use_ir_first = (
            coord and (
                getattr(coord, "primary_backend", "cloud") == "ir"
                or (is_cloud_offline and getattr(coord, "hybrid_submode", "auto") == "auto" and getattr(coord, "blaster_entity_id", None))
            )
        )

        if coord:
            coord.async_optimistic_update(
                nanoe=turn_on,
                origin="IR" if use_ir_first else "Cloud",
            )
            if hasattr(self, "async_write_ha_state"):
                try:
                    self.async_write_ha_state()
                except Exception:
                    pass

        if use_ir_first:
            success = await coord.async_dispatch_ir_command(
                nanoe=turn_on,
                origin="IR" if getattr(coord, "primary_backend", "cloud") == "ir" else "IR Failover (Offline)",
            )
            if success:
                return
            LOGGER.warning("IR nanoe command failed for %s, falling back to Cloud", self.device.id)

        try:
            await self.device.set_nanoe(turn_on)
        except Exception as err:
            LOGGER.warning("Cloud nanoe command failed for %s: %s", self.device.id, err)
            if coord and getattr(coord, "hybrid_submode", "auto") == "auto" and getattr(coord, "blaster_entity_id", None):
                LOGGER.info("Auto Failover triggered: Transmitting IR nanoe command for %s", self.device.id)
                await coord.async_dispatch_ir_command(nanoe=turn_on, origin="IR Failover")

    async def async_turn_off(self) -> None:
        await self._send_nanoe_command(False)

    async def async_turn_on(self) -> None:
        await self._send_nanoe_command(True)

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        LOGGER.debug("Successfully added Nanoe switch to HA")
        if self.coordinator:
            self.async_on_remove(
                self.coordinator.async_add_listener(self.async_write_ha_state)
            )
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
        self.coordinator._suppress_reload = True
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
        self.coordinator._suppress_reload = True
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
