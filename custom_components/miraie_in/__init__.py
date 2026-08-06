"""The mirAIe integration."""
from __future__ import annotations

from .logger import LOGGER

from miraie_ac import MirAIeBroker, MirAIeHub

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.start import async_at_started
from homeassistant.exceptions import ConfigEntryNotReady, ConfigEntryAuthFailed
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from datetime import date
import aiohttp
import asyncio

from .const import CONF_INSTALL_DATE, DOMAIN
from .sensor import async_backfill_energy_statistics
from .utils import six_months_ago



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

    loaded_components = getattr(getattr(hass, "config", None), "components", set())
    configured_domains = set(hass.config_entries.async_domains()) if hasattr(hass, "config_entries") and hasattr(hass.config_entries, "async_domains") else set()

    if "miraie" in loaded_components or "miraie" in configured_domains:
        LOGGER.warning(
            "Conflicting integration 'miraie' detected! Running both 'miraie' and 'miraie_in' "
            "simultaneously causes MQTT connection drops and database corruption. Please remove one of the integrations."
        )
        async_create_issue(
            hass,
            DOMAIN,
            "conflicting_miraie_integration",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="conflicting_miraie_integration",
        )

    session = async_get_clientsession(hass)
    # If a previously-installed miraie-ac-in version is still loaded in this
    # running process (e.g. right after an integration upgrade, before HA has
    # restarted), MirAIeHub() may not yet accept a session argument. Fall back
    # to a self-managed session in that case; this resolves itself on the next
    # HA restart once the updated dependency is actually loaded.
    # See https://github.com/selvakk2k/ha-miraie-ac-in/issues/2
    try:
        hub = MirAIeHub(session)
    except TypeError:
        LOGGER.warning(
            "miraie-ac-in installed in this process does not accept a shared "
            "session yet (likely an integration upgrade pending a Home "
            "Assistant restart); using a self-managed session for now. This "
            "should resolve automatically after the next restart."
        )
        hub = MirAIeHub()
    broker = MirAIeBroker()
    try:
        await hub.init(entry.data["username"], entry.data["password"], broker)
    except (aiohttp.ClientError, TimeoutError) as err:
        raise ConfigEntryNotReady from err
    except Exception as err:
        # Generic catch for miraie_ac auth failure or other unexpected init errors
        raise ConfigEntryAuthFailed from err

    entry.runtime_data = hub

    # Migrate old-format unique_ids (idempotent, safe to run every startup)
    _migrate_unique_ids(hass, entry, hub)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register listener for option updates to automatically reload entry when options change
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    def _log_backfill_result(task: asyncio.Task) -> None:
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            LOGGER.error("Energy statistics backfill task failed", exc_info=exc)

    def _get_device_install_date(device_id: str) -> date:
        devices_opt = entry.options.get("devices", {})
        dev_opt = devices_opt.get(device_id, {})
        install_str = dev_opt.get(CONF_INSTALL_DATE) or entry.options.get(CONF_INSTALL_DATE)
        if install_str:
            return date.fromisoformat(install_str)
        return six_months_ago(date.today())

    async def _run_startup_backfill(hass: HomeAssistant) -> None:
        """Run the initial backfill only once HA has fully finished starting."""
        for device in hub.home.devices:
            start_date = _get_device_install_date(device.id)
            task = hass.async_create_task(
                async_backfill_energy_statistics(hass, hub, device, start_date)
            )
            task.add_done_callback(_log_backfill_result)

    if hass.is_running:
        hass.async_create_task(_run_startup_backfill(hass))
    else:
        entry.async_on_unload(async_at_started(hass, _run_startup_backfill))

    async def nightly_backfill(now=None):
        for device in hub.home.devices:
            backfill_start = _get_device_install_date(device.id)
            task = hass.async_create_task(
                async_backfill_energy_statistics(hass, hub, device, backfill_start)
            )
            task.add_done_callback(_log_backfill_result)

    # Run nightly backfill at 02:05 AM IST to ensure Panasonic cloud servers have finalized yesterday's daily batch
    unsub = async_track_time_change(hass, nightly_backfill, hour=2, minute=5, second=0)
    entry.async_on_unload(unsub)

    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update by automatically reloading the integration entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hub: MirAIeHub = entry.runtime_data
        if hasattr(hub, "close"):
            await hub.close()
        else:
            for task in list(getattr(hub, "background_tasks", [])):
                task.cancel()
            if hasattr(hub, "http") and hub.http and not getattr(hub.http, "closed", True):
                await hub.http.close()

    return unload_ok



