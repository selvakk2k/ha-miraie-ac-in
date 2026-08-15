"""Tests verifying the 7-phase Hybrid IR+Cloud Action Plan implementation."""
import unittest
from unittest.mock import MagicMock

from tests.ha_stub import setup_ha_stubs
setup_ha_stubs()

from custom_components.miraie_in.coordinator import MirAIeDeviceCoordinator
from custom_components.miraie_in.switch import MirAIeBackendSelectSwitch


class MockServiceRegistry:
    def __init__(self):
        self.calls = []

    async def async_call(self, domain, service, service_data, blocking=True):
        self.calls.append({
            "domain": domain,
            "service": service,
            "service_data": service_data,
        })
        return True


class MockHass:
    def __init__(self):
        self.services = MockServiceRegistry()
        self.states = {}
        self.config_entries = MagicMock()



class TestHybridActionPlan(unittest.IsolatedAsyncioTestCase):
    async def test_coordinator_pushed_mqtt_update(self):
        hass = MockHass()
        coord = MirAIeDeviceCoordinator(
            hass=hass,
            subentry_id="entry_123",
            device_id="dev_456",
            model_code="CS-CU-RU18CKY-1",
            has_wifi=True,
            blaster_entity_id="infrared.living_room_ir_transmitter",
        )

        cloud_payload = {
            "pwr": "on",
            "md": "cool",
            "tset": 22,
            "acfs": "high",
            "acec": "on",
        }
        await coord.async_handle_cloud_update(cloud_payload)

        self.assertEqual(coord.state["power"], "on")
        self.assertEqual(coord.state["mode"], "cool")
        self.assertEqual(coord.state["temperature"], 22)
        self.assertEqual(coord.state["fan_speed"], "high")
        self.assertTrue(coord.state["eco"])
        self.assertEqual(coord.state["last_controlled_by"], "Cloud")

    async def test_phase5_auto_flip_backend_switch(self):
        hass = MockHass()
        coord = MirAIeDeviceCoordinator(
            hass=hass,
            subentry_id="entry_123",
            device_id="dev_456",
            model_code="CS-CU-RU18CKY-1",
            has_wifi=True,
            blaster_entity_id="infrared.living_room_ir_transmitter",
            primary_backend="cloud",
            hybrid_submode="auto",
        )
        coord.hass = hass

        mock_entry = MagicMock()
        mock_entry.options = {}
        hass.config_entries.async_get_entry = MagicMock(return_value=mock_entry)
        hass.config_entries.async_update_entry = MagicMock()

        device = MagicMock()
        device.id = "dev_456"
        device.friendly_name = "Room 2 AC"
        device.details.brand = "Panasonic"
        device.details.model_number = "CS-CU-RU18CKY-1"

        backend_switch = MirAIeBackendSelectSwitch(device, coord)
        backend_switch.hass = hass
        backend_switch.async_write_ha_state = MagicMock()

        # Turning off primary backend switch while in auto mode should flip submode to manual
        await backend_switch.async_turn_off()


        self.assertEqual(coord.primary_backend, "ir")
        self.assertEqual(coord.hybrid_submode, "manual")
        self.assertTrue(hass.config_entries.async_update_entry.called)


if __name__ == "__main__":
    unittest.main()
