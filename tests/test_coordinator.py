import unittest
from pathlib import Path
import sys

# Ensure ha_stub is loaded
LOCAL_MIRAIE_AC = Path("/home/skk/Documents/GitHub/miraie-ac")
LOCAL_PANASONIC_MODELS = Path("/home/skk/Documents/GitHub/panasonic-ac-models")

if str(LOCAL_MIRAIE_AC) not in sys.path and LOCAL_MIRAIE_AC.exists():
    sys.path.insert(0, str(LOCAL_MIRAIE_AC))

if str(LOCAL_PANASONIC_MODELS) not in sys.path and LOCAL_PANASONIC_MODELS.exists():
    sys.path.insert(0, str(LOCAL_PANASONIC_MODELS))

from tests.ha_stub import setup_ha_stubs
setup_ha_stubs()

from custom_components.miraie_in.coordinator import MirAIeDeviceCoordinator

class MockServiceRegistry:
    def __init__(self):
        self.calls = []

    async def async_call(self, domain, service, service_data, blocking=True):
        self.calls.append({
            "domain": domain,
            "service": service,
            "service_data": service_data,
        })
        return True

class MockHass:
    def __init__(self):
        self.services = MockServiceRegistry()
        self.states = {}

class TestCoordinatorIRDispatch(unittest.IsolatedAsyncioTestCase):
    async def test_infrared_domain_dispatch(self):
        hass = MockHass()
        coord = MirAIeDeviceCoordinator(
            hass=hass,
            subentry_id="sub_123",
            device_id="dev_456",
            model_code="CS-CU-RU18CKY-1",
            has_wifi=False,
            blaster_entity_id="infrared.living_room_ir_transmitter"
        )

        success = await coord.async_dispatch_ir_command(mode="cool", target_temp=24, fan="low")
        self.assertTrue(success)

        # Test remote domain service call
        coord_remote = MirAIeDeviceCoordinator(
            hass=hass,
            subentry_id="sub_123",
            device_id="dev_456",
            model_code="CS-CU-RU18CKY-1",
            has_wifi=False,
            blaster_entity_id="remote.living_room_blaster"
        )
        success_remote = await coord_remote.async_dispatch_ir_command(mode="cool", target_temp=24, fan="low")
        self.assertTrue(success_remote)
        self.assertEqual(len(hass.services.calls), 1)
        call = hass.services.calls[0]
        self.assertEqual(call["domain"], "remote")
        self.assertEqual(call["service"], "send_command")
        self.assertEqual(call["service_data"]["entity_id"], "remote.living_room_blaster")

    async def test_cloud_update_grace_window_power_and_display(self):
        import asyncio
        hass = MockHass()
        coord = MirAIeDeviceCoordinator(
            hass=hass,
            entry_id="entry_123",
            device_id="dev_456",
            model_code="CS-CU-RU18CKY-1",
            has_wifi=True,
            primary_backend="ir",
            blaster_entity_id="remote.living_room_blaster",
        )

        # Optimistically turn power ON and display ON
        coord.async_optimistic_update(mode="cool", target_temp=24, display=True, origin="IR")
        coord._last_ir_command_timestamp = asyncio.get_event_loop().time()
        self.assertEqual(coord.state["power"], "on")
        self.assertEqual(coord.state["display"], "on")

        # Stale cloud update arriving within grace window reflecting old "off" states
        await coord.async_handle_cloud_update({"pwr": "off", "acdc": "off", "tset": 26})

        # Grace window must protect power and display and temp from being overwritten by stale payload
        self.assertEqual(coord.state["power"], "on")
        self.assertEqual(coord.state["display"], "on")
        self.assertEqual(coord.state["temperature"], 24)

        # Simulate expiration of grace window (> 8.0s ago)
        coord._last_ir_command_timestamp = asyncio.get_event_loop().time() - 10.0
        await coord.async_handle_cloud_update({"pwr": "off", "acdc": "off"})
        self.assertEqual(coord.state["power"], "off")
        self.assertEqual(coord.state["display"], "off")

    async def test_blaster_reconnect_resync_success(self):
        import time
        from unittest.mock import patch, AsyncMock, MagicMock
        from homeassistant.core import Event

        hass = MockHass()
        coord = MirAIeDeviceCoordinator(
            hass=hass,
            entry_id="entry_ir_123",
            device_id="dev_ir_456",
            model_code="CS-CU-RU18CKY-1",
            has_wifi=False,
            primary_backend="ir",
            blaster_entity_id="infrared.living_room_blaster",
        )
        coord._is_esphome_blaster = True

        # 1. Dispatch command (Cool 22C, Fan Low)
        with patch.object(coord, "async_dispatch_ir_command", wraps=coord.async_dispatch_ir_command):
            await coord.async_dispatch_ir_command(mode="cool", target_temp=22, fan="low", origin="HA UI")
            self.assertEqual(coord._last_ir_command_source, "HA UI")
            self.assertEqual(coord._last_requested_ir_params["target_temp"], 22)
            self.assertEqual(coord._last_requested_ir_params["mode"], "cool")

        # 2. Simulate blaster reconnect event (unavailable -> available)
        event = MagicMock(spec=Event)
        event.data = {
            "old_state": MagicMock(state="unavailable"),
            "new_state": MagicMock(state="available"),
        }

        with patch.object(coord, "async_dispatch_ir_command", new_callable=AsyncMock) as mock_dispatch, patch(
            "custom_components.miraie_in.coordinator.asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep:
            mock_dispatch.return_value = True
            await coord._async_blaster_state_changed(event)

            mock_sleep.assert_called_once_with(0.3)
            mock_dispatch.assert_called_once()
            call_kwargs = mock_dispatch.call_args[1]
            self.assertEqual(call_kwargs["target_temp"], 22)
            self.assertEqual(call_kwargs["mode"], "cool")
            self.assertEqual(call_kwargs["origin"], "Blaster Reconnect Resync")
            # Action is consumed
            self.assertIsNone(coord._last_requested_ir_params)

    async def test_blaster_reconnect_ttl_discard(self):
        import time
        from unittest.mock import patch, AsyncMock, MagicMock
        from homeassistant.core import Event

        hass = MockHass()
        coord = MirAIeDeviceCoordinator(
            hass=hass,
            entry_id="entry_ir_123",
            device_id="dev_ir_456",
            model_code="CS-CU-RU18CKY-1",
            has_wifi=False,
            primary_backend="ir",
            blaster_entity_id="infrared.living_room_blaster",
        )

        # Simulate command issued 200 seconds ago (> 180s TTL)
        coord._last_ir_command_source = "HA UI"
        coord._last_ir_command_timestamp = time.monotonic() - 200.0
        coord._last_requested_ir_params = {"mode": "cool", "target_temp": 20}

        event = MagicMock(spec=Event)
        event.data = {
            "old_state": MagicMock(state="unavailable"),
            "new_state": MagicMock(state="available"),
        }

        with patch.object(coord, "async_dispatch_ir_command", new_callable=AsyncMock) as mock_dispatch:
            await coord._async_blaster_state_changed(event)
            mock_dispatch.assert_not_called()

    async def test_blaster_reconnect_physical_remote_precedence(self):
        import time
        from unittest.mock import patch, AsyncMock, MagicMock
        from homeassistant.core import Event

        hass = MockHass()
        coord = MirAIeDeviceCoordinator(
            hass=hass,
            entry_id="entry_ir_123",
            device_id="dev_ir_456",
            model_code="CS-CU-RU18CKY-1",
            has_wifi=False,
            primary_backend="ir",
            blaster_entity_id="infrared.living_room_blaster",
            receiver_entity_id="infrared.living_room_receiver",
        )

        # 1. HA command issued
        await coord.async_dispatch_ir_command(mode="cool", target_temp=22, origin="HA UI")
        self.assertIsNotNone(coord._last_requested_ir_params)

        # 2. Physical remote decoded
        coord._apply_decoded_ir_state({
            "packet_type": "full_frame",
            "power": "on",
            "mode": "cool",
            "temperature": 26,
            "fan_speed": "auto",
        })
        self.assertEqual(coord._last_ir_command_source, "IR Remote")
        self.assertIsNone(coord._last_requested_ir_params)

        # 3. Blaster reconnects
        event = MagicMock(spec=Event)
        event.data = {
            "old_state": MagicMock(state="unavailable"),
            "new_state": MagicMock(state="available"),
        }

        with patch.object(coord, "async_dispatch_ir_command", new_callable=AsyncMock) as mock_dispatch:
            await coord._async_blaster_state_changed(event)
            mock_dispatch.assert_not_called()

    async def test_blaster_reconnect_ha_startup_no_spurious_transmission(self):
        from unittest.mock import patch, AsyncMock, MagicMock
        from homeassistant.core import Event

        hass = MockHass()
        coord = MirAIeDeviceCoordinator(
            hass=hass,
            entry_id="entry_ir_123",
            device_id="dev_ir_456",
            model_code="CS-CU-RU18CKY-1",
            has_wifi=False,
            primary_backend="ir",
            blaster_entity_id="infrared.living_room_blaster",
        )

        self.assertEqual(coord._last_ir_command_source, "Init")
        self.assertIsNone(coord._last_requested_ir_params)

        event = MagicMock(spec=Event)
        event.data = {
            "old_state": MagicMock(state="unavailable"),
            "new_state": MagicMock(state="available"),
        }

        with patch.object(coord, "async_dispatch_ir_command", new_callable=AsyncMock) as mock_dispatch:
            await coord._async_blaster_state_changed(event)
            mock_dispatch.assert_not_called()


    async def test_blaster_reconnect_flapping_no_rearm(self):
        """Verify that connection flapping (multiple reconnects) does not recursively re-arm resync."""
        from unittest.mock import patch, AsyncMock, MagicMock
        from homeassistant.core import Event

        hass = MockHass()
        coord = MirAIeDeviceCoordinator(
            hass=hass,
            entry_id="entry_ir_123",
            device_id="dev_ir_456",
            model_code="CS-CU-RU18CKY-1",
            has_wifi=False,
            primary_backend="ir",
            blaster_entity_id="infrared.living_room_blaster",
        )
        coord._is_esphome_blaster = False

        # 1. Dispatch initial command (Cool 22C)
        await coord.async_dispatch_ir_command(mode="cool", target_temp=22, origin="HA UI")
        self.assertEqual(coord._last_ir_command_source, "HA UI")
        self.assertIsNotNone(coord._last_requested_ir_params)

        # 2. First reconnect event (unavailable -> available)
        event1 = MagicMock(spec=Event)
        event1.data = {
            "old_state": MagicMock(state="unavailable"),
            "new_state": MagicMock(state="available"),
        }

        # Trigger first resync (runs actual async_dispatch_ir_command with is_resync=True)
        await coord._async_blaster_state_changed(event1)

        # Verify that after first resync, pending params is None and source is stamped as resync
        self.assertIsNone(coord._last_requested_ir_params)
        self.assertEqual(coord._last_ir_command_source, "Blaster Reconnect Resync")

        # 3. Flapping: Second reconnect event 30 seconds later (unavailable -> available)
        event2 = MagicMock(spec=Event)
        event2.data = {
            "old_state": MagicMock(state="unavailable"),
            "new_state": MagicMock(state="available"),
        }

        with patch.object(coord, "async_dispatch_ir_command", new_callable=AsyncMock) as mock_dispatch2:
            await coord._async_blaster_state_changed(event2)
            # Second flap must NOT trigger any new IR dispatch!
            mock_dispatch2.assert_not_called()


if __name__ == "__main__":
    unittest.main()
