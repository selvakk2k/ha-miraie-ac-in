"""Push-Based Two-Axis State Coordinator for Panasonic MirAIe AC Integration (2.0 Hybrid Release)."""
from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import Any, Callable, Dict, Optional

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval, async_track_time_change
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .logger import LOGGER
try:
    from panasonic_ac_models import ACModelLookup, generate_ir_code  # type: ignore[import-not-found, import-untyped]
except ImportError:
    from .panasonic_ac_models import ACModelLookup, generate_ir_code


class MirAIeDeviceCoordinator:
    """State Coordinator managing push-based state for a single Panasonic AC device."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str = "",
        device_id: str = "",
        model_code: str = "",
        has_wifi: bool = True,
        control_mode: str = "cloud",  # "cloud", "ir", "hybrid"
        primary_backend: str = "cloud",  # "cloud" or "ir"
        hybrid_submode: str = "auto",  # "auto" or "manual"
        blaster_entity_id: Optional[str] = None,
        ir_format: str = "auto",
        lookup=None,
        subentry_id: Optional[str] = None,  # Backward-compatible alias
    ):
        self.hass = hass
        resolved_entry_id = entry_id or subentry_id or ""
        self.entry_id = resolved_entry_id
        self.subentry_id = resolved_entry_id  # Kept as alias
        self.device_id = device_id
        self.model_code = model_code
        self.has_wifi = has_wifi
        self.control_mode = control_mode
        self.primary_backend = primary_backend
        self.hybrid_submode = hybrid_submode
        self.blaster_entity_id = blaster_entity_id
        self.ir_format = ir_format
        self.hub: Any = None

        # Resolve hardware capabilities
        self.lookup = lookup if lookup is not None else ACModelLookup()
        self.capabilities = self.lookup.get_capabilities(model_code)

        # State storage
        self.state: Dict[str, Any] = {
            "power": "off",
            "mode": "cool",
            "active_preset": "none",
            "temperature": 24,
            "fan_speed": "low",
            "v_vane": "V1",
            "h_vane": "H0",
            "eco": False,
            "nanoe": False,
            "display": "on",
            "last_controlled_by": "Cloud",
            "provisional": False,
        }

        # Operational diagnostics
        self.cloud_mqtt_connected = False
        self.device_online = False
        self.ir_blaster_available = False
        self._working_ir_format: Optional[str] = ir_format

        self._last_ir_command_timestamp: float = 0.0
        self._listeners: list[Callable[[], None]] = []

    @callback
    def async_add_listener(self, update_callback: Callable[[], None]) -> Callable[[], None]:
        """Listen for coordinator state updates."""
        self._listeners.append(update_callback)

        def _remove_listener():
            if update_callback in self._listeners:
                self._listeners.remove(update_callback)

        return _remove_listener

    @callback
    def _notify_listeners(self) -> None:
        """Notify all entities of a state update."""
        for update_callback in self._listeners:
            update_callback()

    async def async_handle_cloud_update(self, cloud_data: Dict[str, Any]) -> None:
        """Process incoming Cloud MQTT state payload.

        Cloud telemetry serves as confirmation. Incoming cloud updates within the
        IR command grace window do not overwrite optimistic IR temperature or origin.
        """
        LOGGER.debug("Device %s: Cloud state update received: %s", self.device_id, cloud_data)

        try:
            loop = getattr(self.hass, "loop", None) or asyncio.get_running_loop()
            now = loop.time()
            if not isinstance(now, (int, float)):
                now = 0.0
        except Exception:
            now = 0.0
        last_ir_ts = getattr(self, "_last_ir_command_timestamp", 0.0)
        in_ir_grace_window = (last_ir_ts > 0.0) and ((now - last_ir_ts) < 8.0)

        # Map cloud payload keys
        if "pwr" in cloud_data:
            new_power = "on" if str(cloud_data["pwr"]).lower() in ["on", "1", "true"] else "off"
            if not in_ir_grace_window or new_power == self.state.get("power"):
                self.state["power"] = new_power
        if "acdc" in cloud_data:
            new_disp = "on" if str(cloud_data["acdc"]).lower() in ["on", "1", "true"] else "off"
            if not in_ir_grace_window or new_disp == self.state.get("display"):
                self.state["display"] = new_disp
        if "md" in cloud_data:
            md_val = str(cloud_data["md"]).lower()
            if md_val not in ("powerful", "boost", "clean") and not md_val.startswith("converti_"):
                self.state["mode"] = md_val

        conv_val = cloud_data.get("converti")
        preset_val = str(cloud_data.get("preset", "")).lower()

        if conv_val and int(conv_val) > 0:
            self.state["converti"] = f"cv_{conv_val}"
            self.state["active_preset"] = f"cv_{conv_val}"
        elif preset_val in ("boost", "powerful"):
            self.state["active_preset"] = "powerful"
        elif preset_val == "clean":
            self.state["active_preset"] = "clean"
        elif preset_val == "eco":
            self.state["active_preset"] = "eco"
        else:
            if not in_ir_grace_window:
                if self.primary_backend != "ir" or not self.state.get("provisional"):
                    self.state["active_preset"] = "none"
                    self.state["converti"] = "cv_off"

        if "tset" in cloud_data:
            try:
                cloud_temp = int(float(cloud_data["tset"]))
                if not in_ir_grace_window or cloud_temp == self.state.get("temperature"):
                    self.state["temperature"] = cloud_temp
            except (ValueError, TypeError):
                pass

        if "acfs" in cloud_data:
            if not in_ir_grace_window or str(cloud_data["acfs"]).lower() == self.state.get("fan_speed"):
                self.state["fan_speed"] = str(cloud_data["acfs"]).lower()
        if "acvs" in cloud_data:
            if not in_ir_grace_window or str(cloud_data["acvs"]).upper() == self.state.get("v_vane"):
                self.state["v_vane"] = str(cloud_data["acvs"]).upper()
        if "achs" in cloud_data:
            if not in_ir_grace_window or str(cloud_data["achs"]).upper() == self.state.get("h_vane"):
                self.state["h_vane"] = str(cloud_data["achs"]).upper()
        if "acec" in cloud_data:
            self.state["eco"] = str(cloud_data["acec"]).lower() in ["on", "1", "true"]
        if "acngs" in cloud_data:
            self.state["nanoe"] = str(cloud_data["acngs"]).lower() in ["on", "1", "true"]

        # Origin tracking: preserve "IR" origin during active IR control
        if not in_ir_grace_window and self.state.get("last_controlled_by") != "IR":
            self.state["last_controlled_by"] = "Cloud"

        self.state["provisional"] = False
        self.device_online = True

        self._notify_listeners()

    async def async_dispatch_ir_command(
        self,
        mode: Optional[str] = None,
        target_temp: Optional[int] = None,
        fan: Optional[str] = None,
        v_vane: Optional[str] = None,
        h_vane: Optional[str] = None,
        eco: Optional[bool] = None,
        nanoe: Optional[bool] = None,
        display: Optional[bool] = None,
        origin: str = "IR",
    ) -> bool:
        """Generate and transmit IR payload via configured blaster entity.

        RULE: IR writes are optimistic — updates coordinator state immediately.
        """
        if not self.blaster_entity_id:
            LOGGER.error("Device %s: Cannot dispatch IR command — no blaster entity configured", self.device_id)
            return False

        # Apply parameters or use current coordinator state
        cmd_mode = mode or self.state["mode"]
        cmd_temp = target_temp if target_temp is not None else self.state["temperature"]
        cmd_fan = fan or self.state["fan_speed"]
        cmd_v = v_vane or self.state["v_vane"]
        cmd_h = h_vane or self.state["h_vane"]
        cmd_eco = eco if eco is not None else self.state["eco"]
        cmd_nanoe = nanoe if nanoe is not None else self.state["nanoe"]

        # Generate IR payload using panasonic-ac-models
        series_code = self.capabilities.get("series", "EU")
        ir_data = generate_ir_code(
            mode=cmd_mode,
            target_temp=cmd_temp,
            fan=cmd_fan,
            v_vane=cmd_v,
            h_vane=cmd_h,
            eco=cmd_eco,
            nanoe=cmd_nanoe,
            series=series_code,
        )

        LOGGER.info(
            "Device %s: Transmitting IR command via %s -> %s",
            self.device_id,
            self.blaster_entity_id,
            ir_data["description"],
        )

        # Optimistically update coordinator state IMMEDIATELY for zero-lag UI response
        try:
            loop = getattr(self.hass, "loop", None) or asyncio.get_running_loop()
            self._last_ir_command_timestamp = loop.time()
        except Exception:
            self._last_ir_command_timestamp = 0.0

        if cmd_mode == "display":
            self.async_optimistic_update(
                display=display if display is not None else (self.state.get("display") != "on"),
                origin=origin,
            )
        else:
            self.async_optimistic_update(
                mode=cmd_mode,
                target_temp=cmd_temp,
                fan=cmd_fan,
                v_vane=cmd_v,
                h_vane=cmd_h,
                eco=cmd_eco,
                nanoe=cmd_nanoe,
                origin=origin,
            )

        # Determine target domain & service call based on blaster_entity_id
        target_domain = self.blaster_entity_id.split(".")[0]
        success = False

        if target_domain == "infrared":
            # Native Home Assistant Infrared platform helper check
            if getattr(self, "_native_ir_helper_available", True):
                try:
                    from homeassistant.components.infrared.helpers import async_send_command
                    try:
                        from infrared_protocols.commands import Command as BaseCommand  # type: ignore[import-not-found, import-untyped]
                    except ImportError:
                        class BaseCommand:  # type: ignore[no-redef]
                            def __init__(self, modulation=38000):
                                self.modulation = modulation

                    class MirAIeRawIRCommand(BaseCommand):  # type: ignore[misc, valid-type]
                        def __init__(self, raw_timings: list[int], modulation: int = 38000) -> None:
                            if hasattr(super(), "__init__"):
                                try:
                                    super().__init__(modulation=modulation)
                                except TypeError:
                                    self.modulation = modulation
                            else:
                                self.modulation = modulation
                            self._raw_timings = list(raw_timings)

                        def get_raw_timings(self) -> list[int]:
                            return self._raw_timings

                    cmd_obj = MirAIeRawIRCommand(ir_data["raw"])
                    LOGGER.info("Device %s: Transmitting native IR command via %s", self.device_id, self.blaster_entity_id)
                    await async_send_command(self.hass, self.blaster_entity_id, cmd_obj)
                    return True
                except Exception as err:
                    LOGGER.error("Native infrared transmission failed for %s: %s", self.device_id, err)
                    return False

            return False




        elif target_domain == "esphome":
            # ESPHome transmit_raw service
            device_name = self.blaster_entity_id.replace("esphome.", "").strip()
            service_name = f"{device_name}_transmit_raw" if not device_name.endswith("_transmit_raw") else device_name
            # ESPHome transmit_raw expects marks as positive, spaces as negative
            raw_timings = list(ir_data["raw"])
            try:
                LOGGER.info("Device %s: Transmitting IR via esphome.%s", self.device_id, service_name)
                await self.hass.services.async_call(
                    "esphome",
                    service_name,
                    {"command": raw_timings},
                    blocking=False,
                )
                success = True
            except Exception as err:
                LOGGER.error("Device %s: ESPHome IR transmission failed: %s", self.device_id, err)

        elif target_domain == "mqtt":
            # MQTT / Tasmota transmitter topic
            try:
                LOGGER.info("Device %s: Transmitting IR via mqtt.publish -> %s", self.device_id, self.blaster_entity_id)
                await self.hass.services.async_call(
                    "mqtt",
                    "publish",
                    {"topic": self.blaster_entity_id, "payload": ir_data["tasmota_json"]},
                    blocking=False,
                )
                success = True
            except Exception as err:
                LOGGER.error("Device %s: MQTT IR transmission failed: %s", self.device_id, err)

        elif target_domain == "remote":
            if self._working_ir_format:
                format_map = {
                    "Broadlink b64:": [f"b64:{ir_data['broadlink_b64']}"],
                    "Broadlink raw b64:": [ir_data["broadlink_b64"]],
                    "Tuya b64:": [ir_data["tuya_b64"]],
                    "Raw pulse array:": [ir_data["raw"]],
                    "Raw positive pulse array:": [[abs(p) for p in ir_data["raw"]]],
                }
                cmd_payload = format_map.get(self._working_ir_format, [f"b64:{ir_data['broadlink_b64']}"])
                try:
                    LOGGER.info("Device %s: Transmitting IR payload (%s) via remote.send_command -> %s", self.device_id, self._working_ir_format, self.blaster_entity_id)
                    await self.hass.services.async_call(
                        "remote",
                        "send_command",
                        {"entity_id": self.blaster_entity_id, "command": cmd_payload},
                        blocking=False,
                    )
                    return True
                except Exception as err:
                    LOGGER.warning("Cached IR format %s failed for %s: %s, re-detecting format", self._working_ir_format, self.device_id, err)
                    self._working_ir_format = None

            # First time format detection — test candidates synchronously (blocking=True) to find the valid format
            transmission_attempts = [
                ("Broadlink b64:", [f"b64:{ir_data['broadlink_b64']}"]),
                ("Broadlink raw b64:", [ir_data["broadlink_b64"]]),
                ("Tuya b64:", [ir_data["tuya_b64"]]),
                ("Raw pulse array:", [ir_data["raw"]]),
                ("Raw positive pulse array:", [[abs(p) for p in ir_data["raw"]]]),
            ]

            for label, cmd_payload in transmission_attempts:
                try:
                    LOGGER.info("Device %s: Testing IR payload format (%s) via remote.send_command -> %s", self.device_id, label, self.blaster_entity_id)
                    await self.hass.services.async_call(
                        "remote",
                        "send_command",
                        {"entity_id": self.blaster_entity_id, "command": cmd_payload},
                        blocking=True,
                    )
                    self._working_ir_format = label
                    LOGGER.info("Device %s: Locked in working IR format: %s", self.device_id, label)
                    return True
                except Exception as err:
                    LOGGER.debug("IR payload format (%s) rejected: %s", label, err)

            LOGGER.error("Device %s: All IR transmission attempts failed for blaster entity %s", self.device_id, self.blaster_entity_id)
            return False

        return success

    @callback
    def async_optimistic_update(
        self,
        mode: Optional[str] = None,
        target_temp: Optional[int] = None,
        fan: Optional[str] = None,
        v_vane: Optional[str] = None,
        h_vane: Optional[str] = None,
        eco: Optional[bool] = None,
        nanoe: Optional[bool] = None,
        display: Optional[bool] = None,
        origin: str = "Cloud",
    ) -> None:
        """Optimistically update coordinator state for instant UI response."""
        if mode is not None:
            if mode == "display":
                pass
            elif mode in ("powerful", "boost"):
                self.state["power"] = "on"
                self.state["active_preset"] = "powerful"
                self.state["eco"] = False
            elif mode == "clean":
                self.state["power"] = "on"
                self.state["active_preset"] = "clean"
                self.state["eco"] = False
            elif mode.startswith("converti_"):
                self.state["power"] = "on"
                step = mode.split("_")[1]
                if step == "0":
                    self.state["converti"] = "cv_off"
                    self.state["active_preset"] = "none"
                else:
                    self.state["converti"] = f"cv_{step}"
                    self.state["active_preset"] = f"cv_{step}"
                self.state["eco"] = False
            elif mode == "off":
                self.state["power"] = "off"
                self.state["active_preset"] = "none"
                self.state["converti"] = "cv_off"
                self.state["eco"] = False
            else:
                self.state["power"] = "on"
                self.state["mode"] = mode
                # Preserve active convertible or boost preset unless turned off or reset via eco
        if target_temp is not None:
            self.state["temperature"] = target_temp
        if fan is not None:
            self.state["fan_speed"] = fan
        if v_vane is not None:
            self.state["v_vane"] = v_vane
        if h_vane is not None:
            self.state["h_vane"] = h_vane
        if eco is not None:
            self.state["eco"] = eco
            if eco:
                self.state["active_preset"] = "none"
                self.state["converti"] = "cv_off"
        if nanoe is not None:
            self.state["nanoe"] = nanoe
        if display is not None:
            self.state["display"] = "on" if display else "off"
        self.state["last_controlled_by"] = origin
        self.state["provisional"] = True

        self._notify_listeners()
