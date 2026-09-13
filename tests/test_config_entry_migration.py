"""Unit test verifying Config Entry Migration from v1 to v2."""
import unittest
from unittest.mock import MagicMock, patch

from tests.ha_stub import setup_ha_stubs
setup_ha_stubs()


class TestConfigEntryMigration(unittest.IsolatedAsyncioTestCase):
    async def test_migrate_v1_cloud_entry(self):
        from custom_components.miraie_in import async_migrate_entry

        hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.version = 1
        mock_entry.entry_id = "test_entry_123"
        mock_entry.data = {"username": "selvakk@gmail.com", "password": "secret_password"}
        mock_entry.options = {
            "install_date": "2024-03-01",
            "blaster_entity_id": "infrared.room_2_blaster",
            "primary_backend": "cloud",
        }

        res = await async_migrate_entry(hass, mock_entry)
        self.assertTrue(res)
        hass.config_entries.async_update_entry.assert_called_with(mock_entry, version=2)

    async def test_migrate_v1_ir_entry(self):
        from custom_components.miraie_in import async_migrate_entry

        hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.version = 1
        mock_entry.entry_id = "test_ir_entry_456"
        mock_entry.data = {"is_ir_only": True, "name": "Living Room AC", "model_code": "CS-CU-RU18CKY-1"}
        mock_entry.options = {
            "blaster_entity_id": "infrared.living_room_blaster",
            "primary_backend": "ir",
        }

        res = await async_migrate_entry(hass, mock_entry)
        self.assertTrue(res)
        hass.config_entries.async_update_entry.assert_called_with(mock_entry, version=2)

    async def test_auto_split_preserves_install_date_and_options(self):
        from custom_components.miraie_in import async_setup_entry
        from unittest.mock import patch, AsyncMock
        import asyncio

        hass = MagicMock()
        hass.config_entries.async_entries.return_value = []

        mock_entry = MagicMock()
        mock_entry.entry_id = "legacy_parent_entry_789"
        mock_entry.version = 2
        mock_entry.data = {"username": "test@example.com", "password": "password"}
        mock_entry.options = {
            "install_date": "2024-01-15",
            "devices": {
                "dev_living": {
                    "install_date": "2023-11-01",
                    "blaster_entity_id": "remote.living_blaster",
                    "primary_backend": "ir",
                }
            }
        }

        mock_dev1 = MagicMock(id="dev_living", friendly_name="Living Room AC")
        mock_dev1.details = MagicMock(model_number="CS-CU-RU18CKY-1")
        mock_dev2 = MagicMock(id="dev_bedroom", friendly_name="Bedroom AC")
        mock_dev2.details = MagicMock(model_number="CS-CU-KN18YKY")

        mock_hub = MagicMock()
        mock_hub.init = AsyncMock(return_value=None)
        mock_hub.home = MagicMock(devices=[mock_dev1, mock_dev2])

        created_tasks = []
        def fake_create_task(coro):
            created_tasks.append(coro)

        hass.async_create_task.side_effect = fake_create_task
        hass.config_entries.flow.async_init = AsyncMock(return_value={"type": "create_entry"})
        hass.config_entries.async_remove = AsyncMock(return_value=None)

        with patch("custom_components.miraie_in.MirAIeHub", return_value=mock_hub), \
             patch("custom_components.miraie_in.MirAIeBroker", return_value=MagicMock()):
            res = await async_setup_entry(hass, mock_entry)
            self.assertTrue(res)

        # Run all scheduled tasks
        for t in created_tasks:
            if asyncio.iscoroutine(t):
                await t

        # Verify flow.async_init calls with preserved options
        calls = hass.config_entries.flow.async_init.call_args_list
        self.assertEqual(len(calls), 2)

        # First device: specific options
        self.assertEqual(calls[0][1]["data"]["device_id"], "dev_living")
        self.assertEqual(calls[0][1]["data"]["options"]["install_date"], "2023-11-01")
        self.assertEqual(calls[0][1]["data"]["options"]["blaster_entity_id"], "remote.living_blaster")
        self.assertEqual(calls[0][1]["data"]["options"]["primary_backend"], "ir")

        # Second device: inherits parent level install_date
        self.assertEqual(calls[1][1]["data"]["device_id"], "dev_bedroom")
        self.assertEqual(calls[1][1]["data"]["options"]["install_date"], "2024-01-15")

        # Verify parent entry was scheduled for removal
        hass.config_entries.async_remove.assert_called_with("legacy_parent_entry_789")

    async def test_auto_split_partial_failure_preserves_parent(self):
        from custom_components.miraie_in import async_setup_entry
        from unittest.mock import patch, AsyncMock
        import asyncio

        hass = MagicMock()
        hass.config_entries.async_entries.return_value = []

        mock_entry = MagicMock()
        mock_entry.entry_id = "legacy_parent_entry_fail"
        mock_entry.version = 2
        mock_entry.data = {"username": "test@example.com", "password": "password"}
        mock_entry.options = {}

        mock_dev1 = MagicMock(id="dev_1", friendly_name="AC 1")
        mock_dev1.details = MagicMock(model_number="CS-CU-RU18CKY-1")
        mock_dev2 = MagicMock(id="dev_2", friendly_name="AC 2")
        mock_dev2.details = MagicMock(model_number="CS-CU-KN18YKY")

        mock_hub = MagicMock()
        mock_hub.init = AsyncMock(return_value=None)
        mock_hub.home = MagicMock(devices=[mock_dev1, mock_dev2])

        hass.config_entries.async_remove = AsyncMock(return_value=None)

        # First device succeeds, second device fails
        side_effects = [{"type": "create_entry"}, Exception("Network timeout during import")]
        hass.config_entries.flow.async_init = AsyncMock(side_effect=side_effects)

        with patch("custom_components.miraie_in.MirAIeHub", return_value=mock_hub), \
             patch("custom_components.miraie_in.MirAIeBroker", return_value=MagicMock()):
            res = await async_setup_entry(hass, mock_entry)
            self.assertFalse(res)

        # Parent entry must NOT be removed on failure
        hass.config_entries.async_remove.assert_not_called()

    async def test_v1_to_v2_migration_with_orphan_buzzer_pruning(self):
        """Verify direct v1 to v2 migration prunes orphaned buzzer entities for unsupported models."""
        from custom_components.miraie_in.switch import async_setup_entry as async_setup_switch
        from custom_components.miraie_in.const import DOMAIN

        hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.data = {"device_id": "dev_migrated", "is_ir_only": False}

        mock_hub = MagicMock()
        mock_entry.runtime_data = mock_hub

        dev = MagicMock(id="dev_migrated", friendly_name="Migrated AC")
        dev.details = MagicMock(model_number="CS-CU-EU18CKY5XFM", brand="Panasonic", firmware_version="3.02")
        dev.status = MagicMock(is_online=True, buzzer=False)

        coord = MagicMock()
        coord.has_wifi = True
        coord.blaster_entity_id = None
        coord.capabilities = {"has_buzzer": False, "h_vane_enabled": 1}
        coord.state = {"buzzer": False}

        mock_hub.home = MagicMock(devices=[dev])
        mock_hub.coordinators = {"dev_migrated": coord}

        mock_ent_reg = MagicMock()
        # Simulate legacy entity in registry created under v1.x
        mock_ent_reg.async_get_entity_id.return_value = "switch.migrated_ac_buzzer"

        with patch("custom_components.miraie_in.switch.er.async_get", return_value=mock_ent_reg):
            entities = []
            await async_setup_switch(hass, mock_entry, lambda ents: entities.extend(ents))

            # Verify no buzzer switch was created
            buzzer_ents = [e for e in entities if e._attr_translation_key == "buzzer"]
            self.assertEqual(len(buzzer_ents), 0)

            # Verify orphaned buzzer switch from v1.x was pruned
            mock_ent_reg.async_remove.assert_called_with("switch.migrated_ac_buzzer")


if __name__ == "__main__":
    unittest.main()
