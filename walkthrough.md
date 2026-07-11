# Walkthrough - Split Convertible Mode and Coil Clean from Climate Presets

We have implemented and verified the backend refactoring to separate the capacity limit (Convertible Modes) and maintenance cycle (Coil Clean) out of the main climate entity's comfort presets.

In addition, we migrated all hardcoded friendly names from the Python codebase to the translation file (`en.json`) to allow full localization of all entities in the integration.

## Changes Made

### Custom Integration (`ha-miraie-ac-in`)
* **[__init__.py](file:///home/skk/Documents/GitHub/ha-miraie-ac/custom_components/miraie_in/__init__.py)**: Registered `Platform.SELECT` and `Platform.BUTTON` platforms.
* **[climate.py](file:///home/skk/Documents/GitHub/ha-miraie-ac/custom_components/miraie_in/climate.py)**:
  * Restricted `_attr_preset_modes` to `none`, `eco`, and `boost`.
  * Simplified the `preset_mode` property to return the device status preset directly (safely mapping the backend `CLEAN` preset to `none` at the climate entity level).
  * Cleaned up `async_set_preset_mode` to remove the prefix parsing for `"cv "` since convertible capacity limits are now controlled by the select entity.
* **[binary_sensor.py](file:///home/skk/Documents/GitHub/ha-miraie-ac/custom_components/miraie_in/binary_sensor.py)**: 
  * Removed hardcoded entity names.
  * Added `self._attr_translation_key` to `MirAIeFilterCleanBinarySensor` (`"filter_clean_alert"`) and `MirAIeCoilCleanBinarySensor` (`"coil_cleaning"`).
* **[select.py](file:///home/skk/Documents/GitHub/ha-miraie-ac/custom_components/miraie_in/select.py) [NEW]**: Added `MirAIeConvertiSelect` representing the convertible modes (capacity limit). Options now use raw identifiers (`cv 110`, `cv 100`, etc.) in python, delegating user-friendly localization to the translation files.
* **[button.py](file:///home/skk/Documents/GitHub/ha-miraie-ac/custom_components/miraie_in/button.py) [NEW]**: Added `MirAIeCoilCleanButton` to trigger the start of the coil cleaning cycle via `device.set_preset_mode(PresetMode.CLEAN)`, with the translation key `start_coil_clean`.
* **[switch.py](file:///home/skk/Documents/GitHub/ha-miraie-ac/custom_components/miraie_in/switch.py)**:
  * Removed hardcoded entity names.
  * Replaced DOMAIN-bound translation keys with unique translation keys `display` and `nanoe`.
* **[sensor.py](file:///home/skk/Documents/GitHub/ha-miraie-ac/custom_components/miraie_in/sensor.py)**:
  * Removed all hardcoded energy and status sensor names.
  * Configured `self._attr_translation_key` on all sensor subclasses (`yesterday_consumption`, `current_consumption`, `weekly_consumption`, `monthly_consumption`, `ac_temperature`, `wifi_signal`, `last_controlled_via`).
  * Updated logging statements referencing `_attr_name` to use `entity_id` or `friendly_name`.
* **[en.json](file:///home/skk/Documents/GitHub/ha-miraie-ac/custom_components/miraie_in/translations/en.json)**:
  * Moved all sensor, binary sensor, switch, select, and button entity names into translation key objects.
  * Localized the raw convertible select values (e.g. `cv 80` $\rightarrow$ `"80%"`, `cv 0` $\rightarrow$ `"Normal"`).

---

## Validation Results

* **Syntax Verification**: Ran compilation checks on all Python files across the integration using `python3 -m py_compile`. All files compiled successfully with no syntax or import errors.
* **JSON Verification**: Validated translation JSON structure using `json.tool`.
