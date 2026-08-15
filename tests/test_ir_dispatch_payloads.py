"""Test multi-format IR payload transmission fallback in coordinator.py."""
import unittest
from unittest.mock import MagicMock, AsyncMock, patch

from tests.ha_stub import setup_ha_stubs
setup_ha_stubs()


class TestIRDispatchPayloads(unittest.IsolatedAsyncioTestCase):
    async def test_remote_send_command_multi_fallback(self):
        from custom_components.miraie_in.coordinator import MirAIeDeviceCoordinator

        hass = MagicMock()
        service_calls = []

        async def mock_call_service(domain, service, service_data, blocking=True):
            service_calls.append((domain, service, service_data))
            # Fail the first attempt (b64 with prefix) to test fallback
            if len(service_calls) == 1:
                raise ValueError("Broadlink prefix not supported on this entity")
            return True

        hass.services.async_call = AsyncMock(side_effect=mock_call_service)

        coord = MirAIeDeviceCoordinator(
            hass=hass,
            subentry_id="sub1",
            device_id="dev1",
            model_code="CS-CU-RU18CKY-1",
            has_wifi=False,
            blaster_entity_id="remote.bedroom_ir_blaster",
        )

        res = await coord.async_dispatch_ir_command(
            mode="cool",
            target_temp=24,
            fan="low",
            v_vane="V1",
        )

        self.assertTrue(res)
        self.assertEqual(len(service_calls), 2)
        # Verify 2nd attempt transmitted raw b64 payload in a list
        domain, service, data = service_calls[1]
        self.assertEqual(domain, "remote")
        self.assertEqual(service, "send_command")
        self.assertEqual(data["entity_id"], "remote.bedroom_ir_blaster")
        self.assertIsInstance(data["command"], list)


if __name__ == "__main__":
    unittest.main()
