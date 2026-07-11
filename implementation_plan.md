# Implementation Plan - Hardening and fixing MirAIe AC Integration

This plan addresses the 10 identified bugs and code quality issues across the Home Assistant Custom Component (`ha-miraie-ac-in`) and its companion library (`miraie-ac-in`).

## User Review Required

> [!IMPORTANT]
> **Unique ID Migration Plan**: We will **NOT** modify the unique ID of the climate entity (`MirAIeClimate`) because doing so would orphan existing users' configuration and history. However, we will change the display switch entity's unique ID to namespace it with a `_display` suffix to prevent collisions.

## Open Questions

None at this stage. The feedback from Claude has clarified the design choices and confirmed the scope of the fixes.

---

## Proposed Changes

### Component 1: `miraie-ac` (Companion Library)

#### [MODIFY] [device.py](file:///home/skk/Documents/GitHub/miraie-ac/miraie_ac/device.py)
* Remove `__del__` method.
* Add an explicit `close(self)` method to cleanly unregister MQTT topics from the broker.

#### [MODIFY] [hub.py](file:///home/skk/Documents/GitHub/miraie-ac/miraie_ac/hub.py)
* Update `MirAIeHub.__init__` to accept an optional `session` parameter (`aiohttp.ClientSession`).
* Store `self._close_session` to indicate if the hub should close the session on shutdown.
* In `close()`, loop through and call `device.close()` for all devices, and only close the HTTP session if `self._close_session` is `True`.
* In `get_all_device_status()`, read the `nanoe_mode` operational status checking `acngs` first, falling back to `acng`.

#### [MODIFY] [broker.py](file:///home/skk/Documents/GitHub/miraie-ac/miraie_ac/broker.py)
* Update `connect` method signature's type hint for `access_token` from `User` to `str`.
* In `on_message`, add a safety `if func:` check before calling the callback, and wrap the callback execution in a `try...except` block to prevent a callback failure from crashing the background MQTT client task.
* In `on_connect`, replace the raw `print` statement with `LOGGER.debug`.

#### [MODIFY] [utils.py](file:///home/skk/Documents/GitHub/miraie-ac/miraie_ac/utils.py)
* Modify `toFloat` to return `None` (instead of `-1.0`) on parsing errors.
* Harden `parse_room_temp` by stripping non-digit and non-dot characters from `firmware_version` before checking version number thresholds.

#### [MODIFY] [pyproject.toml](file:///home/skk/Documents/GitHub/miraie-ac/pyproject.toml)
* Remove the obsolete `asyncio = "^3.4.3"` PyPI dependency.

---

### Component 2: `ha-miraie-ac` (Home Assistant Custom Component)

#### [MODIFY] [__init__.py](file:///home/skk/Documents/GitHub/ha-miraie-ac/custom_components/miraie_in/__init__.py)
* Pass the Home Assistant shared client session (`async_get_clientsession(hass)`) to `MirAIeHub` inside `async_setup_entry`.

#### [MODIFY] [switch.py](file:///home/skk/Documents/GitHub/ha-miraie-ac/custom_components/miraie_in/switch.py)
* Change `MirAIeDisplaySwitch` unique ID from `device.id` to `f"{device.id}_display"` to avoid colliding with the climate entity.

#### [MODIFY] [sensor.py](file:///home/skk/Documents/GitHub/ha-miraie-ac/custom_components/miraie_in/sensor.py)
* In `async_update`, avoid instantiating inline/temporary ClientSessions. Log an error if the hub session is closed or unavailable.
* Update `update_sensors()` inside `async_setup_entry` to run all updates concurrently using `asyncio.gather` instead of running sequentially.

---

## Verification Plan

### Automated Tests
* We will verify python package validity by running syntax/compile checks.
* Run standard Home Assistant configuration validation if possible, or verify code runs successfully without warnings/exceptions.

### Manual Verification
* Ensure the local custom component loads correctly and doesn't print any runtime exceptions.
* Verify the display switch unique ID works and does not conflict with climate entities.
