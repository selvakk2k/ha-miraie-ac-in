import calendar
from datetime import date, timedelta
from typing import Any
from homeassistant.util import dt as dt_util
from .logger import LOGGER


def get_last_sunday() -> date:
    """Returns the datetime.date object corresponding to the last sunday before today.
    Excludes the present day (if it is a sunday).
    """
    today = dt_util.now().date()
    days_since_sunday = today.weekday() + 1  # weekday() -> Monday=0, Sunday=6
    previous_sunday = today - timedelta(days=days_since_sunday)
    return previous_sunday


def months_ago(today: date, months: int) -> date:
    """Return the date `months` ago from `today`."""
    month = today.month - months
    year = today.year
    if month <= 0:
        month += 12
        year -= 1
    day = min(today.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)

def six_months_ago(today: date) -> date:
    """Return the date 6 months ago from `today`."""
    return months_ago(today, 6)

def eight_months_ago(today: date) -> date:
    """Return the date 8 months ago from `today`."""
    return months_ago(today, 8)


def get_devices_for_entry(hub: Any, entry: Any) -> list[Any]:
    """Resolve the devices belonging to a given ConfigEntry.

    For per-device entries with 'device_id', returns a list containing the single matched device.
    If 'device_id' is specified but not found in the account, logs an error and returns []
    (preventing silent fallbacks or cross-device entity duplication).
    """
    if not hub or not hasattr(hub, "home") or not hasattr(hub.home, "devices"):
        return []

    entry_data = getattr(entry, "data", entry) if isinstance(getattr(entry, "data", entry), dict) else {}
    target_id = entry_data.get("device_id")

    if target_id:
        matched = [d for d in hub.home.devices if getattr(d, "id", None) == target_id]
        if not matched:
            found_ids = [getattr(d, "id", None) for d in hub.home.devices]
            from .logger import LOGGER
            LOGGER.error(
                "Device ID '%s' for entry '%s' not found in MirAIe account devices: %s",
                target_id,
                getattr(entry, "title", getattr(entry, "entry_id", "unknown")),
                found_ids,
            )
            return []
        return matched

    # Fallback only when device_id is not specified (e.g. single-device setups or IR dummy device)
    return list(hub.home.devices)

