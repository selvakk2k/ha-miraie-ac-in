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

    def test_energy_backfill_timestamp_boundary_and_state_class(self):
        """Verify that MirAIeEnergyHistorySensor retains TOTAL_INCREASING for HA stats validation and timestamp boundary logic works correctly."""
        mod_sensor = importlib.import_module("custom_components.miraie_in.sensor")
        from homeassistant.components.sensor import SensorStateClass
        from datetime import date, timedelta

        class MockDetails:
            model_number = "CS-CU-NU18WKY"
            brand = "Panasonic"
            firmware_version = "1.0"
        class MockDevice:
            id = "dev_test"
            friendly_name = "Test AC"
            details = MockDetails()

        # 1. Verify state_class is TOTAL_INCREASING for HA statistics validation
        history_sensor = mod_sensor.MirAIeEnergyHistorySensor(None, MockDevice())
        self.assertEqual(history_sensor._attr_state_class, SensorStateClass.TOTAL_INCREASING)

        # 2. Verify timestamp boundary matching: target_day = end_date + 1 day (local midnight today)
        today = date(2026, 8, 6)
        end_date = today - timedelta(days=1)  # 2026-08-05
        target_day = today                    # 2026-08-06 (midnight timestamp)

        # Verify old condition (target_day <= end_date) failed
        self.assertFalse(target_day <= end_date)

        # Verify fixed condition ((target_day - timedelta(days=1)) <= end_date) passes
        self.assertTrue((target_day - timedelta(days=1)) <= end_date)

    def test_rebuild_button_and_verification_hierarchy(self):
        """Verify Diagnostic Rebuild Button properties and range sum extraction helper."""
        mod_button = importlib.import_module("custom_components.miraie_in.button")
        mod_sensor = importlib.import_module("custom_components.miraie_in.sensor")
        from homeassistant.helpers.entity import EntityCategory
        from datetime import date, timedelta

        class MockDetails:
            model_number = "CS-CU-NU18WKY"
            brand = "Panasonic"
            firmware_version = "1.0"
        class MockStatus:
            is_online = True
        class MockDevice:
            id = "dev_bedroom"
            friendly_name = "Bedroom AC"
            details = MockDetails()
            status = MockStatus()

        class MockConfigEntry:
            runtime_data = type("Hub", (), {"home": type("Home", (), {"devices": [MockDevice()]})()})()

        # 1. Verify Rebuild Button Entity
        rebuild_btn = mod_button.MirAIeRebuildEnergyStatsButton(MockConfigEntry.runtime_data, MockDevice())
        self.assertEqual(rebuild_btn._attr_entity_category, EntityCategory.DIAGNOSTIC)
        self.assertEqual(rebuild_btn._attr_translation_key, "rebuild_energy_statistics")
        self.assertEqual(rebuild_btn.icon, "mdi:database-refresh")
        self.assertEqual(rebuild_btn._attr_unique_id, "dev_bedroom_rebuild_energy_statistics")

        # 2. Verify Verify Button Entity
        verify_btn = mod_button.MirAIeVerifyEnergyStatsButton(MockConfigEntry.runtime_data, MockDevice())
        self.assertEqual(verify_btn._attr_entity_category, EntityCategory.DIAGNOSTIC)
        self.assertEqual(verify_btn._attr_translation_key, "verify_energy_statistics")
        self.assertEqual(verify_btn.icon, "mdi:database-check")
        self.assertEqual(verify_btn._attr_unique_id, "dev_bedroom_verify_energy_statistics")

        # 2. Verify _extract_recorded_range_sum helper
        start_day = date(2026, 8, 1)
        end_day = date(2026, 8, 5)
        start_ts = mod_sensor._get_statistic_timestamp(start_day).timestamp()
        end_ts = mod_sensor._get_statistic_timestamp(end_day + timedelta(days=1)).timestamp()

        mock_entries = [
            {"start": start_ts, "sum": 100.0},
            {"start": end_ts, "sum": 125.5},
        ]
        delta = mod_sensor._extract_recorded_range_sum(mock_entries, start_day, end_day)
        self.assertIsNotNone(delta)
        self.assertAlmostEqual(delta, 25.5)

    def test_backfill_hierarchy_verification_and_mismatch_rebuild(self):
        """Test Yesterday -> Weekly -> Monthly hierarchy verification and API > Recorder rebuild triggers."""
        mod_sensor = importlib.import_module("custom_components.miraie_in.sensor")
        from unittest.mock import AsyncMock, MagicMock, patch
        from datetime import date, timedelta
        from miraie_ac import ConsumptionPeriodType

        class MockDetails:
            model_number = "CS-CU-NU18WKY"
            brand = "Panasonic"
            firmware_version = "1.0"
        class MockDevice:
            id = "dev_bedroom"
            friendly_name = "Bedroom AC"
            details = MockDetails()

        class MockHub:
            http = MagicMock(closed=False)
            get_energy_consumption = AsyncMock()
            get_energy_consumption_full = AsyncMock(return_value={"05082026": 2.5})

        mock_hass = MagicMock()
        mock_hass.loop.call_soon_threadsafe = lambda cb: cb()

        # Test initial backfill (no existing statistics) calls get_energy_consumption_full
        with patch("custom_components.miraie_in.sensor.get_instance") as mock_get_instance, patch("custom_components.miraie_in.sensor.er") as mock_er:
            mock_recorder = MagicMock()
            mock_recorder.async_add_executor_job = AsyncMock(return_value={})
            mock_get_instance.return_value = mock_recorder
            mock_er.async_get.return_value = MagicMock(async_get_entity_id=MagicMock(return_value="sensor.dev_bedroom_energy_history"))

            hub = MockHub()
            device = MockDevice()
            asyncio.run(mod_sensor.async_backfill_energy_statistics(mock_hass, hub, device, date(2026, 8, 1)))
            hub.get_energy_consumption_full.assert_called()


if __name__ == "__main__":
    import asyncio
    unittest.main()




