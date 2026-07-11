"""The mirAIe integration."""
from __future__ import annotations

from .logger import LOGGER

from miraie_ac import MirAIeBroker, MirAIeHub

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN



# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.BUTTON,
    Platform.BINARY_SENSOR,
]

# Mapping of entity-domain prefixes that appear in old-format unique_ids.
_OLD_UID_PREFIXES = ("sensor.", "switch.", "button.", "binary_sensor.")


def _migrate_unique_ids(
    hass: HomeAssistant, entry: ConfigEntry, hub: MirAIeHub
) -> None:
    """Migrate entity unique_ids from the old format to the new format.

    Old format: ``<domain>.<device_name>_<device_id>_<suffix>``
    New format: ``<device_id>_<suffix>``

    The migration is idempotent — entities already in the new format are
    skipped.
    """
    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)

    # Build a set of known device IDs for fast lookup
    device_ids = {device.id for device in hub.home.devices}

    migrated = 0
    for entity_entry in entities:
        old_uid = entity_entry.unique_id

        # Only process unique_ids that start with a domain prefix (old format)
        if not any(old_uid.startswith(prefix) for prefix in _OLD_UID_PREFIXES):
            continue

        # Strip the domain prefix (e.g. "sensor.")
        stripped = old_uid.split(".", 1)[1] if "." in old_uid else old_uid

        # Find which device_id is embedded in this unique_id
        for device_id in device_ids:
            idx = stripped.find(f"_{device_id}_")
            if idx == -1:
                # Also check if the stripped string starts with device_id
                if stripped.startswith(f"{device_id}_"):
                    # No name prefix, just device_id_suffix
                    new_uid = stripped
                    break
                continue

            # Everything after the device_id is the suffix (including leading _)
            suffix_start = idx + 1 + len(device_id)
            suffix = stripped[suffix_start:]
            new_uid = f"{device_id}{suffix}"
            break
        else:
            LOGGER.warning(
                "Could not determine device_id for entity %s (unique_id=%s), skipping migration",
                entity_entry.entity_id,
                old_uid,
            )
            continue

        if new_uid == old_uid:
            continue

        LOGGER.info(
            "Migrating unique_id for %s: %s → %s",
            entity_entry.entity_id,
            old_uid,
            new_uid,
        )
        registry.async_update_entity(entity_entry.entity_id, new_unique_id=new_uid)
        migrated += 1

    if migrated:
        LOGGER.info("Migrated %d entity unique_id(s) to new format", migrated)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up mirAIe from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass)
    hub = MirAIeHub(session)
    broker = MirAIeBroker()
    await hub.init(entry.data["username"], entry.data["password"], broker)
    hass.data[DOMAIN][entry.entry_id] = hub

    # Migrate old-format unique_ids (idempotent, safe to run every startup)
    _migrate_unique_ids(hass, entry, hub)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hub = hass.data[DOMAIN].pop(entry.entry_id)
        await hub.close()

    return unload_ok
