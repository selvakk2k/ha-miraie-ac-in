from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from miraie_ac import MirAIeHub

TO_REDACT = {
    "login_id",
    "mobile_number",
    "password",
    "auth_token",
    "id",
    "mac_address",
    "device_name",
    "home_id",
    "home_name",
    "friendly_name",
    "serial_number"
}

async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    hub: MirAIeHub = entry.runtime_data

    diagnostics_data = {
        "info": async_redact_data(entry.data, TO_REDACT),
        "devices": []
    }
    
    for device in hub.home.devices:
        device_data = {
            "id": device.id,
            "friendly_name": device.friendly_name,
            "status": async_redact_data(device.status.__dict__, TO_REDACT) if hasattr(device, "status") else None,
            "details": async_redact_data(device.details.__dict__, TO_REDACT) if hasattr(device, "details") else None,
        }
        diagnostics_data["devices"].append(async_redact_data(device_data, TO_REDACT))
        
    if hasattr(hub, "_raw_api_payload"):
        diagnostics_data["api_payload"] = async_redact_data(hub._raw_api_payload, TO_REDACT)
        
    return diagnostics_data
