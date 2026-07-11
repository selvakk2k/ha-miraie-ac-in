<p align="center">
  <img src="https://github.com/user-attachments/assets/b430eac3-5971-4d6e-83e1-d216cddf8600">
</p>

# Home Assistant Integration for the Panasonic MirAIe Air Conditioner

*Integration for **[Panasonic MirAIe App enabled ACs](https://store.in.panasonic.com/air-conditioners/split-ac.html)***

> [!IMPORTANT]
> This integration **exclusively** works with Panasonic air conditioners that utilize the [MirAIe App](https://play.google.com/store/apps/details?id=com.panasonic.in.miraie&hl=en_IN&gl=US). It is **not compatible** with global/European models using the **Panasonic Comfort Cloud** app.

---

## About This Fork

This is a fork of [rkzofficial/ha-miraie-ac](https://github.com/rkzofficial/ha-miraie-ac), renamed to `ha-miraie-ac-in` to expand features that may break if merged with upstream. The `v1.0.0` release marks the fork point — depending on [`miraie-ac-in`](https://pypi.org/project/miraie-ac-in/), the matching library fork.

The changes introduced in this fork are developed with the assistance of [Claude](https://claude.ai) (Anthropic) and [Antigravity](https://github.com/google-deepmind) (Google DeepMind), categorized as follows:

### 1. Hardware Adaptations & Gating
* **Room Temperature Sensor Fix (Firmware 3.02+)**: Panasonic AC units running firmware 3.02+ report room temperature in a packed string format where the actual value is in the decimals (e.g., `"134.30"` means `30°C`). The fork introduces version-aware parsing to correctly display this temperature while keeping standard parsing for older pre-3.02 firmware.
* **Converti Mode: 7-in-1 vs. 8-in-1 Support**: Automatically decides between 7-in-1 and 8-in-1 capacity step presets (e.g. mapping the 55% step vs. 60%/50% steps) based on the model's series and generation letter (e.g., threshold `B` for `NU/SU` and `C` for `EZ/HU/EU`). Unrecognized models safely fallback to 7-in-1.
* **Heat Mode ("Hot & Cold" Gating)**: Restricts `HVACMode.HEAT` controls in Home Assistant specifically to Hot & Cold models (`EZ` and `KZ` series) to prevent displaying unusable heat controls on cooling-only units.

### 2. New Sensors, Switches & Alerts
* **Gated Nanoe Air Purifier Control (Untested)**: Adds a switch entity (`switch.<ac_name>_nanoe`) to control the built-in Nanoe™ (nanoe-G / nanoe-X) air purifier, gated to supported premium series (`XU` and `HU`). *Note: This feature is currently untested due to a lack of a physical device with the feature to verify.*
* **Standalone Room Temperature**: Exposes the room temperature as a separate `sensor.<ac_name>_room_temperature` entity for easier historical charting.
* **Filter Clean Alert**: A binary sensor `binary_sensor.<ac_name>_filter_clean_alert` using the `problem` class to notify you when the physical mesh filter needs cleaning (as reported by the AC unit's internal status).
* **WiFi Signal Strength (RSSI)**: Diagnostic sensor to track WiFi dBm signal strength (disabled by default).
* **Last Control Source**: Diagnostic sensor showing whether the AC was last adjusted via the App/API or the physical remote (disabled by default).
* **Coil Cleaning Button & Binary Sensor**: Exposes a stateless trigger button (`button.<ac_name>_start_coil_clean`) to start the indoor coil clean cycle and a binary sensor (`binary_sensor.<ac_name>_coil_cleaning`) to monitor when the self-cleaning cycle is running.
* **Standalone Convertible Mode Select**: Exposes a separate select entity (`select.<ac_name>_convertible_mode`) under the Configuration section to easily control and automate the compressor capacity steps (40% to 110%) without using the climate preset dropdown. Changing this automatically synchronizes with the main climate entity's preset state.

### 3. Stability & Code Cleanup
* **Resource Leak Fixes**: Decoupled `ClientSession` closing from individual sensors, letting it live cleanly for the lifetime of the config entry. Added registration of the 30-minute sensor update timer to prevent background leaks when unloading/reloading the integration.
* **Config Flow Unique Verification**: Enforced unique ID verification in the configuration flow based on the username to prevent creating duplicate integration entries for the same account.

---

## Tested On

- **Panasonic CS-CU-EU18CKY5XFM** (1.5 Ton, 2026 range, Firmware 3.02)
- **Panasonic CS-CU-SU18ZKYWT** (upstream integration)

---

## Migrating from the old `MirAIe` integration

This fork's integration domain changed from `miraie` to `miraie_in` as part of a clean split from upstream. If you previously had the original `MirAIe` integration installed, this is a fresh integration to Home Assistant — you'll need to remove the old config entry and add this one again; existing entity IDs and automations referencing the old entities will need to be updated.

---

## Installation

### Method 1: Using [HACS](https://hacs.xyz) (Recommended)

1. Open your Home Assistant UI.
2. Go to **HACS** (Home Assistant Community Store).
3. Click the three dots in the upper right corner and select **Custom repositories**.
4. Under **Add custom repository**, enter:
    - **URL:** `https://github.com/selvakk2k/ha-miraie-ac-in`
    - **Category:** Integration
5. Click **Add**.
6. Go back to the HACS search.
7. Search for **MirAIe India** and select it from the list.
8. Click **Install** and follow any prompts to complete the installation.
9. Restart Home Assistant.

### Method 2: Manual Installation

1. Open the directory for your HA configuration (where `configuration.yaml` lives).
2. If you do not have a `custom_components` directory, create one.
3. Inside `custom_components`, create a new folder called `miraie_in`.
4. Download all the files from `custom_components/miraie_in/` in this repository.
5. Place them in the folder you just created.
6. Restart Home Assistant.

> **Note:** This fork depends on [`miraie-ac-in`](https://pypi.org/project/miraie-ac-in/) (published on PyPI) rather than the upstream `miraie-ac` release. Home Assistant will install it automatically like any other Python dependency listed in `manifest.json`.

---

## Configuration

### Step 1: Create a MirAIe Account

1. Download the [Panasonic MirAIe App](https://play.google.com/store/apps/details?id=com.panasonic.in.miraie&hl=en_IN&gl=US).
2. Create a new account using the in-app form.
3. Note your username (email or phone number) and password for the next step.

### Step 2: Add the Integration to Home Assistant

1. Open your Home Assistant UI.
2. Navigate to **Settings → Devices & Services**.
3. Click **+ Add Integration**.
4. Search for **MirAIe India** and select it.

### Step 3: Enter Your Credentials

1. Enter your `username` and `password`.
    - If using a phone number, include the country code (e.g., `+91XXXXXXXXXX`).
2. Submit the form.

---

## Caveats

- The primary functions of the integration (reading and writing AC state) use `cloud_push`, while energy consumption sensor entities are updated via `cloud_polling`.
- **Room temperature readings have two known limitations:**
  - They update with a delay of a few reporting cycles, as the AC unit only reports its internal sensor reading periodically over MQTT. This is a firmware behaviour, not an integration bug.
  - While the AC is actively cooling, the room temperature reading will be inaccurate — the internal sensor sits close to the coil/intake and reads significantly lower than the actual ambient room temperature. Readings will normalise once the AC is no longer in an active cooling cycle. This behaviour has been verified by comparing the integration's room temperature value against the reading shown on the physical AC display in fan-only mode (where internal heating from the compressor is absent), which matched the parsed value from the integration accurately.
  - For more reliable ambient temperature tracking, an external temperature sensor (e.g. a Wi-Fi temperature/humidity sensor) is strongly recommended, especially if using automations that depend on room temperature.
- **App & Platform Compatibility**: This integration **only** works with Panasonic ACs registered on the MirAIe app platform. If your AC uses the **Panasonic Comfort Cloud** app, this integration will not work.

---

## Enabling Debug Logs

```yaml
logger:
  logs:
    custom_components.miraie_in: debug
```

---

## Credits

- Original integration by [@rkzofficial](https://github.com/rkzofficial), [@deCodeIt](https://github.com/deCodeIt), and [@gutpull](https://github.com/gutpull).
- Fork changes (firmware 3.02+ temperature fix, Converti 8-in-1 model support, stability refactoring, diagnostic sensors, Nanoe toggle support, and split convertible mode / coil clean entities) developed by [@selvakk2k](https://github.com/selvakk2k) with the assistance of [Claude](https://claude.ai) (Anthropic) and [Antigravity](https://github.com/google-deepmind) (Google DeepMind).
