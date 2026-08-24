"""Shared test fixtures and stubs for ha-miraie-ac test suite."""

from __future__ import annotations
from datetime import date


class MockDetails:
    """Mock device details."""

    def __init__(self, brand="Panasonic", model_number="CS-CU-EU18CKY5XFM", firmware_version="3.02"):
        self.brand = brand
        self.model_number = model_number
        self.firmware_version = firmware_version


class MockStatus:
    """Mock device status."""

    def __init__(self, room_temp=24.0, wifi_signal=-70, control_source="an"):
        self.room_temperature = room_temp
        self.wifi_signal = wifi_signal
        self.control_source = control_source


class MockDevice:
    """Mock MirAIe Device for unit tests."""

    def __init__(self, device_id="dev_bedroom", friendly_name="PANASONIC AC"):
        self.id = device_id
        self.friendly_name = friendly_name
        self.details = MockDetails()
        self.status = MockStatus()
        self.callbacks = []

    def register_callback(self, cb):
        self.callbacks.append(cb)

    def remove_callback(self, cb):
        if cb in self.callbacks:
            self.callbacks.remove(cb)


class MockConfigEntry:
    """Mock ConfigEntry for unit tests."""

    def __init__(self, entry_id="mock_entry_id", options=None, devices=None, data=None):
        self.entry_id = entry_id
        self.options = options or {}
        self.data = data or {}
        if devices is None:

            devices = [MockDevice()]
        self.runtime_data = type(
            "Hub",
            (),
            {
                "home": type("Home", (), {"devices": devices})(),
                "get_energy_consumption": None,
                "get_energy_consumption_full": None,
            },
        )()
