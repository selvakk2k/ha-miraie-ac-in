"""Unit tests for Cloud Capability Enrichment, Buzzer Gating, and Diagnostic Sensors."""

import unittest
from unittest.mock import MagicMock, AsyncMock, patch

from tests.ha_stub import setup_ha_stubs
setup_ha_stubs()

from custom_components.miraie_in.coordinator import MirAIeDeviceCoordinator
from custom_components.miraie_in.switch import MirAIeBuzzerSwitch, async_setup_entry as async_setup_switch_entry
from custom_components.miraie_in.sensor import MirAIeErrorCodeSensor
from custom_components.miraie_in.const import DOMAIN


class TestCapabilityEnrichment(unittest.IsolatedAsyncioTestCase):
    """Test dynamic capabilities resolution and entity gating."""

    def setUp(self):
        self.mock_hass = MagicMock()
        self.mock_hass.states.get.return_value = None

    def test_coordinator_capabilities_swing_and_buzzer_defaults(self):
        """Test coordinator capability resolution from model string and decoder."""
        # 2-way swing unit (KN series)
        coord_2way = MirAIeDeviceCoordinator(
            hass=self.mock_hass,
            entry_id="entry_kn",
            device_id="dev_kn",
            model_code="CS-KN18WKY",
            has_wifi=True,
        )
        self.assertEqual(coord_2way.capabilities.get("h_vane_enabled"), 0)
        self.assertFalse(coord_2way.capabilities.get("has_buzzer"))

        # 4-way swing unit (AU series)
        coord_4way = MirAIeDeviceCoordinator(
            hass=self.mock_hass,
            entry_id="entry_au",
            device_id="dev_au",
            model_code="CS-AU18AKYA",
            has_wifi=True,
        )
        self.assertEqual(coord_4way.capabilities.get("h_vane_enabled"), 1)
        self.assertFalse(coord_4way.capabilities.get("has_buzzer"))

    def test_update_model_capabilities_enables_buzzer_and_overrides_vane(self):
        """Test merging cloud capabilities dictionary."""
        coord = MirAIeDeviceCoordinator(
            hass=self.mock_hass,
            entry_id="entry_test",
            device_id="dev_test",
            model_code="CS-CU-EU18CKY5XFM",
            has_wifi=True,
        )
        # Without BuzzerControl in cloud capabilities
        cloud_caps_no_buzzer = {
            "modelNumber": "CS-CU-EU18CKY5XFM",
            "controlCapabilities": {
                "PowerControl": ["on", "off"],
                "HorizontalVaneControl": ["Auto", "Left", "Right"],
            }
        }
        coord.update_model_capabilities(cloud_caps_no_buzzer)
        self.assertFalse(coord.capabilities["has_buzzer"])
        self.assertEqual(coord.capabilities["h_vane_enabled"], 1)

        # With BuzzerControl in cloud capabilities
        cloud_caps_buzzer = {
            "modelNumber": "CS-TEST-BUZZER",
            "controlCapabilities": {
                "PowerControl": ["on", "off"],
                "BuzzerControl": ["on", "off"],
            }
        }
        coord.update_model_capabilities(cloud_caps_buzzer)
        self.assertTrue(coord.capabilities["has_buzzer"])

    async def test_switch_gating_and_orphan_cleanup(self):
        """Verify switch platform adds buzzer switch when enabled and cleans up orphans when disabled."""
        mock_hub = MagicMock()
        mock_entry_buzzer = MagicMock()
        mock_entry_buzzer.runtime_data = mock_hub
        mock_entry_buzzer.data = {"device_id": "dev_with_buzzer", "is_ir_only": False}

        mock_entry_no_buzzer = MagicMock()
        mock_entry_no_buzzer.runtime_data = mock_hub
        mock_entry_no_buzzer.data = {"device_id": "dev_no_buzzer", "is_ir_only": False}

        dev_with_buzzer = MagicMock()
        dev_with_buzzer.id = "dev_with_buzzer"
        dev_with_buzzer.friendly_name = "Living Room AC"
        dev_with_buzzer.details = MagicMock(model_number="MODEL_WITH_BUZZER", brand="Panasonic", firmware_version="1.0")
        dev_with_buzzer.status = MagicMock(is_online=True, buzzer=False)

        coord_with_buzzer = MagicMock()
        coord_with_buzzer.has_wifi = True
        coord_with_buzzer.blaster_entity_id = None
        coord_with_buzzer.capabilities = {"has_buzzer": True}
        coord_with_buzzer.state = {"buzzer": False}

        dev_no_buzzer = MagicMock()
        dev_no_buzzer.id = "dev_no_buzzer"
        dev_no_buzzer.friendly_name = "Bedroom AC"
        dev_no_buzzer.details = MagicMock(model_number="CS-CU-EU18CKY5XFM", brand="Panasonic", firmware_version="3.02")
        dev_no_buzzer.status = MagicMock(is_online=True, buzzer=False)

        coord_no_buzzer = MagicMock()
        coord_no_buzzer.has_wifi = True
        coord_no_buzzer.blaster_entity_id = None
        coord_no_buzzer.capabilities = {"has_buzzer": False}
        coord_no_buzzer.state = {"buzzer": False}

        mock_hub.home = MagicMock(devices=[dev_with_buzzer, dev_no_buzzer])
        mock_hub.coordinators = {
            "dev_with_buzzer": coord_with_buzzer,
            "dev_no_buzzer": coord_no_buzzer,
        }

        # Mock entity registry with an existing orphaned buzzer switch for dev_no_buzzer
        mock_ent_reg = MagicMock()
        mock_ent_reg.async_get_entity_id.side_effect = lambda domain, comp_domain, unq_id: (
            "switch.bedroom_ac_buzzer" if unq_id == "dev_no_buzzer_buzzer" else None
        )

        with patch("custom_components.miraie_in.switch.er.async_get", return_value=mock_ent_reg):
            # Test setup for dev_with_buzzer
            added_buzzer_entities = []
            await async_setup_switch_entry(self.mock_hass, mock_entry_buzzer, lambda ents: added_buzzer_entities.extend(ents))

            buzzer_switches = [e for e in added_buzzer_entities if isinstance(e, MirAIeBuzzerSwitch)]
            self.assertEqual(len(buzzer_switches), 1)
            self.assertEqual(buzzer_switches[0].device.id, "dev_with_buzzer")

            # Test setup for dev_no_buzzer (should not add buzzer switch, should clean up orphan)
            added_no_buzzer_entities = []
            await async_setup_switch_entry(self.mock_hass, mock_entry_no_buzzer, lambda ents: added_no_buzzer_entities.extend(ents))

            no_buzzer_switches = [e for e in added_no_buzzer_entities if isinstance(e, MirAIeBuzzerSwitch)]
            self.assertEqual(len(no_buzzer_switches), 0)
            mock_ent_reg.async_remove.assert_called_with("switch.bedroom_ac_buzzer")

    async def test_buzzer_switch_turn_on_and_off(self):
        """Test buzzer switch turns on and off via device or coordinator."""
        dev = MagicMock()
        dev.id = "dev_test"
        dev.friendly_name = "Test AC"
        dev.details = MagicMock(model_number="MODEL", brand="Panasonic", firmware_version="1.0")
        dev.status = MagicMock(is_online=True, buzzer=False)
        dev.set_buzzer = AsyncMock()

        coord = MagicMock()
        coord.state = {"buzzer": False}
        coord._notify_listeners = MagicMock()

        switch = MirAIeBuzzerSwitch(dev, coord)
        self.assertFalse(switch.is_on)
        self.assertEqual(switch.icon, "mdi:volume-mute")

        # Turn on
        await switch.async_turn_on()
        self.assertTrue(coord.state["buzzer"])
        dev.set_buzzer.assert_awaited_with(True)
        self.assertEqual(switch.icon, "mdi:volume-high")

        # Turn off
        await switch.async_turn_off()
        self.assertFalse(coord.state["buzzer"])
        dev.set_buzzer.assert_awaited_with(False)

    async def test_error_code_sensor_state_and_attributes(self):
        """Test diagnostic error code sensor exposes status and warning attributes."""
        dev = MagicMock()
        dev.id = "dev_diag"
        dev.friendly_name = "Diag AC"
        dev.details = MagicMock(model_number="MODEL", brand="Panasonic", firmware_version="1.0")
        dev.status = MagicMock(is_online=True, error_code="", warning_code="")

        coord = MagicMock()
        coord.state = {"error_code": "OK", "warning_code": ""}

        sensor = MirAIeErrorCodeSensor(dev, coord)
        self.assertEqual(sensor.native_value, "OK")
        self.assertEqual(sensor.extra_state_attributes.get("warning_code"), "")

        # Simulate hardware fault update
        coord.state["error_code"] = "H11"
        coord.state["warning_code"] = "W02"
        self.assertEqual(sensor.native_value, "H11")
        self.assertEqual(sensor.extra_state_attributes.get("warning_code"), "W02")


if __name__ == "__main__":
    unittest.main()
