"""Unit tests for MirAIe config flow and per-device options flow forms."""

import unittest
import asyncio
import importlib
from unittest.mock import MagicMock
import tests.ha_stub


class TestConfigFlowDevices(unittest.TestCase):
    """Test options flow device listing, __all__ overrides, and error validation."""

    def setUp(self):
        self.mod_flow = importlib.import_module("custom_components.miraie_in.config_flow")

    async def async_test_options_flow_init_form_render(self):
        """Test async_step_init form rendering when user_input is None."""
        from tests.fixtures import MockConfigEntry, MockDevice

        dev1 = MockDevice(device_id="dev_living", friendly_name="Living Room AC")
        dev2 = MockDevice(device_id="dev_bed", friendly_name="Bedroom AC")
        entry = MockConfigEntry(devices=[dev1, dev2])

        flow = self.mod_flow.OptionsFlowHandler()
        flow.config_entry = entry

        res = await flow.async_step_init(user_input=None)
        self.assertEqual(res["type"], "form")
        self.assertEqual(res["step_id"], "init")

    async def async_test_options_flow_all_clear_branch(self):
        """Test async_step_device_settings with __all__ device setting clears overrides."""
        from tests.fixtures import MockConfigEntry, MockDevice

        dev1 = MockDevice(device_id="dev1")
        entry = MockConfigEntry(
            options={"install_date": "2026-01-01", "devices": {"dev1": {"install_date": "2026-02-01"}}},
            devices=[dev1],
        )

        flow = self.mod_flow.OptionsFlowHandler()
        flow.config_entry = entry

        await flow.async_step_init(user_input={"devices": ["__all__"]})

        res = await flow.async_step_device_settings(user_input={"install_date": "2026-03-01"})
        self.assertEqual(res["type"], "create_entry")
        # Ensure per-device overrides were cleared
        self.assertEqual(res["data"]["devices"], {})
        self.assertEqual(res["data"]["install_date"], "2026-03-01")

    async def async_test_options_flow_invalid_date_error_redisplay(self):
        """Test invalid install date returns form with error."""
        from tests.fixtures import MockConfigEntry, MockDevice

        dev1 = MockDevice(device_id="dev1")
        entry = MockConfigEntry(devices=[dev1])

        flow = self.mod_flow.OptionsFlowHandler()
        flow.config_entry = entry

        await flow.async_step_init(user_input={"devices": ["__all__"]})

        res = await flow.async_step_device_settings(user_input={"install_date": "invalid-date"})
        self.assertEqual(res["type"], "form")
        self.assertIn("errors", res)
        self.assertEqual(res["errors"]["install_date"], "invalid_install_date")

    def test_run_async_tests(self):
        """Runner for async test methods."""
        asyncio.run(self.async_test_options_flow_init_form_render())
        asyncio.run(self.async_test_options_flow_all_clear_branch())
        asyncio.run(self.async_test_options_flow_invalid_date_error_redisplay())


if __name__ == "__main__":
    unittest.main()
