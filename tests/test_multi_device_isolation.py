"""Unit test verifying multi-device isolation and zero cross-entry entity duplication.

Tests simulating a 13-device account to verify that each per-device ConfigEntry
creates entities exclusively for its target device (total 13 climate entities, not 169).
"""

import unittest
import asyncio
import importlib
from unittest.mock import MagicMock, AsyncMock, patch
from tests.ha_stub import setup_ha_stubs
setup_ha_stubs()

from enum import Enum
import homeassistant.components.binary_sensor
import homeassistant.helpers.entity
class BinarySensorDeviceClass(Enum):
    PROBLEM = "problem"
    CONNECTIVITY = "connectivity"
    RUNNING = "running"
homeassistant.components.binary_sensor.BinarySensorDeviceClass = BinarySensorDeviceClass

class EntityCategory(Enum):
    CONFIG = "config"
    DIAGNOSTIC = "diagnostic"
homeassistant.helpers.entity.EntityCategory = EntityCategory
homeassistant.const.EntityCategory = EntityCategory

import homeassistant.components.sensor
class SensorDeviceClass(Enum):
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    ENERGY = "energy"
    POWER = "power"
    VOLTAGE = "voltage"
    CURRENT = "current"
    SIGNAL_STRENGTH = "signal_strength"
homeassistant.components.sensor.SensorDeviceClass = SensorDeviceClass

import homeassistant.helpers.event
homeassistant.helpers.event.async_track_time_interval = lambda *args, **kwargs: (lambda: None)

from tests.fixtures import MockDevice


class MockHass:
    def __init__(self):
        self.config_entries = MagicMock()
        self.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
        self.services = MagicMock()
        self.states = {}
        self.is_running = True
        self.config = MagicMock()
        self.config.components = set()

    def async_create_task(self, target):
        return asyncio.create_task(target) if asyncio.iscoroutine(target) else target

    async def async_add_executor_job(self, fn, *args):
        return fn(*args)


class MockEntry:
    def __init__(self, entry_id="mock_entry", title="Mock AC", data=None, options=None, devices=None):
        self.entry_id = entry_id
        self.title = title
        self.data = data or {}
        self.options = options or {}
        self.runtime_data = None

    def async_on_unload(self, fn):
        pass

    def add_update_listener(self, fn):
        return lambda: None


class TestMultiDeviceIsolation(unittest.IsolatedAsyncioTestCase):
    """Test multi-device per-entry isolation and entity registry cleanup."""

    async def asyncSetUp(self):
        self.mod_init = importlib.import_module("custom_components.miraie_in")
        self.mod_climate = importlib.import_module("custom_components.miraie_in.climate")
        self.mod_sensor = importlib.import_module("custom_components.miraie_in.sensor")
        self.mod_binary_sensor = importlib.import_module("custom_components.miraie_in.binary_sensor")
        self.mod_switch = importlib.import_module("custom_components.miraie_in.switch")
        self.mod_button = importlib.import_module("custom_components.miraie_in.button")

    async def test_13_devices_happy_path_isolation(self):
        """Simulate a 13-device user account on happy path and verify exactly 1 climate entity per entry."""
        # 1. Create 13 mock devices in a single MirAIe home
        all_devices = [
            MockDevice(
                device_id=f"dev_{i}",
                friendly_name=f"AC Room {i}",
            )
            for i in range(1, 14)
        ]
        self.assertEqual(len(all_devices), 13)

        hass = MockHass()

        # Track entities created across all 13 entries
        created_climate_entities = []
        created_switches = []
        created_sensors = []
        created_binary_sensors = []
        created_buttons = []

        # 2. Simulate 13 individual ConfigEntries (one for each device_id)
        for i in range(1, 14):
            dev_id = f"dev_{i}"
            entry = MockEntry(
                entry_id=f"entry_{dev_id}",
                title=f"AC Room {i}",
                data={
                    "username": "user@example.com",
                    "password": "password",
                    "device_id": dev_id,
                    "name": f"AC Room {i}",
                    "model_code": "CS-CU-RU18CKY-1",
                    "is_ir_only": False,
                },
                options={},
            )

            mock_hub = MagicMock()
            mock_home = MagicMock()
            mock_home.devices = list(all_devices)  # Account returns all 13 devices initially
            mock_hub.home = mock_home
            mock_hub.init = AsyncMock(return_value=True)

            # Setup integration entry
            with patch("custom_components.miraie_in.MirAIeHub", return_value=mock_hub), \
                 patch("custom_components.miraie_in.MirAIeBroker"), \
                 patch("custom_components.miraie_in.async_backfill_energy_statistics", new_callable=AsyncMock):
                res = await self.mod_init.async_setup_entry(hass, entry)
                self.assertTrue(res)

            # Setup Climate platform
            entry_climate = []
            await self.mod_climate.async_setup_entry(hass, entry, lambda ents: entry_climate.extend(ents))
            self.assertEqual(len(entry_climate), 1, f"Entry {dev_id} must create exactly 1 climate entity, got {len(entry_climate)}")
            self.assertEqual(entry_climate[0].device.id, dev_id)
            created_climate_entities.extend(entry_climate)

            # Setup Switch platform
            entry_switches = []
            await self.mod_switch.async_setup_entry(hass, entry, lambda ents: entry_switches.extend(ents))
            for sw in entry_switches:
                self.assertEqual(sw.device.id, dev_id)
            created_switches.extend(entry_switches)

            # Setup Binary Sensor platform
            entry_bin_sensors = []
            await self.mod_binary_sensor.async_setup_entry(hass, entry, lambda ents: entry_bin_sensors.extend(ents))
            for bs in entry_bin_sensors:
                self.assertEqual(bs.device.id, dev_id)
            created_binary_sensors.extend(entry_bin_sensors)

            # Setup Button platform
            entry_buttons = []
            await self.mod_button.async_setup_entry(hass, entry, lambda ents: entry_buttons.extend(ents))
            for btn in entry_buttons:
                self.assertEqual(btn.device.id, dev_id)
            created_buttons.extend(entry_buttons)

            # Setup Sensor platform
            entry_sensors = []
            await self.mod_sensor.async_setup_entry(hass, entry, lambda ents, update_before_add=False: entry_sensors.extend(ents))
            for s in entry_sensors:
                self.assertEqual(s.device.id, dev_id)
            created_sensors.extend(entry_sensors)

        # 3. Assert total counts: exactly 13 climate entities across all 13 entries (NOT 169)
        self.assertEqual(
            len(created_climate_entities),
            13,
            f"Expected total 13 climate entities across 13 entries, but got {len(created_climate_entities)} (169-device bug!)",
        )

        # Verify all 13 distinct device IDs are represented exactly once
        unique_device_ids = {e.device.id for e in created_climate_entities}
        self.assertEqual(len(unique_device_ids), 13)
        for i in range(1, 14):
            self.assertIn(f"dev_{i}", unique_device_ids)

    async def test_mismatched_device_id_raises_not_ready_and_prevents_entity_generation(self):
        """Verify that an entry with an unknown/missing device_id raises ConfigEntryNotReady and generates 0 entities."""
        from homeassistant.exceptions import ConfigEntryNotReady

        # Account has devices dev_1..dev_13
        all_devices = [
            MockDevice(device_id=f"dev_{i}", friendly_name=f"AC Room {i}")
            for i in range(1, 14)
        ]
        hass = MockHass()

        entry_mismatched = MockEntry(
            entry_id="entry_dev_mismatched",
            title="Mismatched AC",
            data={
                "username": "user@example.com",
                "password": "password",
                "device_id": "dev_non_existent_99",
                "name": "Mismatched AC",
                "model_code": "CS-CU-RU18CKY-1",
                "is_ir_only": False,
            },
            options={},
        )

        mock_hub = MagicMock()
        mock_home = MagicMock()
        mock_home.devices = list(all_devices)
        mock_hub.home = mock_home
        mock_hub.init = AsyncMock(return_value=True)

        # 1. Assert async_setup_entry in __init__.py raises ConfigEntryNotReady
        with patch("custom_components.miraie_in.MirAIeHub", return_value=mock_hub), \
             patch("custom_components.miraie_in.MirAIeBroker"), \
             patch("custom_components.miraie_in.async_backfill_energy_statistics", new_callable=AsyncMock):
            with self.assertRaises(ConfigEntryNotReady):
                await self.mod_init.async_setup_entry(hass, entry_mismatched)

        # 2. Directly verify each platform module produces 0 entities when given a mismatched device_id
        entry_mismatched.runtime_data = mock_hub
        mock_hub.coordinators = {}

        created_climate = []
        await self.mod_climate.async_setup_entry(hass, entry_mismatched, lambda ents: created_climate.extend(ents))
        self.assertEqual(len(created_climate), 0, "Platform climate must create 0 entities for a mismatched device_id")

        created_switches = []
        await self.mod_switch.async_setup_entry(hass, entry_mismatched, lambda ents: created_switches.extend(ents))
        self.assertEqual(len(created_switches), 0, "Platform switch must create 0 entities for a mismatched device_id")

        created_sensors = []
        await self.mod_sensor.async_setup_entry(hass, entry_mismatched, lambda ents, update_before_add=False: created_sensors.extend(ents))
        self.assertEqual(len(created_sensors), 0, "Platform sensor must create 0 entities for a mismatched device_id")

        created_binary = []
        await self.mod_binary_sensor.async_setup_entry(hass, entry_mismatched, lambda ents: created_binary.extend(ents))
        self.assertEqual(len(created_binary), 0, "Platform binary_sensor must create 0 entities for a mismatched device_id")

        created_buttons = []
        await self.mod_button.async_setup_entry(hass, entry_mismatched, lambda ents: created_buttons.extend(ents))
        self.assertEqual(len(created_buttons), 0, "Platform button must create 0 entities for a mismatched device_id")

    async def test_cross_device_entity_registry_cleanup(self):
        """Verify _cleanup_cross_device_entities automatically removes orphaned cross-device duplicates."""
        from homeassistant.helpers import entity_registry as er

        hass = MockHass()
        registry = er.async_get(hass)

        target_dev_id = "dev_living"
        entry = MockEntry(
            entry_id="entry_living",
            data={"device_id": target_dev_id},
        )

        # Pre-populate registry under this entry with both legitimate and cross-device duplicate entities
        # 1. Legitimate entity for dev_living
        registry.async_get_or_create("climate", "miraie_in", "dev_living", config_entry=entry)
        registry.async_get_or_create("sensor", "miraie_in", "dev_living_room_temperature", config_entry=entry)

        # 2. Duplicate entities for dev_bedroom and dev_kitchen that were accidentally registered under this entry
        registry.async_get_or_create("climate", "miraie_in", "dev_bedroom", config_entry=entry)
        registry.async_get_or_create("sensor", "miraie_in", "dev_bedroom_room_temperature", config_entry=entry)
        registry.async_get_or_create("climate", "miraie_in", "dev_kitchen", config_entry=entry)

        # Verify pre-cleanup count = 5 entities under entry_living
        entries_before = er.async_entries_for_config_entry(registry, "entry_living")
        self.assertEqual(len(entries_before), 5)

        # Run cleanup
        self.mod_init._cleanup_cross_device_entities(hass, entry, target_dev_id)

        # Verify post-cleanup count = exactly 2 entities (only dev_living remains)
        entries_after = er.async_entries_for_config_entry(registry, "entry_living")
        self.assertEqual(len(entries_after), 2)
        remaining_uids = {e.unique_id for e in entries_after}
        self.assertEqual(remaining_uids, {"dev_living", "dev_living_room_temperature"})

    async def test_cross_device_registry_169_device_cleanup(self):
        """Simulate the exact 169-device registry corruption and verify cleanup down to 13."""
        from homeassistant.helpers import device_registry as dr
        from homeassistant.helpers import entity_registry as er

        hass = MockHass()
        dev_reg = dr.async_get(hass)
        ent_reg = er.async_get(hass)

        # 1. Populate DeviceRegistry and EntityRegistry with 169 cross-device entries
        # (All 13 entries linked to all 13 devices = 13 x 13 = 169 device links)
        for i in range(1, 14):
            entry_id = f"entry_dev_{i}"
            entry = MockEntry(
                entry_id=entry_id,
                data={"device_id": f"dev_{i}"},
            )
            for j in range(1, 14):
                dev_id = f"dev_{j}"
                # Link device j to entry i in DeviceRegistry
                dev_reg.async_get_or_create(
                    config_entry_id=entry_id,
                    identifiers={("miraie_in", dev_id)},
                    name=f"PANASONIC AC {j}",
                )
                # Link entity j to entry i in EntityRegistry
                ent_reg.async_get_or_create("climate", "miraie_in", dev_id, config_entry=entry)

        # Verify pre-cleanup count across all 13 entries = 169 device links and 169 entities
        total_dev_links_before = sum(
            len(dr.async_entries_for_config_entry(dev_reg, f"entry_dev_{i}"))
            for i in range(1, 14)
        )
        self.assertEqual(total_dev_links_before, 169, "Pre-condition: must start with 169 device links")

        # 2. Run self-healing cleanup across all 13 entries
        for i in range(1, 14):
            entry_id = f"entry_dev_{i}"
            target_dev_id = f"dev_{i}"
            entry = MockEntry(
                entry_id=entry_id,
                data={"device_id": target_dev_id},
            )
            self.mod_init._cleanup_cross_device_entities(hass, entry, target_dev_id)

        # 3. Assert post-cleanup state in DeviceRegistry: exactly 1 device per entry (total 13, not 169)
        for i in range(1, 14):
            entry_id = f"entry_dev_{i}"
            target_dev_id = f"dev_{i}"
            entry_devices = dr.async_entries_for_config_entry(dev_reg, entry_id)
            self.assertEqual(
                len(entry_devices),
                1,
                f"Entry {entry_id} must have exactly 1 device in DeviceRegistry, got {len(entry_devices)}"
            )
            # Verify the 1 device is indeed dev_i
            matched_idents = [ident[1] for ident in entry_devices[0].identifiers if ident[0] == "miraie_in"]
            self.assertEqual(matched_idents, [target_dev_id])

        # Assert total device links across the entire system is strictly 13
        total_dev_links_after = sum(
            len(dr.async_entries_for_config_entry(dev_reg, f"entry_dev_{i}"))
            for i in range(1, 14)
        )
        self.assertEqual(
            total_dev_links_after,
            13,
            f"Expected total 13 device links across all entries in DeviceRegistry, got {total_dev_links_after} (169-device bug!)"
        )

    def test_get_devices_for_entry_helper(self):
        """Verify get_devices_for_entry helper behavior under all matching conditions."""
        from custom_components.miraie_in.utils import get_devices_for_entry

        dev1 = MockDevice(device_id="dev_1", friendly_name="Living Room AC")
        dev2 = MockDevice(device_id="dev_2", friendly_name="Bedroom AC")

        mock_hub = MagicMock()
        mock_home = MagicMock()
        mock_home.devices = [dev1, dev2]
        mock_hub.home = mock_home

        # 1. Matching target_id
        entry_dev1 = MockEntry(entry_id="e1", title="Living Room AC", data={"device_id": "dev_1"})
        res = get_devices_for_entry(mock_hub, entry_dev1)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].id, "dev_1")

        # 2. Mismatched target_id -> returns empty list (never falls back to all devices)
        entry_mismatched = MockEntry(entry_id="e_bad", title="Ghost AC", data={"device_id": "dev_99"})
        res = get_devices_for_entry(mock_hub, entry_mismatched)
        self.assertEqual(res, [], "Mismatched device_id must return empty list without falling back")

        # 3. Missing target_id on a multi-device account -> returns empty list (BLOCKS FAN-OUT)
        entry_no_id_multi = MockEntry(entry_id="e_no_id", title="Legacy Multi AC", data={"username": "u@example.com"})
        res = get_devices_for_entry(mock_hub, entry_no_id_multi)
        self.assertEqual(res, [], "Multi-device cloud account missing device_id must return empty list (preventing fanout)")

        # 4. Missing target_id on a single-device account -> safely returns single device
        single_hub = MagicMock()
        single_home = MagicMock()
        single_home.devices = [dev1]
        single_hub.home = single_home
        entry_no_id_single = MockEntry(entry_id="e_single", title="Legacy Single AC", data={"username": "u@example.com"})
        res_single = get_devices_for_entry(single_hub, entry_no_id_single)
        self.assertEqual(len(res_single), 1)
        self.assertEqual(res_single[0].id, "dev_1")

        # 5. Standalone IR entry (is_ir_only) -> returns dummy device safely
        dummy_dev = MockDevice(device_id="manual_1", friendly_name="IR AC")
        ir_hub = MagicMock()
        ir_home = MagicMock()
        ir_home.devices = [dummy_dev]
        ir_hub.home = ir_home
        entry_ir = MockEntry(entry_id="e_ir", title="IR AC", data={"is_ir_only": True})
        res_ir = get_devices_for_entry(ir_hub, entry_ir)
        self.assertEqual(len(res_ir), 1)
        self.assertEqual(res_ir[0].id, "manual_1")

        # 6. Hub is None or invalid -> returns empty list safely
        self.assertEqual(get_devices_for_entry(None, entry_dev1), [])
        self.assertEqual(get_devices_for_entry(object(), entry_dev1), [])

    async def test_shared_session_pool_refcounting_and_unload(self):
        """Verify that sibling entries share a hub/broker and unload ref-counts properly."""
        from tests.ha_stub import MockHass
        from unittest.mock import AsyncMock, patch

        hass = MockHass()
        hass.data = {}
        hass.is_running = True
        hass.async_create_task = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)


        mock_dev1 = MockDevice("dev_1", "Living Room AC")

        mock_dev2 = MockDevice("dev_2", "Bedroom AC")
        devices = [mock_dev1, mock_dev2]

        mock_hub = MagicMock()
        mock_hub.home = MagicMock(devices=devices)
        mock_hub.init = AsyncMock()
        mock_hub.close = AsyncMock()
        mock_hub.background_tasks = []

        entry1 = MockEntry(
            entry_id="entry_1",
            title="Living Room AC",
            data={"username": "user@example.com", "password": "pass", "device_id": "dev_1"},
        )
        entry2 = MockEntry(
            entry_id="entry_2",
            title="Bedroom AC",
            data={"username": "user@example.com", "password": "pass", "device_id": "dev_2"},
        )

        with patch("custom_components.miraie_in.MirAIeHub", return_value=mock_hub), \
             patch("custom_components.miraie_in.MirAIeBroker", return_value=MagicMock()):


            # Setup entry 1
            await self.mod_init.async_setup_entry(hass, entry1)
            self.assertEqual(mock_hub.init.call_count, 1)
            self.assertIn("user@example.com", hass.data["miraie_in"]["sessions"])
            self.assertEqual(hass.data["miraie_in"]["sessions"]["user@example.com"]["entries"], {"entry_1"})

            # Setup entry 2 - should reuse existing hub without calling hub.init again
            await self.mod_init.async_setup_entry(hass, entry2)
            self.assertEqual(mock_hub.init.call_count, 1, "hub.init must only be called once for shared account")
            self.assertEqual(hass.data["miraie_in"]["sessions"]["user@example.com"]["entries"], {"entry_1", "entry_2"})

            # Unload entry 1 - hub should NOT be closed
            with patch.object(hass.config_entries, "async_unload_platforms", AsyncMock(return_value=True)):
                await self.mod_init.async_unload_entry(hass, entry1)
                self.assertEqual(mock_hub.close.call_count, 0, "hub.close must NOT be called while sibling entry is active")
                self.assertEqual(hass.data["miraie_in"]["sessions"]["user@example.com"]["entries"], {"entry_2"})

                # Unload entry 2 - last entry unloads, hub MUST be closed
                await self.mod_init.async_unload_entry(hass, entry2)
                self.assertEqual(mock_hub.close.call_count, 1, "hub.close MUST be called when last entry unloads")
                self.assertNotIn("user@example.com", hass.data["miraie_in"]["sessions"])

    async def test_reauth_sibling_propagation(self):
        """Verify reauth updates all sibling config entries sharing the same username."""
        from custom_components.miraie_in.config_flow import ConfigFlow
        from tests.ha_stub import MockHass
        from unittest.mock import AsyncMock, patch

        hass = MockHass()
        flow = ConfigFlow()
        flow.hass = hass

        entry1 = MockEntry(
            entry_id="entry_1",
            title="Living Room AC",
            data={"username": "old_user@example.com", "password": "old_password", "device_id": "dev_1"},
        )
        entry2 = MockEntry(
            entry_id="entry_2",
            title="Bedroom AC",
            data={"username": "old_user@example.com", "password": "old_password", "device_id": "dev_2"},
        )

        hass.config_entries.async_entries = MagicMock(return_value=[entry1, entry2])
        hass.config_entries.async_update_entry = MagicMock()
        hass.config_entries.async_reload = AsyncMock()

        flow._reauth_entry = entry1

        with patch("custom_components.miraie_in.config_flow.validate_input", AsyncMock(return_value=({}, []))):
            res = await flow.async_step_reauth_confirm(
                {"username": "new_user@example.com", "password": "new_password"}
            )
            self.assertEqual(res["type"], "abort")
            self.assertEqual(res["reason"], "reauth_successful")
            self.assertEqual(hass.config_entries.async_update_entry.call_count, 2, "Both sibling entries must be updated on reauth")
            self.assertEqual(hass.config_entries.async_reload.call_count, 2, "Both sibling entries must be reloaded")

    async def test_incremental_device_onboarding(self):
        """Verify newly discovered AC on existing account can be onboarded."""
        from custom_components.miraie_in.config_flow import ConfigFlow
        from unittest.mock import AsyncMock, patch

        flow = ConfigFlow()
        flow.hass = MagicMock()

        existing_entry = MockEntry(
            entry_id="entry_1",
            title="Living Room AC",
            data={"username": "user@example.com", "device_id": "dev_1"},
        )
        flow._async_current_entries = MagicMock(return_value=[existing_entry])

        discovered = [
            {"id": "dev_1", "name": "Living Room AC", "model_code": "CS-CU-RU18CKY"},
            {"id": "dev_2", "name": "New Guest AC", "model_code": "CS-CU-RU18CKY"},
        ]

        with patch("custom_components.miraie_in.config_flow.validate_input", AsyncMock(return_value=({}, discovered))):
            res = await flow.async_step_cloud_account(
                {"username": "user@example.com", "password": "password123"}
            )
            self.assertEqual(res["type"], "form")
            self.assertEqual(res["step_id"], "cloud_devices")
            self.assertEqual(len(flow._discovered_cloud_devices), 1)
            self.assertEqual(flow._discovered_cloud_devices[0]["id"], "dev_2", "Only unconfigured dev_2 should be queued for setup")




if __name__ == "__main__":
    unittest.main()

