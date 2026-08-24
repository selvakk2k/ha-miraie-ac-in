import unittest
from pathlib import Path
import sys

# Ensure ha_stub is loaded
LOCAL_MIRAIE_AC = Path("/home/skk/Documents/GitHub/miraie-ac")
LOCAL_PANASONIC_MODELS = Path("/home/skk/Documents/GitHub/panasonic-ac-models")

if str(LOCAL_MIRAIE_AC) not in sys.path and LOCAL_MIRAIE_AC.exists():
    sys.path.insert(0, str(LOCAL_MIRAIE_AC))

if str(LOCAL_PANASONIC_MODELS) not in sys.path and LOCAL_PANASONIC_MODELS.exists():
    sys.path.insert(0, str(LOCAL_PANASONIC_MODELS))

from tests.ha_stub import setup_ha_stubs
setup_ha_stubs()

from custom_components.miraie_in.coordinator import MirAIeDeviceCoordinator

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

class TestCoordinatorIRDispatch(unittest.IsolatedAsyncioTestCase):
    async def test_infrared_domain_dispatch(self):
        hass = MockHass()
        coord = MirAIeDeviceCoordinator(
            hass=hass,
            subentry_id="sub_123",
            device_id="dev_456",
            model_code="CS-CU-RU18CKY-1",
            has_wifi=False,
            blaster_entity_id="infrared.living_room_ir_transmitter"
        )

        success = await coord.async_dispatch_ir_command(mode="cool", target_temp=24, fan="low")
        self.assertTrue(success)

        # Test remote domain service call
        coord_remote = MirAIeDeviceCoordinator(
            hass=hass,
            subentry_id="sub_123",
            device_id="dev_456",
            model_code="CS-CU-RU18CKY-1",
            has_wifi=False,
            blaster_entity_id="remote.living_room_blaster"
        )
        success_remote = await coord_remote.async_dispatch_ir_command(mode="cool", target_temp=24, fan="low")
        self.assertTrue(success_remote)
        self.assertEqual(len(hass.services.calls), 1)
        call = hass.services.calls[0]
        self.assertEqual(call["domain"], "remote")
        self.assertEqual(call["service"], "send_command")
        self.assertEqual(call["service_data"]["entity_id"], "remote.living_room_blaster")

    async def test_cloud_update_grace_window_power_and_display(self):
        import asyncio
        hass = MockHass()
        coord = MirAIeDeviceCoordinator(
            hass=hass,
            entry_id="entry_123",
            device_id="dev_456",
            model_code="CS-CU-RU18CKY-1",
            has_wifi=True,
            primary_backend="ir",
            blaster_entity_id="remote.living_room_blaster",
        )

        # Optimistically turn power ON and display ON
        coord.async_optimistic_update(mode="cool", target_temp=24, display=True, origin="IR")
        coord._last_ir_command_timestamp = asyncio.get_event_loop().time()
        self.assertEqual(coord.state["power"], "on")
        self.assertEqual(coord.state["display"], "on")

        # Stale cloud update arriving within grace window reflecting old "off" states
        await coord.async_handle_cloud_update({"pwr": "off", "acdc": "off", "tset": 26})

        # Grace window must protect power and display and temp from being overwritten by stale payload
        self.assertEqual(coord.state["power"], "on")
        self.assertEqual(coord.state["display"], "on")
        self.assertEqual(coord.state["temperature"], 24)

        # Simulate expiration of grace window (> 8.0s ago)
        coord._last_ir_command_timestamp = asyncio.get_event_loop().time() - 10.0
        await coord.async_handle_cloud_update({"pwr": "off", "acdc": "off"})
        self.assertEqual(coord.state["power"], "off")
        self.assertEqual(coord.state["display"], "off")


if __name__ == "__main__":
    unittest.main()
