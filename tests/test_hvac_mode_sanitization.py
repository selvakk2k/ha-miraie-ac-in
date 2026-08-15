"""Unit test verifying that short frame names (powerful, clean, converti) never produce invalid HVACMode values."""
from tests.ha_stub import setup_ha_stubs
setup_ha_stubs()

import unittest
from unittest.mock import MagicMock
from homeassistant.components.climate import HVACMode


class TestHVACModeSanitization(unittest.TestCase):
    def test_hvac_mode_validity(self):
        from custom_components.miraie_in.coordinator import MirAIeDeviceCoordinator
        from custom_components.miraie_in.climate import MirAIeClimate

        mock_dev = MagicMock()
        mock_dev.id = "dev1"
        mock_dev.friendly_name = "Living Room AC"
        mock_dev.status.is_online = True
        mock_dev.status.power_mode.value = "on"
        mock_dev.status.hvac_mode.value = "cool"
        mock_dev.status.temperature = 24

        coord = MirAIeDeviceCoordinator(MagicMock(), mock_dev, "remote.blaster", "CS-CU-RU18CKY-1", True)
        coord.state["mode"] = "cool"
        coord.state["power"] = "on"

        climate = MirAIeClimate(mock_dev, coord)

        valid_modes = [m.value for m in HVACMode]

        # 1. Powerful / Boost
        coord.async_optimistic_update(mode="powerful")
        self.assertIn(climate.hvac_mode, valid_modes)
        self.assertNotIn(climate.hvac_mode, ["powerful", "boost"])

        # 2. Converti Step (e.g. converti_80)
        coord.async_optimistic_update(mode="converti_80")
        self.assertIn(climate.hvac_mode, valid_modes)
        self.assertNotEqual(climate.hvac_mode, "converti_80")

        # 3. Clean
        coord.async_optimistic_update(mode="clean")
        self.assertIn(climate.hvac_mode, valid_modes)
        self.assertNotEqual(climate.hvac_mode, "clean")


if __name__ == "__main__":
    unittest.main()
