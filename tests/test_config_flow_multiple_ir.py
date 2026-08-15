"""Test adding multiple standalone IR AC units via ConfigFlow and OptionsFlow."""
import unittest
from unittest.mock import MagicMock, AsyncMock, patch

from tests.ha_stub import setup_ha_stubs
setup_ha_stubs()


class TestMultipleIRDevices(unittest.IsolatedAsyncioTestCase):
    async def test_add_multiple_ir_entries(self):
        from custom_components.miraie_in.config_flow import ConfigFlow

        flow = ConfigFlow()

        flow.hass = MagicMock()
        flow._async_current_entries = MagicMock(return_value=[
            MagicMock(data={"is_ir_only": True, "name": "Living Room AC"})
        ])

        res1 = await flow.async_step_ir_device(
            user_input={
                "name": "Bedroom AC",
                "model_code": "CS-CU-KN18YKY",
            }
        )

        self.assertEqual(res1["type"], "form")
        self.assertEqual(res1["step_id"], "feature_confirmation")

        res2 = await flow.async_step_feature_confirmation({"control_mode": "ir", "has_heat_mode": False, "has_nanoe": False, "converti_type": "7-in-1", "h_vane_enabled": True})
        self.assertEqual(res2["type"], "form")
        self.assertEqual(res2["step_id"], "attach_blaster")

        result_final = await flow.async_step_attach_blaster({"blaster_entity_id": "infrared.bedroom_blaster"})
        self.assertEqual(result_final["type"], "create_entry")
        self.assertEqual(result_final["title"], "Bedroom AC (IR Only)")
        self.assertTrue(result_final["data"]["is_ir_only"])
        self.assertEqual(result_final["data"]["name"], "Bedroom AC")
        self.assertEqual(result_final["options"]["blaster_entity_id"], "infrared.bedroom_blaster")

    async def test_add_multiple_manual_devices_in_options(self):
        from custom_components.miraie_in.config_flow import OptionsFlowHandler

        options_flow = OptionsFlowHandler()
        mock_entry = MagicMock()
        mock_entry.options = {
            "manual_devices": [
                {
                    "id": "manual_1_living_room_ac",
                    "name": "Living Room AC",
                    "model_code": "CS-CU-RU18CKY-1",
                    "blaster_entity_id": "infrared.living_room_blaster",
                }
            ]
        }
        options_flow.config_entry = mock_entry

        result = await options_flow.async_step_add_manual_device(
            user_input={
                "name": "Guest Room AC",
                "model_code": "CS-CU-KN18YKY",
                "blaster_entity_id": "infrared.guest_blaster",
                "primary_backend": "ir",
            }
        )

        self.assertEqual(result["type"], "create_entry")
        manual_devs = result["data"]["manual_devices"]
        self.assertEqual(len(manual_devs), 2)
        self.assertEqual(manual_devs[1]["name"], "Guest Room AC")
        self.assertEqual(manual_devs[1]["blaster_entity_id"], "infrared.guest_blaster")


if __name__ == "__main__":
    unittest.main()
