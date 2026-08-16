"""Unit tests for MirAIe Climate entity platform."""

import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from tests.ha_stub import MockHass, MockEntry
from homeassistant.components.climate import (
    HVACMode,
    HVACAction,
    ClimateEntityFeature,
)
from homeassistant.const import UnitOfTemperature

from custom_components.miraie_in.climate import MirAIeClimate
from custom_components.miraie_in.coordinator import MirAIeDeviceCoordinator
from miraie_ac.enums import (
    PowerMode as LibPowerMode,
    HVACMode as LibHVACMode,
    FanMode as LibFanMode,
    SwingMode as LibSwingMode,
    PresetMode as LibPresetMode,
    ConvertiMode as LibConvertiMode,
)
from miraie_ac.device import DeviceStatus, DeviceDetails


class TestClimatePlatform(unittest.IsolatedAsyncioTestCase):
    """Test MirAIeClimate entity state mapping and command dispatching."""

    def setUp(self):
        self.hass = MockHass()
        self.mock_entry = MockEntry(
            entry_id="entry_climate_test",
            data={"device_id": "dev_test", "model_code": "CS-HZ24XKE"},
            options={},
        )

        self.mock_device = MagicMock()
        self.mock_device.id = "dev_test"
        self.mock_device.friendly_name = "Living Room AC"
        self.calls = []
        async def _set_temp(t):
            self.calls.append(("set_temperature", t))
        async def _turn_off():
            self.calls.append(("turn_off",))
        async def _set_hvac(m):
            self.calls.append(("set_hvac_mode", m))
        async def _set_fan(f):
            self.calls.append(("set_fan_mode", f))
        async def _set_preset(p):
            self.calls.append(("set_preset_mode", p))
        async def _set_converti(c):
            self.calls.append(("set_converti_mode", c))

        self.mock_device.turn_on = AsyncMock()
        self.mock_device.turn_off = _turn_off
        self.mock_device.set_temperature = _set_temp
        self.mock_device.set_hvac_mode = _set_hvac
        self.mock_device.set_fan_mode = _set_fan
        self.mock_device.set_preset_mode = _set_preset
        self.mock_device.set_converti_mode = _set_converti
        self.mock_device.register_callback = MagicMock()
        self.mock_device.remove_callback = MagicMock()

        self.mock_device.details = DeviceDetails(
            model_name="Panasonic AC",
            mac_address="AA:BB:CC:DD:EE:FF",
            category="ac",
            brand="Panasonic",
            firmware_version="1.0.0",
            serial_number="SN12345",
            model_number="CS-HZ24XKE",
            product_serial_number="PSN12345",
        )

        self.mock_device.status = DeviceStatus(
            is_online=True,
            temperature=24.0,
            room_temperature=26.0,
            power_mode=LibPowerMode.ON,
            fan_mode=LibFanMode.AUTO,
            v_swing_mode=LibSwingMode.AUTO,
            h_swing_mode=LibSwingMode.AUTO,
            display_mode=MagicMock(value="on"),
            hvac_mode=LibHVACMode.COOL,
            preset_mode=LibPresetMode.NONE,
            converti_mode=LibConvertiMode.OFF,
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

        self.climate = MirAIeClimate(
            device=self.mock_device,
            entry=self.mock_entry,
            coordinator=self.coordinator,
        )
        self.climate.hass = self.hass

    async def test_climate_properties(self):
        """Test climate property mappings."""
        self.assertEqual(self.climate._attr_unique_id, "dev_test")
        self.assertEqual(self.climate.name, "Living Room AC")
        self.assertEqual(self.climate._attr_temperature_unit, UnitOfTemperature.CELSIUS)
        self.assertEqual(self.climate.target_temperature, 24)
        self.assertEqual(self.climate.current_temperature, 26.0)
        self.assertEqual(self.climate.hvac_mode, "cool")

    async def test_set_temperature_in_bounds(self):
        """Test setting target temperature within limits."""
        await self.climate.async_set_temperature(temperature=22.0)
        await asyncio.sleep(0.01)
        self.assertIn(("set_temperature", 22.0), self.calls)

    async def test_set_hvac_mode_cool_and_off(self):
        """Test setting HVAC mode to COOL and OFF."""
        await self.climate.async_set_hvac_mode(HVACMode.DRY)
        await asyncio.sleep(0.01)
        self.assertIn(("set_hvac_mode", LibHVACMode.DRY), self.calls)

        await self.climate.async_set_hvac_mode(HVACMode.OFF)
        await asyncio.sleep(0.01)
        self.assertIn(("turn_off",), self.calls)

    async def test_set_fan_mode(self):
        """Test setting fan modes."""
        await self.climate.async_set_fan_mode("high")
        await asyncio.sleep(0.01)
        self.assertIn(("set_fan_mode", LibFanMode.HIGH), self.calls)

    async def test_set_preset_mode_boost_eco_converti(self):
        """Test preset mode setting for Boost, Eco, and Converti."""
        await self.climate.async_set_preset_mode("boost")
        await asyncio.sleep(0.01)
        self.assertIn(("set_preset_mode", LibPresetMode.BOOST), self.calls)

        await self.climate.async_set_preset_mode("eco")
        await asyncio.sleep(0.01)
        self.assertIn(("set_preset_mode", LibPresetMode.ECO), self.calls)

        await self.climate.async_set_preset_mode("80%")
        await asyncio.sleep(0.01)
        self.assertIn(("set_converti_mode", LibConvertiMode.C80), self.calls)


if __name__ == "__main__":
    unittest.main()
