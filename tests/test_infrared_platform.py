"""Test native Home Assistant infrared platform transmission in coordinator.py."""
import unittest
from unittest.mock import MagicMock, AsyncMock, patch

from tests.ha_stub import setup_ha_stubs
setup_ha_stubs()


class TestInfraredPlatformTransmission(unittest.IsolatedAsyncioTestCase):
    async def test_native_infrared_platform(self):
        from custom_components.miraie_in.coordinator import MirAIeDeviceCoordinator

        hass = MagicMock()
        service_calls = []

        async def mock_call_service(domain, service, service_data, blocking=True):
            service_calls.append((domain, service, service_data))
            return True

        hass.services.async_call = AsyncMock(side_effect=mock_call_service)

        coord = MirAIeDeviceCoordinator(
            hass=hass,
            subentry_id="sub1",
            device_id="dev1",
            model_code="CS-CU-RU18CKY-1",
            has_wifi=False,
            blaster_entity_id="infrared.living_room_blaster",
        )

        res = await coord.async_dispatch_ir_command(
            mode="cool",
            target_temp=22,
            fan="high",
            v_vane="V1",
        )

        self.assertTrue(res)

        # Test failure path when helper raises Exception
        with patch("homeassistant.components.infrared.helpers.async_send_command", side_effect=RuntimeError("Blaster unreachable")):
            res2 = await coord.async_dispatch_ir_command(
                mode="cool",
                target_temp=22,
                fan="high",
                v_vane="V1",
            )

        self.assertFalse(res2)
        self.assertEqual(len(service_calls), 0)




if __name__ == "__main__":
    unittest.main()
