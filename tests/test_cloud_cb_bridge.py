"""Test that _make_cloud_cb correctly bridges device.status to coordinator.state."""
import unittest
from unittest.mock import MagicMock

from tests.ha_stub import setup_ha_stubs
setup_ha_stubs()


class TestCloudCBBridge(unittest.IsolatedAsyncioTestCase):
    async def test_cloud_cb_bridge_vane_and_presets(self):
        from custom_components.miraie_in.__init__ import _make_cloud_cb
        from custom_components.miraie_in.coordinator import MirAIeDeviceCoordinator

        hass = MagicMock()
        
        # Mock device with status matching miraie_ac structure
        dev = MagicMock()
        dev.id = "test_dev_1"
        dev.details.model_number = "CS-CU-RU18CKY-1"
        dev.details.has_wifi = True
        
        dev.status.power_mode.value = "on"
        dev.status.hvac_mode.value = "cool"
        dev.status.temperature = 24
        dev.status.fan_mode.value = "high"
        dev.status.v_swing_mode.value = 1  # Integer 1 -> should map to V1
        dev.status.h_swing_mode.value = 2  # Integer 2 -> should map to H2
        dev.status.preset_mode.value = "eco"
        dev.status.nanoe_mode = "on"

        coordinator = MirAIeDeviceCoordinator(
            hass=hass,
            subentry_id="sub1",
            device_id="test_dev_1",
            model_code="CS-CU-RU18CKY-1",
            has_wifi=True,
        )

        created_coros = []
        def _mock_create_task(coro):
            created_coros.append(coro)
            return coro

        hass.async_create_task = _mock_create_task

        cb = _make_cloud_cb(hass, coordinator, dev)
        
        # Invoke callback with dummy args
        cb(dev, dev.status)

        for c in created_coros:
            await c

        # Force await async_handle_cloud_update if it returned a coroutine
        # Assert correct string format V1/H2 and boolean eco/nanoe states
        self.assertEqual(coordinator.state["v_vane"], "V1")
        self.assertEqual(coordinator.state["h_vane"], "H2")
        self.assertEqual(coordinator.state["eco"], True)
        self.assertEqual(coordinator.state["nanoe"], True)


if __name__ == "__main__":
    unittest.main()
