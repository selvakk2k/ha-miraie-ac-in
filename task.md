# Task List

- [x] Modify `miraie-ac` companion library
  - [x] Update `device.py` to remove `__del__` and add explicit `close()`
  - [x] Update `hub.py` to support shared HTTP session and call `device.close()` on teardown, check `acngs` for nanoe
  - [x] Update `broker.py` to fix access_token type hint, safely dispatch callbacks in `on_message` with try/except, and fix print statements
  - [x] Update `utils.py` to return `None` in `toFloat` and harden `parse_room_temp` firmware version parsing
  - [x] Update `pyproject.toml` to remove obsolete `asyncio` dependency
- [x] Modify `ha-miraie-ac` Home Assistant custom component
  - [x] Update `__init__.py` to pass the HA shared client session to `MirAIeHub`
  - [x] Update `switch.py` to namespace `MirAIeDisplaySwitch` unique ID with `_display`
  - [x] Update `sensor.py` to avoid inline ClientSessions and run energy sensor updates concurrently via `asyncio.gather`
- [x] Verify changes
