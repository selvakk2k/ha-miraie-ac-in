"""Unit tests for Diagnostics platform redaction in ha-miraie-ac."""

import unittest
from unittest.mock import MagicMock

from tests.ha_stub import MockHass, MockEntry
from custom_components.miraie_in.diagnostics import async_get_config_entry_diagnostics
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


class TestDiagnosticsPlatform(unittest.IsolatedAsyncioTestCase):
    """Test diagnostics extraction and redaction."""

    async def test_diagnostics_redaction(self):
        """Verify sensitive credentials and device serials are redacted."""
        hass = MockHass()
        entry = MockEntry(
            entry_id="entry_diag_test",
            data={
                "username": "secret_user@example.com",
                "password": "super_secret_password",
                "device_id": "dev_secret",
                "model_code": "CS-HZ24XKE",
            },
            options={"install_date": "2026-01-01"},
        )

        mock_hub = MagicMock()
        mock_device = MagicMock()
        mock_device.id = "dev_secret"
        mock_device.friendly_name = "Secret AC"
        mock_device.details = DeviceDetails(
            model_name="Panasonic AC",
            mac_address="AA:BB:CC:DD:EE:FF",
            category="ac",
            brand="Panasonic",
            firmware_version="1.0.0",
            serial_number="SECRET_SN",
            model_number="CS-HZ24XKE",
            product_serial_number="SECRET_PSN",
        )
        mock_device.status = DeviceStatus(
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

        mock_hub.home = MagicMock()
        mock_hub.home.devices = [mock_device]

        coordinator = MirAIeDeviceCoordinator(
            hass=hass,
            entry_id=entry.entry_id,
            device_id=mock_device.id,
            model_code="CS-HZ24XKE",
            has_wifi=True,
            blaster_entity_id=None,
            primary_backend="cloud",
            hybrid_submode="auto",
        )
        mock_hub.coordinators = {mock_device.id: coordinator}
        entry.runtime_data = mock_hub

        diag = await async_get_config_entry_diagnostics(hass, entry)

        self.assertIn("info", diag)
        self.assertEqual(diag["info"]["password"], "**REDACTED**")
        self.assertEqual(diag["info"]["username"], "**REDACTED**")
        self.assertIn("devices", diag)
        self.assertEqual(len(diag["devices"]), 1)
        self.assertEqual(diag["devices"][0]["details"]["mac_address"], "**REDACTED**")
        self.assertEqual(diag["devices"][0]["details"]["serial_number"], "**REDACTED**")


if __name__ == "__main__":
    unittest.main()
