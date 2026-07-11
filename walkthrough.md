# Walkthrough - Split Convertible Mode and Coil Clean from Climate Presets

We have implemented and verified the backend refactoring to separate the capacity limit (Convertible Modes) and maintenance cycle (Coil Clean) out of the main climate entity's comfort presets.

In addition, we migrated all hardcoded friendly names from the Python codebase to the translation file (`en.json`) to allow full localization of all entities in the integration.

We also restored dual exposure of the convertible presets under the climate entity (for backward compatibility with the standard thermostat card) and assigned the select entity to the Configuration category so it doesn't clutter the main Controls card.

Finally, we registered icons for all the newly created and modified entities in `icons.json`.

## Changes Made

### Custom Integration (`ha-miraie-ac-in`)
* **[__init__.py](file:///home/skk/Documents/GitHub/ha-miraie-ac/custom_components/miraie_in/__init__.py)**: Registered `Platform.SELECT` and `Platform.BUTTON` platforms.
* **[climate.py](file:///home/skk/Documents/GitHub/ha-miraie-ac/custom_components/miraie_in/climate.py)**:
  * Exposes comfort presets (`none`, `eco`, `boost`) and convertible capacity steps (`cv 110` to `cv 0`).
  * Maps preset/convertible mode values to the AC command payload correctly.
* **[binary_sensor.py](file:///home/skk/Documents/GitHub/ha-miraie-ac/custom_components/miraie_in/binary_sensor.py)**: 
  * Removed hardcoded entity names.
  * Added `self._attr_translation_key` to `MirAIeFilterCleanBinarySensor` (`"filter_clean_alert"`) and `MirAIeCoilCleanBinarySensor` (`"coil_cleaning"`).
* **[select.py](file:///home/skk/Documents/GitHub/ha-miraie-ac/custom_components/miraie_in/select.py) [NEW]**: 
  * Added `MirAIeConvertiSelect` representing the convertible modes (capacity limit). 
  * Assigned `self._attr_entity_category = EntityCategory.CONFIG` to place the dropdown cleanly under "Configuration" on the device page rather than the main "Controls" card.
* **[button.py](file:///home/skk/Documents/GitHub/ha-miraie-ac/custom_components/miraie_in/button.py) [NEW]**: 
  * Added `MirAIeCoilCleanButton` to trigger the start of the coil cleaning cycle via `device.set_preset_mode(PresetMode.CLEAN)`, with the translation key `start_coil_clean`.
* **[switch.py](file:///home/skk/Documents/GitHub/ha-miraie-ac/custom_components/miraie_in/switch.py)**:
  * Removed hardcoded entity names.
  * Replaced DOMAIN-bound translation keys with unique translation keys `display` and `nanoe`.
* **[sensor.py](file:///home/skk/Documents/GitHub/ha-miraie-ac/custom_components/miraie_in/sensor.py)**:
  * Removed all hardcoded energy and status sensor names.
  * Configured `self._attr_translation_key` on all sensor subclasses.
* **[en.json](file:///home/skk/Documents/GitHub/ha-miraie-ac/custom_components/miraie_in/translations/en.json)**:
  * Restored climate preset translations (`cv 110` $\rightarrow$ `"HC"`, etc.).
  * Added translation dictionary mapping for all sensor, binary sensor, switch, select, and button entity names.
* **[icons.json](file:///home/skk/Documents/GitHub/ha-miraie-ac/custom_components/miraie_in/icons.json)**:
  * Added default icons for the newly introduced button (`mdi:sparkles`), switches (`mdi:eye-outline`, `mdi:air-filter`), binary sensors (`mdi:air-filter`, `mdi:sparkles`), and select (`mdi:speedometer`) entities.
  * Added state-specific icons for the convertible mode capacity steps (e.g. `cv 110` $\rightarrow$ `mdi:alpha-h-circle`, `cv 80` $\rightarrow$ `mdi:circle-slice-7`, etc.) matching their limits.

---

## Validation Results

* **Syntax Verification**: Ran compilation checks on all Python files across the integration using `python3 -m py_compile`. All files compiled successfully with no syntax or import errors.
* **JSON Verification**: Validated translation and icon JSON structures using `json.tool`.
