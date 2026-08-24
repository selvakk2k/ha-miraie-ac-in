"""Unit tests for Switch and Button platforms in ha-miraie-ac."""

import unittest
from unittest.mock import MagicMock, AsyncMock

from tests.ha_stub import MockHass, MockEntry
from custom_components.miraie_in.switch import (
    MirAIeDisplaySwitch,
    MirAIeNanoeSwitch,
    MirAIeHybridSubmodeSwitch,
    MirAIeBackendSelectSwitch,
)
from custom_components.miraie_in.button import (
    MirAIeCoilCleanButton,
    MirAIeRebuildEnergyStatsButton,
    MirAIeVerifyEnergyStatsButton,
)
from custom_components.miraie_in.coordinator import MirAIeDeviceCoordinator
from miraie_ac.device import DeviceStatus, DeviceDetails
from miraie_ac.enums import (
    PowerMode as LibPowerMode,
    HVACMode as LibHVACMode,
    FanMode as LibFanMode,
    SwingMode as LibSwingMode,
    PresetMode as LibPresetMode,
    ConvertiMode as LibConvertiMode,
    DisplayMode as LibDisplayMode,
)


class TestSwitchAndButtonPlatform(unittest.IsolatedAsyncioTestCase):
    """Test Switch and Button entities execution and state reflection."""

    def setUp(self):
        self.hass = MockHass()
        self.mock_entry = MockEntry(
            entry_id="entry_sw_btn_test",
            data={"device_id": "dev_sb_test", "model_code": "CS-HZ24XKE"},
            options={},
        )

        self.mock_hub = MagicMock()
        self.mock_device = MagicMock()
        self.mock_device.id = "dev_sb_test"
        self.mock_device.friendly_name = "Dining Room AC"
        self.mock_device.set_display_mode = AsyncMock()
        self.mock_device.set_nanoe = AsyncMock()
        self.mock_device.set_preset_mode = AsyncMock()
        self.mock_device.register_callback = MagicMock()
        self.mock_device.remove_callback = MagicMock()

        self.mock_device.details = DeviceDetails(
            model_name="Panasonic AC",
            mac_address="33:44:55:66:77:88",
            category="ac",
            brand="Panasonic",
            firmware_version="1.0.0",
            serial_number="SN55555",
            model_number="CS-HZ24XKE",
            product_serial_number="PSN55555",
        )

        self.mock_device.status = DeviceStatus(
            is_online=True,
            temperature=24.0,
            room_temperature=26.0,
            power_mode=LibPowerMode.ON,
            fan_mode=LibFanMode.AUTO,
            v_swing_mode=LibSwingMode.AUTO,
            h_swing_mode=LibSwingMode.AUTO,
            display_mode=LibDisplayMode.ON,
            hvac_mode=LibHVACMode.COOL,
            preset_mode=LibPresetMode.NONE,
            converti_mode=LibConvertiMode.OFF,
            nanoe_mode="on",
        )

        self.coordinator = MirAIeDeviceCoordinator(
            hass=self.hass,
            entry_id=self.mock_entry.entry_id,
            device_id=self.mock_device.id,
            model_code="CS-HZ24XKE",
            has_wifi=True,
            blaster_entity_id=None,
            primary_backend="cloud",
            hybrid_submode="auto",
        )
        self.coordinator.state["power"] = "on"
        self.coordinator.state["mode"] = "cool"
        self.coordinator.state["temperature"] = 24.0
        self.coordinator.state["room_temperature"] = 26.0
        self.coordinator.state["nanoe"] = True
        self.coordinator.state["display"] = "on"

    async def test_display_switch_turn_on_and_off(self):
        """Test display switch toggles display mode via cloud."""
        switch = MirAIeDisplaySwitch(self.mock_device, self.coordinator)
        self.assertTrue(switch.is_on)

        await switch.async_turn_off()
        self.mock_device.set_display_mode.assert_awaited_with(LibDisplayMode.OFF)
        self.assertEqual(self.coordinator.state.get("display"), "off")

        await switch.async_turn_on()
        self.mock_device.set_display_mode.assert_awaited_with(LibDisplayMode.ON)
        self.assertEqual(self.coordinator.state.get("display"), "on")

    async def test_display_switch_ir_primary(self):
        """Test display switch dispatches IR command when primary_backend is ir."""
        coord_ir = MirAIeDeviceCoordinator(
            hass=self.hass,
            entry_id=self.mock_entry.entry_id,
            device_id=self.mock_device.id,
            model_code="CS-HZ24XKE",
            has_wifi=False,
            blaster_entity_id="infrared.living_room_blaster",
            primary_backend="ir",
        )
        coord_ir.async_dispatch_ir_command = AsyncMock(return_value=True)

        switch = MirAIeDisplaySwitch(self.mock_device, coord_ir)
        # Precondition: AC is running COOL at 28C, Fan=auto, V-Vane=V2
        coord_ir.state["mode"] = "cool"
        coord_ir.state["temperature"] = 28
        coord_ir.state["fan_speed"] = "auto"
        coord_ir.state["v_vane"] = "V2"

        await switch.async_turn_off()
        coord_ir.async_dispatch_ir_command.assert_awaited_with(mode="display", display=False, origin="IR")
        self.assertEqual(coord_ir.state.get("display"), "off")
        # Ensure climate HVAC mode and temperature were NOT altered by display toggle
        self.assertEqual(coord_ir.state.get("mode"), "cool")
        self.assertEqual(coord_ir.state.get("temperature"), 28)
        self.assertEqual(coord_ir.state.get("fan_speed"), "auto")
        self.assertEqual(coord_ir.state.get("v_vane"), "V2")

    async def test_nanoe_switch_turn_on_and_off(self):
        """Test nanoe switch toggles nanoe mode."""
        switch = MirAIeNanoeSwitch(self.mock_device, self.coordinator)
        self.assertTrue(switch.is_on)

        await switch.async_turn_off()
        self.mock_device.set_nanoe.assert_awaited_with(False)
        self.assertFalse(self.coordinator.state.get("nanoe"))

        await switch.async_turn_on()
        self.mock_device.set_nanoe.assert_awaited_with(True)
        self.assertTrue(self.coordinator.state.get("nanoe"))

    async def test_nanoe_switch_ir_primary(self):
        """Test nanoe switch dispatches IR command when primary_backend is ir."""
        coord_ir = MirAIeDeviceCoordinator(
            hass=self.hass,
            entry_id=self.mock_entry.entry_id,
            device_id=self.mock_device.id,
            model_code="CS-HZ24XKE",
            has_wifi=False,
            blaster_entity_id="infrared.living_room_blaster",
            primary_backend="ir",
        )
        coord_ir.async_dispatch_ir_command = AsyncMock(return_value=True)

        switch = MirAIeNanoeSwitch(self.mock_device, coord_ir)
        self.assertTrue(switch.available)

        await switch.async_turn_on()
        coord_ir.async_dispatch_ir_command.assert_awaited_with(nanoe=True, origin="IR")
        self.assertTrue(coord_ir.state.get("nanoe"))

    async def test_coil_clean_button_press(self):
        """Test coil clean button triggers clean preset."""
        btn = MirAIeCoilCleanButton(self.mock_device)
        await btn.async_press()
        self.mock_device.set_preset_mode.assert_awaited_with(LibPresetMode.CLEAN)


if __name__ == "__main__":
    unittest.main()
