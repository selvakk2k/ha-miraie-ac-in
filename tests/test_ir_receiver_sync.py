"""Unit tests for IR Receiver state synchronization, echo suppression, and physical remote decoding."""
import asyncio
import time
import unittest
from unittest.mock import MagicMock, patch

from tests.ha_stub import setup_ha_stubs
setup_ha_stubs()

from homeassistant.core import HomeAssistant
from custom_components.miraie_in.coordinator import MirAIeDeviceCoordinator
from custom_components.miraie_in.panasonic_ac_models import generate_ir_code


class TestIRReceiverSync(unittest.TestCase):
    """Test suite for IR Receiver listening and state synchronization."""

    def setUp(self):
        self.hass = MagicMock(spec=HomeAssistant)
        self.hass.states = MagicMock()
        self.listeners = {}

        def mock_track_state_change(hass, entity_ids, action):
            for ent in entity_ids:
                self.listeners[ent] = action
            return lambda: [self.listeners.pop(ent, None) for ent in entity_ids]

        self.patcher = patch(
            "homeassistant.helpers.event.async_track_state_change_event",
            side_effect=mock_track_state_change,
        )
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_ir_receiver_state_sync_full_frame(self):
        """Verify receiving a physical remote full-frame updates coordinator state."""
        coordinator = MirAIeDeviceCoordinator(
            hass=self.hass,
            entry_id="test_entry",
            device_id="ac_living_room",
            model_code="CS-CU-RU18CKY-1",
            has_wifi=True,
            receiver_entity_id="sensor.ir_rx",
        )
        coordinator.async_setup_receiver()
        self.assertIn("sensor.ir_rx", self.listeners)

        updated = False
        def on_update():
            nonlocal updated
            updated = True

        coordinator.async_add_listener(on_update)

        # Generate a Cool 22°C, High Fan, V2 Vane IR frame
        ir = generate_ir_code(mode="cool", target_temp=22, fan="high", v_vane="V2", h_vane="H0", series="EU")

        # Simulate incoming state change from sensor.ir_rx
        event = MagicMock()
        event.data = {
            "new_state": MagicMock(state=ir["aeha_hex"], attributes={})
        }

        # Fire listener callback
        self.listeners["sensor.ir_rx"](event)

        self.assertTrue(updated)
        self.assertEqual(coordinator.state["power"], "on")
        self.assertEqual(coordinator.state["mode"], "cool")
        self.assertEqual(coordinator.state["temperature"], 22)
        self.assertEqual(coordinator.state["fan_speed"], "high")
        self.assertEqual(coordinator.state["v_vane"], "V2")
        self.assertEqual(coordinator.state["last_controlled_by"], "IR Remote")

    def test_ir_receiver_echo_suppression(self):
        """Verify received IR signals within 1.5s of transmission are suppressed as echos."""
        coordinator = MirAIeDeviceCoordinator(
            hass=self.hass,
            entry_id="test_entry",
            device_id="ac_living_room",
            model_code="CS-CU-RU18CKY-1",
            has_wifi=True,
            receiver_entity_id="sensor.ir_rx",
        )
        coordinator.async_setup_receiver()

        # Simulate transmission happened 0.5s ago
        coordinator._last_ir_command_timestamp = time.monotonic()
        initial_temp = coordinator.state["temperature"]

        # Receiver hears a command with a different temperature (e.g. 18°C)
        ir = generate_ir_code(mode="cool", target_temp=18, fan="low", series="EU")
        event = MagicMock()
        event.data = {
            "new_state": MagicMock(state=ir["aeha_hex"], attributes={})
        }

        self.listeners["sensor.ir_rx"](event)

        # Echo suppression must prevent state from updating
        self.assertEqual(coordinator.state["temperature"], initial_temp)

        # Simulate 2.0s passed
        coordinator._last_ir_command_timestamp = time.monotonic() - 2.0
        self.listeners["sensor.ir_rx"](event)

        # Now it is accepted and state updates to 18°C
        self.assertEqual(coordinator.state["temperature"], 18)

    def test_ir_receiver_state_sync_from_attributes(self):
        """Verify receiving code in attributes when state is an ISO timestamp (like native infrared entities)."""
        coordinator = MirAIeDeviceCoordinator(
            hass=self.hass,
            entry_id="test_entry",
            device_id="ac_living_room",
            model_code="CS-CU-RU18CKY-1",
            has_wifi=True,
            receiver_entity_id="infrared.ir_rx",
        )
        coordinator.async_setup_receiver()
        self.assertIn("infrared.ir_rx", self.listeners)

        # Generate a Cool 24°C, Mid Fan IR frame
        ir = generate_ir_code(mode="cool", target_temp=24, fan="medium", series="EU")

        # Simulate state being a timestamp and code stored in attributes["data"]
        event = MagicMock()
        event.data = {
            "new_state": MagicMock(
                state="2026-08-26T02:05:00+00:00",
                attributes={"data": ir["aeha_hex"]}
            )
        }

        self.listeners["infrared.ir_rx"](event)
        self.assertEqual(coordinator.state["temperature"], 24)
        self.assertEqual(coordinator.state["fan_speed"], "medium")
        self.assertEqual(coordinator.state["last_controlled_by"], "IR Remote")

    def test_ir_receiver_short_frame_actions(self):
        """Verify dedicated 16-byte short-frame actions update presets and display."""
        coordinator = MirAIeDeviceCoordinator(
            hass=self.hass,
            entry_id="test_entry",
            device_id="ac_living_room",
            model_code="CS-CU-RU18CKY-1",
            has_wifi=True,
            receiver_entity_id="sensor.ir_rx",
        )
        coordinator.async_setup_receiver()

        # 1. Powerful Mode
        pow_ir = generate_ir_code(mode="powerful")
        event_pow = MagicMock()
        event_pow.data = {"new_state": MagicMock(state=pow_ir["aeha_hex"], attributes={})}
        coordinator._last_ir_command_timestamp = 0
        self.listeners["sensor.ir_rx"](event_pow)
        self.assertEqual(coordinator.state["active_preset"], "powerful")

        # 2. Converti 80%
        c80_ir = generate_ir_code(mode="converti_80")
        event_c80 = MagicMock()
        event_c80.data = {"new_state": MagicMock(state=c80_ir["aeha_hex"], attributes={})}
        coordinator._last_ir_command_timestamp = 0
        self.listeners["sensor.ir_rx"](event_c80)
        self.assertEqual(coordinator.state["active_preset"], "cv_80")
        self.assertEqual(coordinator.state["converti"], "cv_80")

        # 3. Clean
        clean_ir = generate_ir_code(mode="clean")
        event_clean = MagicMock()
        event_clean.data = {"new_state": MagicMock(state=clean_ir["aeha_hex"], attributes={})}
        coordinator._last_ir_command_timestamp = 0
        self.listeners["sensor.ir_rx"](event_clean)
        self.assertEqual(coordinator.state["active_preset"], "clean")

    def test_ir_receiver_unload(self):
        """Verify async_unload cleanly unsubscribes the receiver listener."""
        coordinator = MirAIeDeviceCoordinator(
            hass=self.hass,
            entry_id="test_entry",
            device_id="ac_living_room",
            model_code="CS-CU-RU18CKY-1",
            has_wifi=True,
            receiver_entity_id="sensor.ir_rx",
        )
        coordinator.async_setup_receiver()
        self.assertIn("sensor.ir_rx", self.listeners)

        coordinator.async_unload()
        self.assertNotIn("sensor.ir_rx", self.listeners)

    def test_rapid_successive_physical_presses_not_dropped(self):
        """Verify that two genuine physical remote presses in rapid succession (< 1.5s) are both applied."""
        coordinator = MirAIeDeviceCoordinator(
            hass=self.hass,
            entry_id="test_entry",
            device_id="ac_living_room",
            model_code="CS-CU-RU18CKY-1",
            has_wifi=True,
            receiver_entity_id="sensor.ir_rx",
        )
        coordinator.async_setup_receiver()

        # 1. First physical remote press: Cool 24°C
        ir1 = generate_ir_code(mode="cool", target_temp=24, fan="low", series="EU")
        event1 = MagicMock()
        event1.data = {"new_state": MagicMock(state=ir1["aeha_hex"], attributes={})}
        self.listeners["sensor.ir_rx"](event1)
        self.assertEqual(coordinator.state["temperature"], 24)
        self.assertEqual(coordinator.state["last_controlled_by"], "IR Remote")

        # 2. Second physical remote press 0.5s later: Cool 25°C (no transmission occurred in between)
        ir2 = generate_ir_code(mode="cool", target_temp=25, fan="low", series="EU")
        event2 = MagicMock()
        event2.data = {"new_state": MagicMock(state=ir2["aeha_hex"], attributes={})}
        self.listeners["sensor.ir_rx"](event2)

        # Must NOT be dropped by echo suppression
        self.assertEqual(coordinator.state["temperature"], 25)
        self.assertEqual(coordinator.state["last_controlled_by"], "IR Remote")

    def test_native_infrared_receiver_subscription(self):
        """Verify native infrared.helpers.async_subscribe_receiver callback processes raw timings."""
        native_sub_callback = None

        def mock_subscribe(hass, entity_id, cb):
            nonlocal native_sub_callback
            native_sub_callback = cb
            return lambda: None

        with patch("homeassistant.components.infrared.helpers.async_subscribe_receiver", side_effect=mock_subscribe):
            coordinator = MirAIeDeviceCoordinator(
                hass=self.hass,
                entry_id="test_entry",
                device_id="ac_living_room",
                model_code="CS-CU-RU18CKY-1",
                has_wifi=True,
                receiver_entity_id="infrared.living_room_receiver",
            )
            coordinator.async_setup_receiver()
            self.assertIsNotNone(native_sub_callback)

            # Generate raw pulses for Cool 23°C
            ir = generate_ir_code(mode="cool", target_temp=23, fan="low", series="EU")
            signal_mock = MagicMock()
            signal_mock.timings = ir["raw"]

            native_sub_callback(signal_mock)
            self.assertEqual(coordinator.state["temperature"], 23)
            self.assertEqual(coordinator.state["last_controlled_by"], "IR Remote")


if __name__ == "__main__":
    unittest.main()
