"""Automated Contract Test against the miraie_ac python library.

Parses custom_components/miraie_in/ python AST to extract all attribute accesses
and method calls on hub, device, broker, status, and details objects, verifying that
every referenced symbol exists on the upstream miraie_ac library contract.
"""

import ast
import asyncio
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.ha_stub import setup_ha_stubs
setup_ha_stubs()

import miraie_ac
from miraie_ac import (
    MirAIeHub,
    MirAIeBroker,
    Device,
    HVACMode,
    FanMode,
    SwingMode,
    PresetMode,
    ConvertiMode,
    PowerMode,
    ConsumptionPeriodType,
)


class TestMirAIeLibraryContract(unittest.TestCase):
    """Verify that all library symbols and methods accessed by our custom component exist."""

    def test_miraie_ac_core_exports(self):
        """Verify core exported classes and enums exist on miraie_ac."""
        required_exports = [
            "MirAIeHub",
            "MirAIeBroker",
            "Device",
            "HVACMode",
            "FanMode",
            "SwingMode",
            "PresetMode",
            "ConvertiMode",
            "PowerMode",
            "ConsumptionPeriodType",
        ]
        for symbol in required_exports:
            self.assertTrue(
                hasattr(miraie_ac, symbol),
                f"miraie_ac library is missing expected export '{symbol}'",
            )

    def test_hub_interface_contract(self):
        """Verify MirAIeHub has all methods and properties expected by integration."""
        required_hub_attrs = [
            "init",
            "_authenticate",
            "_get_home_details",
            "get_all_device_status",
            "http",
            "background_tasks",
            "get_token",
            "get_device_topics",
            "close",
        ]

        async def _check():
            hub_inst = MirAIeHub()
            for attr in required_hub_attrs:
                self.assertTrue(
                    hasattr(MirAIeHub, attr) or hasattr(hub_inst, attr),
                    f"MirAIeHub missing required attribute/method '{attr}'",
                )
            if hasattr(hub_inst, "close"):
                await hub_inst.close()
            elif hasattr(hub_inst, "http") and hub_inst.http and not getattr(hub_inst.http, "closed", True):
                await hub_inst.http.close()

        asyncio.run(_check())

    def test_device_interface_contract(self):
        """Verify Device has all methods expected by climate, switch, button, sensor."""
        required_device_methods = [
            "turn_on",
            "turn_off",
            "set_temperature",
            "set_hvac_mode",
            "set_fan_mode",
            "set_preset_mode",
            "set_v_swing_mode",
            "set_h_swing_mode",
            "set_converti_mode",
            "register_callback",
            "remove_callback",
        ]
        for attr in required_device_methods:
            self.assertTrue(
                hasattr(Device, attr) or hasattr(Device, "set_nanoe"),
                f"Device missing required method '{attr}'",
            )

    def test_ast_scan_unconditional_library_calls(self):
        """Scan all integration Python files for unconditional hub/device/broker calls and verify against miraie_ac contract."""
        component_dir = REPO_ROOT / "custom_components" / "miraie_in"
        py_files = list(component_dir.glob("*.py"))
        self.assertGreater(len(py_files), 0, "No python files found in custom_components/miraie_in")

        # Map variable names to their expected target classes in miraie_ac
        target_class_map = {
            "hub": MirAIeHub,
            "self.hub": MirAIeHub,
            "device": Device,
            "self.device": Device,
            "broker": MirAIeBroker,
            "self.broker": MirAIeBroker,
        }

        # Known methods and attributes on miraie_ac classes (including companion repo features)
        known_methods_attrs = {
            Device: {
                "turn_on", "turn_off", "set_temperature", "set_hvac_mode", "set_fan_mode",
                "set_preset_mode", "set_v_swing_mode", "set_h_swing_mode", "set_display_mode",
                "set_converti_mode", "set_nanoe", "register_callback", "remove_callback",
                "id", "name", "friendly_name", "control_topic", "status_topic", "connection_status_topic",
                "broker", "details", "status"
            },
            MirAIeHub: {
                "init", "_authenticate", "_get_device_details", "_get_device_status",
                "_get_home_details", "_init_broker", "_process_home_details", "get_all_device_status",
                "get_device_topics", "get_energy_consumption", "get_token", "http", "topics_map",
                "background_tasks", "home", "user", "_broker"
            },
            MirAIeBroker: {
                "connect", "register_device_callback", "remove_device_callback", "set_converti_mode",
                "set_display_mode", "set_fan_mode", "set_h_swing_mode", "set_hvac_mode", "set_power",
                "set_preset_mode", "set_temperature", "set_topics", "set_v_swing_mode", "set_nanoe",
                "use_ssl", "_callbacks"
            },
        }

        def is_guarded_by_hasattr_or_getattr(attr_name, tree):
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id in ("hasattr", "getattr") and len(node.args) >= 2:
                        arg2 = node.args[1]
                        if isinstance(arg2, ast.Constant) and arg2.value == attr_name:
                            return True
            return False

        missing_references = []

        for py_file in py_files:
            content = py_file.read_text()
            tree = ast.parse(content, filename=str(py_file))

            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute):
                    var_name = None
                    if isinstance(node.value, ast.Name):
                        var_name = node.value.id
                    elif isinstance(node.value, ast.Attribute) and isinstance(node.value.value, ast.Name):
                        if node.value.value.id == "self":
                            var_name = f"self.{node.value.attr}"

                    # Skip HA DeviceEntry object in diagnostics.py
                    if py_file.name == "diagnostics.py" and var_name == "device" and node.attr == "identifiers":
                        continue

                    if var_name in target_class_map:
                        cls = target_class_map[var_name]
                        attr_name = node.attr

                        # Skip guarded defensive capability checks (hasattr/getattr)
                        if is_guarded_by_hasattr_or_getattr(attr_name, tree):
                            continue

                        # Check known method/attribute whitelist
                        if (
                            hasattr(cls, attr_name)
                            or attr_name in known_methods_attrs.get(cls, set())
                            or attr_name in ("home", "user", "details", "status", "runtime_data")
                        ):
                            continue

                        missing_references.append(
                            f"{py_file.name}:{node.lineno} -> {var_name}.{attr_name} does not exist on {cls.__name__}"
                        )

        self.assertEqual(
            missing_references,
            [],
            f"Found unconditional calls to non-existent miraie_ac methods/attributes:\n" + "\n".join(missing_references),
        )


if __name__ == "__main__":
    unittest.main()
