# Panasonic MirAIe AC India Integration (`ha-miraie-ac-in`)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Version](https://img.shields.io/github/v/release/selvakk2k/ha-miraie-ac-in)](https://github.com/selvakk2k/ha-miraie-ac-in/releases)

A Home Assistant custom integration for Panasonic Air Conditioners operating on the Indian-market MirAIe IoT platform.

This repository is a feature-focused fork of `rkzofficial/ha-miraie-ac`, designed to add support for 8-in-1 convertible models, integrate diagnostic sensors, and resolve temperature parsing issues on newer firmware.

> [!IMPORTANT]
> This project is designed **exclusively** for Panasonic Air Conditioners that use the **MirAIe** application. It is **not compatible** with Panasonic ACs that use the global **Comfort Cloud** application.

---

## Features

### 1. Hardware Mappings
* **Firmware 3.02+ Room Temperature Mappings**: Correctly parses packed decimal room temperature payloads returned by newer firmware models (e.g. decoding `"134.30"` to `30°C`), resolving inaccurate ambient temperature display.
* **Dynamic Converti7 vs. Converti8 Support**: Automatically detects whether the connected AC model supports Converti7 or Converti8 capacity steps based on the model's series and generation letters, providing the correct notch options dynamically.
* **Gated Heat Mode**: Hides `HEAT` controls on cooling-only units, showing them only on verified Hot & Cold models (such as the `EZ` and `KZ` series).

### 2. Controls & Diagnostics
* **Nanoe™ Air Purifier Control**: Exposes a switch entity to toggle the built-in Nanoe™ (nanoe-G or nanoe-X) air purification systems on supported premium models (such as the `XU` and `HU` series).
* **Coil Cleaning Cycle**: Adds a stateless trigger button to start the self-cleaning indoor coil cycle and a binary sensor to monitor when it is running.
* **Filter Clean Notification**: Exposes a binary sensor that triggers when the AC's internal controller flags that the mesh air filter needs cleaning.
* **Standalone Room Temperature**: Exposes a dedicated temperature sensor entity for easier historical tracking and graphing.
* **Wi-Fi Strength & Last Control Source**: Sensors tracking Wi-Fi RSSI (in dBm) and whether the unit was last adjusted via the remote or the app.
* **Total Energy & Historical Backfill**: Exposes a `Total Energy` sensor (`TOTAL_INCREASING`) that automatically backfills historical daily energy data from MirAIe (up to ~8 months) directly into Home Assistant's long-term recorder statistics database for seamless use in the Energy Dashboard.
* **Core Diagnostics**: Supports Home Assistant Core Diagnostics. You can download a diagnostic file for the integration directly from the Device page, making it easier to troubleshoot issues without exposing sensitive credentials.

### 3. Stability & Code Cleanup
* **Resource Optimization**: Decoupled HTTP ClientSession scopes to prevent resource leaks when reloading.
* **Duplicate Prevention**: Enforces a unique identifier constraint based on the username during the configuration flow.

---

## Companion Lovelace Card

To get the most out of this integration, check out the [**MirAIe AC Lovelace Card**](https://github.com/selvakk2k/miraie-ac-card-in)!

It is a premium, custom Lovelace thermostat card specifically designed to work seamlessly with this integration. It supports all the custom features exposed by this integration (Converti 8-in-1 presets, Nanoe, Coil Clean, external temperature sensors, etc.) and includes full visual editor support.

---

## Installation

### Method 1: Using HACS (Recommended)
1. In Home Assistant, open **HACS** → **Integration** → Click the three dots (⋮) in the top-right corner.
2. Select **Custom repositories**.
3. Under **URL**, add: `https://github.com/selvakk2k/ha-miraie-ac-in`
4. Select **Integration** as the category and click **Add**.
5. Search for **MirAIe India**, click **Install**, and restart Home Assistant.

### Method 2: Manual Installation
1. Download this repository as a ZIP file.
2. Copy the folder `custom_components/miraie_in` into your Home Assistant's `custom_components/` directory.
3. Restart Home Assistant.

---

## Configuration

1. In Home Assistant, navigate to **Settings → Devices & Services** → **+ Add Integration**.
2. Search for **MirAIe India**.
3. Enter your MirAIe App credentials:
   * **Username**: Your email or mobile number (10-digit number without country code).
   * **Password**: Your password.
4. Submit the form to discover your air conditioning units.

---

## Troubleshooting & Logs

If you encounter an issue, providing debug logs and diagnostic files helps tremendously in identifying the root cause. Sensitive information (such as your phone number, passwords, and device serial numbers) is automatically redacted before any files are downloaded or displayed.

### 1. Enabling Debug Logs (To capture events/errors)
Debug logs record real-time operational messages (like commands and connection status) in the background.

* **Via the UI (Dynamic, no restart required):**
  1. Navigate to **Settings → Devices & Services**.
  2. Locate the **MirAIe India** integration card.
  3. Click the three dots (**⋮**) on the integration card and select **Enable debug logging**.
  4. Reproduce the issue you are experiencing.
  5. Go back to the same menu and select **Disable debug logging**. Home Assistant will automatically download the debug log file to your device.
* **Via configuration.yaml (Persistent):**
  Add the following lines to your `configuration.yaml` and restart Home Assistant:
  ```yaml
  logger:
    default: warning
    logs:
      custom_components.miraie_in: debug
      miraie_ac: debug
  ```

### 2. Downloading Diagnostics (Current state snapshot)
Diagnostics provide a snapshot of the current device status, configuration, and raw JSON payloads.

* **For the entire Integration (All Devices):**
  1. Navigate to **Settings → Devices & Services**.
  2. Click the three dots (**⋮**) on the **MirAIe India** integration card and click **Download diagnostics**.
* **For a single Device:**
  1. Navigate to **Settings → Devices & Services** → click the **MirAIe India** card.
  2. Select the specific Air Conditioner device from the list.
  3. On the Device page, under **Device info**, click **Download diagnostics**.

---

## Caveats & Firmware Limitations

* **Intake Temperature Sensor Placement**: The AC's internal room temperature sensor sits close to the active evaporator coil. During cooling cycles, this sensor reads lower than the actual room temperature. The value will normalize when the unit runs in Fan-Only mode or once compressor cycles pause. For precise automation control, an external temperature sensor is recommended.
* **Update Frequency**: Primary thermostat commands are sent instantly via `cloud_push` (MQTT), while aggregate energy consumption statistics are updated via background polling.

---

## Credits & License

### Upstream Authors & Contributors
* Originally designed and written by [@rkzofficial](https://github.com/rkzofficial).
* Key features contributed by upstream community developers: [@deCodeIt](https://github.com/deCodeIt) and [@gutpull](https://github.com/gutpull).

### Fork Authors & Contributors
* Historical energy statistics backfill feature contributed by [@shashi278](https://github.com/shashi278).
* Fork enhancements (firmware 3.02+ temperature fix, Converti 8-in-1, and MQTT resource leak resolutions) developed by [@selvakk2k](https://github.com/selvakk2k) with assistance from **Claude** (Anthropic) and **Gemini/Antigravity** (Google DeepMind).

Licensed under the **Apache License 2.0**. See the `LICENSE` file for the original license text.
