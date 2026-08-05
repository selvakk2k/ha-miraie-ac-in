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


if __name__ == "__main__":
    unittest.main()
