"""Test setup of IR-only standalone entries in __init__.py."""
import unittest
import asyncio
from typing import Any
from unittest.mock import MagicMock, AsyncMock, patch



from tests.ha_stub import setup_ha_stubs
setup_ha_stubs()

class MockHass:
    def __init__(self):
        self.data = {}
        self.config_entries = MagicMock()
        self.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
        self.services = MagicMock()
        self.states = {}
        self.is_running = True


    def async_create_task(self, target):
        return asyncio.create_task(target) if asyncio.iscoroutine(target) else target


class TestIRDeviceSetup(unittest.IsolatedAsyncioTestCase):
    async def test_ir_device_setup_entry(self):
        import custom_components.miraie_in as mod_init

        mock_entry = MagicMock()
        mock_entry.data = {
            "is_ir_only": True,
            "name": "Living Room AC",
            "model_code": "CS-CU-RU18CKY-1",
        }
        mock_entry.options = {
            "blaster_entity_id": "infrared.living_room_blaster",
            "primary_backend": "ir",
            "hybrid_submode": "manual",
        }
        mock_entry.entry_id = "entry_ir_123"
        mock_entry.unique_id = "ir_standalone_living_room_ac"
        mock_entry.title = "Living Room AC (IR Only)"

        hass: Any = MockHass()
        mock_entry_typed: Any = mock_entry

        with patch("custom_components.miraie_in._migrate_unique_ids"):
            res = await mod_init.async_setup_entry(hass, mock_entry_typed)

        self.assertTrue(res)
        hub = mock_entry.runtime_data
        self.assertIsNotNone(hub)
        self.assertEqual(len(hub.home.devices), 1)
        device = hub.home.devices[0]
        self.assertEqual(device.friendly_name, "Living Room AC")
        self.assertIn(device.id, hub.coordinators)
        coord = hub.coordinators[device.id]
        self.assertEqual(coord.primary_backend, "ir")
        self.assertEqual(coord.hybrid_submode, "manual")

    async def test_special_command_does_not_poison_subsequent_ir_dispatch(self):
        import custom_components.miraie_in as mod_init
        from custom_components.miraie_in.climate import MirAIeClimate

        mock_entry = MagicMock()
        mock_entry.data = {
            "is_ir_only": True,
            "name": "Living Room AC",
            "model_code": "CS-CU-RU18CKY-1",
        }
        mock_entry.options = {
            "blaster_entity_id": "remote.living_room_broadlink",
            "primary_backend": "ir",
            "hybrid_submode": "manual",
        }
        mock_entry.entry_id = "entry_ir_456"
        mock_entry.unique_id = "ir_standalone_living_room_ac_2"
        mock_entry.title = "Living Room AC (IR Only)"

        hass: Any = MockHass()
        mock_entry_typed: Any = mock_entry
        service_calls = []

        async def mock_async_call(domain, service, service_data, blocking=True):
            service_calls.append({"domain": domain, "service": service, "data": service_data})

        hass.services.async_call = mock_async_call

        with patch("custom_components.miraie_in._migrate_unique_ids"):
            await mod_init.async_setup_entry(hass, mock_entry_typed)

        hub = mock_entry.runtime_data
        device = hub.home.devices[0]
        coord = hub.coordinators[device.id]
        climate = MirAIeClimate(device, mock_entry, coord)

        # Step 1: Send Boost (powerful) mode via IR
        await climate.async_set_preset_mode("boost")
        self.assertEqual(coord.state["active_preset"], "powerful")
        self.assertEqual(coord.state["mode"], "cool")

        # Verify Boost IR service call went out
        self.assertTrue(len(service_calls) > 0)
        first_call = service_calls[-1]
        boost_payload = first_call["data"]["command"][0]

        # Step 2: Immediately dispatch fan speed change (mode=None)
        service_calls.clear()
        await climate.async_set_fan_mode("high")

        # Verify fan speed call went out and state["mode"] stayed "cool"
        self.assertEqual(coord.state["fan_speed"], "high")
        self.assertEqual(coord.state["mode"], "cool")
        self.assertTrue(len(service_calls) > 0)

        fan_call = service_calls[-1]
        fan_payload = fan_call["data"]["command"][0]

        # Critical Assertion: Fan change MUST NOT retransmit the short-frame Boost payload!
        self.assertNotEqual(boost_payload, fan_payload)
        self.assertTrue(len(fan_payload) > len(boost_payload))


if __name__ == "__main__":
    unittest.main()
