"""Unit tests for MirAIe Sensor platform entities."""

import unittest
from unittest.mock import MagicMock

from tests.ha_stub import MockHass, MockEntry
from custom_components.miraie_in.sensor import (
    MirAIeTodayEnergySensor,
    MirAIeYesterdayEnergySensor,
    MirAIeWeeklyEnergySensor,
    MirAIeMonthlyEnergySensor,
    MirAIeRoomTemperatureSensor,
    MirAIeWifiSignalSensor,
    MirAIeControlSourceSensor,
    MirAIeModelCapabilitiesSensor,
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
)


class TestSensorPlatform(unittest.IsolatedAsyncioTestCase):
    """Test MirAIe Sensor platform entities state parsing and updates."""

    def setUp(self):
        self.hass = MockHass()
        self.mock_entry = MockEntry(
            entry_id="entry_sensor_test",
            data={"device_id": "dev_sensor_test", "model_code": "CS-HZ24XKE"},
            options={},
        )

        self.mock_hub = MagicMock()
        self.mock_device = MagicMock()
        self.mock_device.id = "dev_sensor_test"
        self.mock_device.friendly_name = "Bed Room AC"
        self.mock_device.register_callback = MagicMock()
        self.mock_device.remove_callback = MagicMock()

        self.mock_device.details = DeviceDetails(
            model_name="Panasonic AC",
            mac_address="11:22:33:44:55:66",
            category="ac",
            brand="Panasonic",
            firmware_version="1.0.0",
            serial_number="SN99999",
            model_number="CS-HZ24XKE",
            product_serial_number="PSN99999",
        )

        self.mock_device.status = DeviceStatus(
            is_online=True,
            temperature=25.0,
            room_temperature=27.5,
            power_mode=LibPowerMode.ON,
            fan_mode=LibFanMode.AUTO,
            v_swing_mode=LibSwingMode.AUTO,
            h_swing_mode=LibSwingMode.AUTO,
            display_mode=MagicMock(value="on"),
            hvac_mode=LibHVACMode.COOL,
            preset_mode=LibPresetMode.NONE,
            converti_mode=LibConvertiMode.OFF,
            wifi_signal=-60,
            control_source="ir",
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

    def test_room_temperature_and_wifi_sensors(self):
        """Test room temperature and wifi signal sensors read values directly from device status."""
        temp_sensor = MirAIeRoomTemperatureSensor(self.mock_device)
        self.assertEqual(temp_sensor.native_value, 27.5)
        self.assertEqual(temp_sensor._attr_unique_id, "dev_sensor_test_room_temperature")

        wifi_sensor = MirAIeWifiSignalSensor(self.mock_device)
        self.assertEqual(wifi_sensor.native_value, -60)
        self.assertEqual(wifi_sensor._attr_unique_id, "dev_sensor_test_wifi_signal")

    def test_last_controlled_via_sensor(self):
        """Test last controlled via sensor maps control source string."""
        source_sensor = MirAIeControlSourceSensor(self.mock_device, self.coordinator)
        self.assertEqual(source_sensor.native_value, "Cloud")

        self.coordinator.state["last_controlled_by"] = "IR Blaster"
        self.assertEqual(source_sensor.native_value, "IR Blaster")

    def test_energy_sensors_initial_state(self):
        """Test yesterday, weekly, and monthly energy sensors initial values."""
        y_sensor = MirAIeYesterdayEnergySensor(self.mock_hub, self.mock_device)
        self.assertEqual(y_sensor._attr_unique_id, "dev_sensor_test_yesterday_energy")

        w_sensor = MirAIeWeeklyEnergySensor(self.mock_hub, self.mock_device)
        self.assertEqual(w_sensor._attr_unique_id, "dev_sensor_test_weekly_energy")

        m_sensor = MirAIeMonthlyEnergySensor(self.mock_hub, self.mock_device)
        self.assertEqual(m_sensor._attr_unique_id, "dev_sensor_test_monthly_energy")


if __name__ == "__main__":
    unittest.main()
