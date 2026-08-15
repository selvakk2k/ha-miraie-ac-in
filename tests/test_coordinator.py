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



if __name__ == "__main__":
    unittest.main()
