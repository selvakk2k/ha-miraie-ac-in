# Implementation Plan - Split Convertible Mode and Coil Clean from Climate Presets

This plan refactors the `ha-miraie-ac` integration to separate the capacity limit (Convertible Modes) and maintenance cycle (Coil Clean) out of the main climate entity's comfort presets. They will be exposed as dedicated entities (`select` and `button`/`binary_sensor`).

## User Review Required

> [!NOTE]
> This change is backward-incompatible for dashboards relying on `cv XX` or `clean` values inside `climate.set_preset_mode`. However, it significantly improves UX and aligns with standard Home Assistant architectural patterns.

## Proposed Changes

### Component: `ha-miraie-ac` (Home Assistant Custom Component)

#### [MODIFY] [__init__.py](file:///home/skk/Documents/GitHub/ha-miraie-ac/custom_components/miraie_in/__init__.py)
* Add `Platform.SELECT` and `Platform.BUTTON` to `PLATFORMS`.

#### [MODIFY] [climate.py](file:///home/skk/Documents/GitHub/ha-miraie-ac/custom_components/miraie_in/climate.py)
* Limit the `preset_modes` to `[PRESET_NONE, PRESET_ECO, PRESET_BOOST]`.
* Simplify `preset_mode` property to return only `self.device.status.preset_mode.value` without checking the `converti_mode` attribute (resolving state collision).
* Simplify `async_set_preset_mode` to only call `self.device.set_preset_mode` with the target `PresetMode` (remove the `cv` check).

#### [MODIFY] [binary_sensor.py](file:///home/skk/Documents/GitHub/ha-miraie-ac/custom_components/miraie_in/binary_sensor.py)
* Add `MirAIeCoilCleanBinarySensor` to show whether coil cleaning is currently running (`device.status.preset_mode == PresetMode.CLEAN`).

#### [NEW] [select.py](file:///home/skk/Documents/GitHub/ha-miraie-ac/custom_components/miraie_in/select.py)
* Implement `MirAIeConvertiSelect` representing the convertible modes / capacity limit.
* Options dynamically map `Normal` (value `0`) and percentages (`110% (HC)`, `100% (FC)`, `90%`, `80%`, `70%`, `60%`, `50%`, `40%`) based on the device model supporting 7-in-1 or 8-in-1.
* Triggers `set_converti_mode(ConvertiMode(value))` when changed.

#### [NEW] [button.py](file:///home/skk/Documents/GitHub/ha-miraie-ac/custom_components/miraie_in/button.py)
* Implement `MirAIeCoilCleanButton` representing the Coil Clean trigger.
* Triggers `device.set_preset_mode(PresetMode.CLEAN)` on press.

---

## Verification Plan

### Automated Tests
* We will verify python package validity by running syntax/compile checks on the modified and new files.

### Manual Verification
* Verify that the integration loads successfully in Home Assistant and correctly initializes the new entities:
  * `climate.room_2_ac` (with only Eco and Boost presets).
  * `select.room_2_ac_convertible_mode` (with options from Normal, 40% to 110%).
  * `binary_sensor.room_2_ac_coil_cleaning`.
  * `button.room_2_ac_start_coil_clean`.
