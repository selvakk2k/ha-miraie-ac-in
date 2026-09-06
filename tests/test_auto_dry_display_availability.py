# pyrefly: ignore-errors[bad-argument-type, bad-assignment]
"""Unit tests verifying Display reconnect sync, Auto/Dry mode normalization, 8s blink delay, and dual-path availability."""

import unittest
import asyncio
import time
from unittest.mock import MagicMock, AsyncMock, patch

from tests.ha_stub import MockHass, MockEntry
from homeassistant.components.climate import HVACMode
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN

from custom_components.miraie_in import _make_cloud_cb
from custom_components.miraie_in.climate import MirAIeClimate
from custom_components.miraie_in.switch import MirAIeDisplaySwitch, MirAIeNanoeSwitch
from custom_components.miraie_in.coordinator import MirAIeDeviceCoordinator
from miraie_ac.enums import (
    PowerMode as LibPowerMode,
    HVACMode as LibHVACMode,
    FanMode as LibFanMode,
    DisplayMode as LibDisplayMode,
    PresetMode as LibPresetMode,
)


class TestAutoDryDisplayAvailability(unittest.IsolatedAsyncioTestCase):
    """Test suite for Auto/Dry normalization, Display sync, and Dual-path availability."""

    def setUp(self):
        self.hass = MockHass()
        self.mock_entry = MockEntry(
            entry_id="entry_test",
            data={"device_id": "dev_test", "model_code": "CS-KN18YKY"},
            options={},
        )
        self.mock_device = MagicMock()
        self.mock_device.id = "dev_test"
        self.mock_device.friendly_name = "Test AC"
        self.mock_device.status = MagicMock()
        self.mock_device.status.is_online = True
        self.mock_device.status.power_mode = LibPowerMode.ON
        self.mock_device.status.hvac_mode = LibHVACMode.COOL
        self.mock_device.status.fan_mode = LibFanMode.AUTO
        self.mock_device.status.temperature = 22
        self.mock_device.status.display_mode = LibDisplayMode.ON
        self.mock_device.status.preset_mode = LibPresetMode.NONE
        self.mock_device.status.nanoe_mode = "off"
        self.mock_device.status.converti_mode = None
        self.mock_device.status.vertical_swing_mode = None
        self.mock_device.status.horizontal_swing_mode = None
        self.mock_device.turn_on = AsyncMock()
        self.mock_device.turn_off = AsyncMock()
        self.mock_device.set_hvac_mode = AsyncMock()
        self.mock_device.set_temperature = AsyncMock()
        self.mock_device.set_fan_mode = AsyncMock()
        self.mock_device.set_display_mode = AsyncMock()

    async def test_cloud_cb_populates_display_acdc(self):
        """Verify _make_cloud_cb includes acdc and passes it to coordinator."""
        coord = MirAIeDeviceCoordinator(
            hass=self.hass,
            entry_id=self.mock_entry.entry_id,
            device_id=self.mock_device.id,
            model_code="CS-KN18YKY",
            has_wifi=True,
        )
        coord.async_handle_cloud_update = AsyncMock()
        cloud_cb = _make_cloud_cb(self.hass, coord, self.mock_device)

        # Trigger cloud update with display ON
        status_on = MagicMock()
        status_on.power_mode = LibPowerMode.ON
        status_on.hvac_mode = LibHVACMode.COOL
        status_on.temperature = 24
        status_on.fan_mode = LibFanMode.AUTO
        status_on.display_mode = LibDisplayMode.ON
        status_on.preset_mode = LibPresetMode.NONE
        status_on.nanoe_mode = "off"
        status_on.converti_mode = None
        status_on.vertical_swing_mode = None
        status_on.horizontal_swing_mode = None

        cloud_cb(status_on)
        await asyncio.sleep(0.01)

        coord.async_handle_cloud_update.assert_called_once()
        cloud_payload = coord.async_handle_cloud_update.call_args[0][0]
        self.assertIn("acdc", cloud_payload)
        self.assertEqual(cloud_payload["acdc"], "on")

    async def test_auto_mode_normalization_sets_temp_24(self):
        """Verify setting Auto mode normalizes target temperature to 24C."""
        coord = MirAIeDeviceCoordinator(
            hass=self.hass,
            entry_id=self.mock_entry.entry_id,
            device_id=self.mock_device.id,
            model_code="CS-KN18YKY",
            has_wifi=True,
        )
        coord.state["temperature"] = 18
        climate = MirAIeClimate(device=self.mock_device, entry=self.mock_entry, coordinator=coord)

        await climate.async_set_hvac_mode(HVACMode.AUTO)
        self.assertEqual(coord.state.get("mode"), "auto")
        self.assertEqual(coord.state.get("temperature"), 24)
        self.assertEqual(climate.target_temperature, 24)

    async def test_dry_mode_normalization_sets_fan_low(self):
        """Verify setting Dry mode normalizes fan speed to low."""
        coord = MirAIeDeviceCoordinator(
            hass=self.hass,
            entry_id=self.mock_entry.entry_id,
            device_id=self.mock_device.id,
            model_code="CS-KN18YKY",
            has_wifi=True,
        )
        coord.state["fan_speed"] = "high"
        climate = MirAIeClimate(device=self.mock_device, entry=self.mock_entry, coordinator=coord)

        await climate.async_set_hvac_mode(HVACMode.DRY)
        self.assertEqual(coord.state.get("mode"), "dry")
        self.assertEqual(coord.state.get("fan_speed"), "low")

    async def test_auto_mode_8s_blinking_delay(self):
        """Verify async_set_temperature waits remaining time of 8s when in Auto mode."""
        coord = MirAIeDeviceCoordinator(
            hass=self.hass,
            entry_id=self.mock_entry.entry_id,
            device_id=self.mock_device.id,
            model_code="CS-KN18YKY",
            has_wifi=True,
        )
        climate = MirAIeClimate(device=self.mock_device, entry=self.mock_entry, coordinator=coord)

        # Transition into Auto mode
        await climate.async_set_hvac_mode(HVACMode.AUTO)
        # Simulate 14.5s already elapsed
        climate._auto_mode_switch_time = time.monotonic() - 14.5

        t0 = time.monotonic()
        await climate.async_set_temperature(temperature=26)
        elapsed = time.monotonic() - t0

        # Must have waited remaining ~0.5s (allow small timing jitter >= 0.4s)
        self.assertGreaterEqual(elapsed, 0.4)
        self.assertEqual(coord.state.get("temperature"), 26)

    async def test_dual_control_availability_logic(self):
        """Verify dual-control AC remains online if either channel is up, offline only when both are down."""
        self.hass.states["remote.blaster"] = MagicMock(state="on")
        coord = MirAIeDeviceCoordinator(
            hass=self.hass,
            entry_id=self.mock_entry.entry_id,
            device_id=self.mock_device.id,
            model_code="CS-KN18YKY",
            has_wifi=True,
            blaster_entity_id="remote.blaster",
        )
        climate = MirAIeClimate(device=self.mock_device, entry=self.mock_entry, coordinator=coord)
        display_sw = MirAIeDisplaySwitch(self.mock_device, coord)

        # 1. Both Cloud & IR online -> Available
        self.mock_device.status.is_online = True
        self.hass.states["remote.blaster"].state = "on"
        self.assertTrue(climate.available)
        self.assertTrue(display_sw.available)

        # 2. Cloud offline, IR online -> Still Available!
        self.mock_device.status.is_online = False
        self.assertTrue(climate.available)
        self.assertTrue(display_sw.available)

        # 3. Cloud online, IR offline -> Still Available!
        self.mock_device.status.is_online = True
        self.hass.states["remote.blaster"].state = STATE_UNAVAILABLE
        self.assertTrue(climate.available)
        self.assertTrue(display_sw.available)

        # 4. Both Cloud AND IR offline -> Unavailable!
        self.mock_device.status.is_online = False
        self.assertFalse(climate.available)
        self.assertFalse(display_sw.available)

    async def test_single_control_ir_availability_logic(self):
        """Verify IR-only device becomes unavailable as soon as blaster is offline."""
        self.hass.states["remote.blaster"] = MagicMock(state="on")
        coord_ir = MirAIeDeviceCoordinator(
            hass=self.hass,
            entry_id=self.mock_entry.entry_id,
            device_id=self.mock_device.id,
            model_code="CS-KN18YKY",
            has_wifi=False,
            blaster_entity_id="remote.blaster",
            primary_backend="ir",
        )
        climate = MirAIeClimate(device=self.mock_device, entry=self.mock_entry, coordinator=coord_ir)

        self.assertTrue(climate.available)

        # Blaster goes offline -> IR-only device immediately unavailable
        self.hass.states["remote.blaster"].state = STATE_UNAVAILABLE
        self.assertFalse(climate.available)
