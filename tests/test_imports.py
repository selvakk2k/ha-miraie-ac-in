import asyncio
import importlib
import sys
import unittest
from pathlib import Path

# Add repository root to sys.path so custom_components can be imported
REPO_ROOT = Path(__file__).parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.ha_stub import setup_ha_stubs
setup_ha_stubs()


class TestModuleImports(unittest.TestCase):
    """Test that all integration modules can be imported without ImportError or AttributeError."""

    def test_import_const(self):
        mod = importlib.import_module("custom_components.miraie_in.const")
        self.assertIsNotNone(mod)
        self.assertEqual(mod.DOMAIN, "miraie_in")

    def test_import_utils(self):
        mod = importlib.import_module("custom_components.miraie_in.utils")
        self.assertIsNotNone(mod)

    def test_import_logger(self):
        mod = importlib.import_module("custom_components.miraie_in.logger")
        self.assertIsNotNone(mod)

    def test_import_config_flow(self):
        mod = importlib.import_module("custom_components.miraie_in.config_flow")
        self.assertIsNotNone(mod)
        handler = mod.ConfigFlow.async_get_options_flow(None)
        self.assertIsInstance(handler, mod.OptionsFlowHandler)

    def test_import_climate(self):
        mod = importlib.import_module("custom_components.miraie_in.climate")
        self.assertIsNotNone(mod)
        self.assertTrue(hasattr(mod, "MirAIeClimate"))

    def test_import_sensor(self):
        mod = importlib.import_module("custom_components.miraie_in.sensor")
        self.assertIsNotNone(mod)

    def test_import_binary_sensor(self):
        mod = importlib.import_module("custom_components.miraie_in.binary_sensor")
        self.assertIsNotNone(mod)

    def test_import_button(self):
        mod = importlib.import_module("custom_components.miraie_in.button")
        self.assertIsNotNone(mod)

    def test_import_switch(self):
        mod = importlib.import_module("custom_components.miraie_in.switch")
        self.assertIsNotNone(mod)

    def test_import_diagnostics(self):
        mod = importlib.import_module("custom_components.miraie_in.diagnostics")
        self.assertIsNotNone(mod)

    def test_import_init(self):
        mod = importlib.import_module("custom_components.miraie_in")
        self.assertIsNotNone(mod)

    def test_invalid_symbol_climate_precision_halves(self):
        """Verify that importing PRECISION_HALVES from homeassistant.components.climate fails."""
        with self.assertRaises((ImportError, AttributeError)):
            from homeassistant.components.climate import PRECISION_HALVES  # type: ignore


    def test_options_flow_multi_device_steps(self):
        mod = importlib.import_module("custom_components.miraie_in.config_flow")
        handler = mod.OptionsFlowHandler()
        # Mock config entry
        class MockConfigEntry:
            options = {}
            runtime_data = None
        handler.config_entry = MockConfigEntry()

        # Step 1 init
        result_step1 = asyncio.run(handler.async_step_init({"devices": ["dev1", "dev2"]}))
        self.assertEqual(result_step1["type"], "form")
        self.assertEqual(result_step1["step_id"], "device_settings")
        self.assertEqual(handler._selected_devices, ["dev1", "dev2"])

        # Step 2 device_settings submission
        result_step2 = asyncio.run(
            handler.async_step_device_settings(
                {"install_date": "2026-01-01", "half_degree_precision": True}
            )
        )
        self.assertEqual(result_step2["type"], "create_entry")
        options = result_step2["data"]
        self.assertIn("devices", options)
        self.assertTrue(options["devices"]["dev1"]["half_degree_precision"])
        self.assertTrue(options["devices"]["dev2"]["half_degree_precision"])
        self.assertEqual(options["devices"]["dev1"]["install_date"], "2026-01-01")

    def test_climate_per_device_precision(self):
        mod_climate = importlib.import_module("custom_components.miraie_in.climate")
        class MockDetails:
            model_number = "CS-CU-NU18WKY"
            brand = "Panasonic"
            firmware_version = "1.0"
        class MockDevice:
            id = "dev_bedroom"
            friendly_name = "Bedroom AC"
            details = MockDetails()

        class MockConfigEntry:
            options = {
                "half_degree_precision": False,
                "devices": {
                    "dev_bedroom": {"half_degree_precision": True}
                }
            }

        climate_entity = mod_climate.MirAIeClimate(MockDevice(), MockConfigEntry())
        self.assertTrue(climate_entity._half_degree_precision)
        self.assertEqual(climate_entity._attr_target_temperature_step, 0.5)


    def test_async_unload_entry(self):
        mod_init = importlib.import_module("custom_components.miraie_in")
        from miraie_ac import MirAIeHub

        async def _run():
            class MockHass:
                class config_entries:
                    @staticmethod
                    async def async_unload_platforms(entry, platforms):
                        return True

            class MockConfigEntry:
                runtime_data = MirAIeHub()

            hass = MockHass()
            entry = MockConfigEntry()
            return await mod_init.async_unload_entry(hass, entry)

        result = asyncio.run(_run())
        self.assertTrue(result)


    def test_async_setup_entry_forwards_platforms(self):
        mod_init = importlib.import_module("custom_components.miraie_in")
        from miraie_ac import MirAIeHub
        from unittest.mock import patch

        forwarded_platforms = []

        async def _run():
            class MockConfigEntries:
                @staticmethod
                async def async_forward_entry_setups(entry, platforms):
                    forwarded_platforms.extend(platforms)
                    return True

            class MockHass:
                config_entries = MockConfigEntries()
                is_running = True

                def async_create_task(self, target):
                    pass

            class MockConfigEntry:
                data = {"username": "test@user.com", "password": "password"}
                options = {}
                entry_id = "test_entry"

                def async_on_unload(self, target):
                    pass

                def add_update_listener(self, listener):
                    return lambda: None

            async def dummy_init(username, password, broker):
                pass

            hub = MirAIeHub()
            hub.init = dummy_init
            hub.home = type("Home", (), {"devices": []})()

            with patch("custom_components.miraie_in.MirAIeHub", return_value=hub), patch("custom_components.miraie_in._migrate_unique_ids"):
                await mod_init.async_setup_entry(MockHass(), MockConfigEntry())

        asyncio.run(_run())
        self.assertEqual(
            set(forwarded_platforms),
            set(mod_init.PLATFORMS),
            "async_setup_entry MUST forward entry setups to all integration PLATFORMS",
        )


    def test_model_gating_heat_and_nanoe(self):
        mod_const = importlib.import_module("custom_components.miraie_in.const")
        # Heat mode: EZ and KZ series support heat
        self.assertTrue(mod_const.supports_heat_mode("CS-CU-EZ18WKY"))
        self.assertTrue(mod_const.supports_heat_mode("CS-CU-KZ18WKY"))
        self.assertFalse(mod_const.supports_heat_mode("CS-CU-NU18WKY"))
        self.assertFalse(mod_const.supports_heat_mode("CS-CU-SU18WKY"))

        # Nanoe: XU and HU series support nanoe
        self.assertTrue(mod_const.supports_nanoe("CS-CU-XU18WKY"))
        self.assertTrue(mod_const.supports_nanoe("CS-CU-HU18WKY"))
        self.assertFalse(mod_const.supports_nanoe("CS-CU-NU18WKY"))

    def test_converti_preset_gating(self):
        mod_const = importlib.import_module("custom_components.miraie_in.const")
        # NU series Gen A (7-in-1) vs Gen B (8-in-1)
        nu_gen_a = mod_const.get_converti_preset_modes("CS-CU-NU18AKY")
        nu_gen_b = mod_const.get_converti_preset_modes("CS-CU-NU18BKY")
        self.assertEqual(len(nu_gen_a), 8)  # 7-in-1 has 8 items (none + 7 capacity steps)
        self.assertEqual(len(nu_gen_b), 9)  # 8-in-1 has 9 items (none + 8 capacity steps)

    def test_per_device_option_fallback(self):
        mod_climate = importlib.import_module("custom_components.miraie_in.climate")
        class MockDetails:
            model_number = "CS-CU-NU18WKY"
            brand = "Panasonic"
            firmware_version = "1.0"
        class MockDevice1:
            id = "dev_bedroom"
            friendly_name = "Bedroom AC"
            details = MockDetails()
        class MockDevice2:
            id = "dev_living"
            friendly_name = "Living Room AC"
            details = MockDetails()

        class MockConfigEntry:
            options = {
                "half_degree_precision": False,
                "devices": {
                    "dev_bedroom": {"half_degree_precision": True}
                }
            }

        entry = MockConfigEntry()
        bedroom_climate = mod_climate.MirAIeClimate(MockDevice1(), entry)
        living_climate = mod_climate.MirAIeClimate(MockDevice2(), entry)

        # Bedroom has explicit override (True -> 0.5 step)
        self.assertTrue(bedroom_climate._half_degree_precision)
        self.assertEqual(bedroom_climate._attr_target_temperature_step, 0.5)

        # Living Room has no override -> falls back to global default (False -> 1.0 step)
        self.assertFalse(living_climate._half_degree_precision)
        self.assertEqual(living_climate._attr_target_temperature_step, 1.0)


if __name__ == "__main__":
    import asyncio
    unittest.main()




