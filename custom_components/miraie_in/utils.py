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

    - For per-device entries with 'device_id': Returns strictly [matching_device] (or [] on mismatch).
    - For standalone IR entries: Returns [dummy_dev].
    - For single-device cloud accounts (legacy v1): Returns [device_1].
    - For multi-device cloud accounts missing 'device_id': Refuses to fan out; logs error and returns [].
    """
    if not hub or not hasattr(hub, "home") or not hasattr(hub.home, "devices"):
        return []

    raw_data = getattr(entry, "data", entry)
    entry_data: dict[str, Any] = raw_data if isinstance(raw_data, dict) else {}
    target_id = entry_data.get("device_id")
    account_devices = list(hub.home.devices)

    # 1. Standard 2.0 per-device entry with explicit device_id
    if target_id:
        matched = [d for d in account_devices if getattr(d, "id", None) == target_id]
        if not matched:
            found_ids = [getattr(d, "id", None) for d in account_devices]
            LOGGER.error(
                "Device ID '%s' for entry '%s' not found in MirAIe account devices: %s",
                target_id,
                getattr(entry, "title", getattr(entry, "entry_id", "unknown")),
                found_ids,
            )
            return []
        return matched

    # 2. Standalone IR / Mock entry (no MirAIe cloud credentials)
    if entry_data.get("is_ir_only") or "username" not in entry_data:
        return account_devices

    # 3. Cloud account with missing device_id on a single-device account
    if len(account_devices) == 1:
        return account_devices

    # 4. Multi-device cloud account with missing device_id -> BLOCK FAN-OUT
    LOGGER.error(
        "ConfigEntry '%s' (%s) is missing 'device_id' on a multi-device account (%d devices found). "
        "Refusing to create duplicate entities across all devices.",
        getattr(entry, "title", "unknown"),
        getattr(entry, "entry_id", "unknown"),
        len(account_devices),
    )
    return []


