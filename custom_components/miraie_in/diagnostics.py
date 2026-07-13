from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from miraie_ac import MirAIeHub

TO_REDACT = {
    "login_id",
    "mobile_number",
    "password",
    "auth_token",
    "username",
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


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: dr.DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    hub: MirAIeHub = entry.runtime_data
    
    miraie_device_id = next(
        (identifier[1] for identifier in device.identifiers if identifier[0] == "miraie_in"), 
        None
    )

    diagnostics_data = {
        "info": async_redact_data(entry.data, TO_REDACT),
    }

    if miraie_device_id:
        for miraie_device in hub.home.devices:
            if miraie_device.id == miraie_device_id:
                device_data = {
                    "id": miraie_device.id,
                    "friendly_name": miraie_device.friendly_name,
                    "status": async_redact_data(miraie_device.status.__dict__, TO_REDACT) if hasattr(miraie_device, "status") else None,
                    "details": async_redact_data(miraie_device.details.__dict__, TO_REDACT) if hasattr(miraie_device, "details") else None,
                }
                diagnostics_data["device"] = async_redact_data(device_data, TO_REDACT)
                break
                
    if hasattr(hub, "_raw_api_payload"):
        diagnostics_data["api_payload"] = async_redact_data(hub._raw_api_payload, TO_REDACT)
        
    return diagnostics_data
