"""Unit tests for AC vs non-AC device filtering."""
import unittest
from types import SimpleNamespace

from tests.ha_stub import setup_ha_stubs
setup_ha_stubs()

from custom_components.miraie_in.utils import is_ac_device


class TestACDeviceFilter(unittest.TestCase):
    """Test suite for validating AC device detection and non-AC device exclusion."""

    def test_ac_categories_identified_correctly(self):
        """Verify standard AC categories return True."""
        for cat in ["RAC", "PAC", "AC", "SAC", "CAC", "AIR_CONDITIONER"]:
            self.assertTrue(is_ac_device({"category": cat, "deviceName": "Room AC"}))
            self.assertTrue(is_ac_device({"deviceType": cat, "deviceName": "Room AC"}))

    def test_non_ac_categories_excluded(self):
        """Verify non-AC categories (plugs, geysers, switches, fans) return False."""
        for cat in ["PLUG", "SMART_PLUG", "SWITCH", "SMART_SWITCH", "FAN", "WATER_HEATER", "WH", "GEYSER", "REF", "WM"]:
            self.assertFalse(is_ac_device({"category": cat, "deviceName": "Smart Appliance"}))
            self.assertFalse(is_ac_device({"deviceType": cat, "deviceName": "Smart Appliance"}))

    def test_ac_model_number_detection(self):
        """Verify Panasonic AC model number prefixes identify ACs even if category is ambiguous."""
        self.assertTrue(is_ac_device({"modelNumber": "CS-CU-RU18CKY-1", "deviceName": "Living Room AC"}))
        self.assertTrue(is_ac_device({"modelNumber": "CW-XN181AM", "deviceName": "Window AC"}))
        self.assertTrue(is_ac_device({"modelNumber": "KN12AKY", "deviceName": "Fixed Speed AC"}))

    def test_device_object_with_details(self):
        """Verify Device object instances with details attribute work correctly."""
        ac_dev = SimpleNamespace(details=SimpleNamespace(category="RAC", model_number="CS-CU-NU18WKYX"))
        self.assertTrue(is_ac_device(ac_dev))

        plug_dev = SimpleNamespace(details=SimpleNamespace(category="PLUG", model_number="P-PLUG-16A"))
        self.assertFalse(is_ac_device(plug_dev))


if __name__ == "__main__":
    unittest.main()
