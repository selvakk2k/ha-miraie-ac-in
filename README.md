<p align="center">
  <img src="https://github.com/user-attachments/assets/b430eac3-5971-4d6e-83e1-d216cddf8600">
</p>

# Home Assistant Integration for the Panasonic MirAIe Air Conditioner

*Integration for **[Panasonic MirAIe App enabled ACs](https://store.in.panasonic.com/air-conditioners/split-ac.html)***

> **Note:** This integration is designed around Panasonic India air conditioners that use the [MirAIe App](https://play.google.com/store/apps/details?id=com.panasonic.in.miraie&hl=en_IN&gl=US). It has not been tested on models sold outside India and may not work with them.

---

## About This Fork

This is a fork of [rkzofficial/ha-miraie-ac](https://github.com/rkzofficial/ha-miraie-ac), with the following changes developed with the assistance of [Claude](https://claude.ai) (Anthropic):

### 1. Room Temperature Sensor Fix (Firmware 3.02+)
Panasonic AC units running firmware 3.02 and above report the room temperature (`rmtmp`) in a packed string format where the actual temperature value is encoded in the decimal portion of the string (e.g., `"134.30"` means `30°C`, not `134.3°C`). The upstream library (`miraie-ac`) used a plain `float()` cast which produced wildly incorrect room temperature readings on affected firmware.

This fix is implemented in the companion library fork [selvakk2k/miraie-ac](https://github.com/selvakk2k/miraie-ac), and this integration's `manifest.json` points to that fork instead of the upstream PyPI release. The fix is firmware-version-aware: units on older firmware (pre-3.02) continue to use the original parsing behaviour.

### 2. Converti Mode: 7-in-1 vs 8-in-1 Support
Panasonic's Converti variable-capacity mode comes in two variants:

| Variant | Capacity Steps |
|---|---|
| Converti 7-in-1 (older models) | 110% / 100% / 90% / 80% / 70% / **55%** / 40% / 0% |
| Converti 8-in-1 (2026 models + some 2025 exceptions) | 110% / 100% / 90% / 80% / 70% / **60% / 50%** / 40% / 0% |

The upstream integration exposed the 7-in-1 preset list to all devices. This fork selects the correct preset set automatically based on the device's model number:

- All **2026-range** models (identified by `CKY` in the model number) get the **8-in-1** preset set.
- Two known **2025-range** exceptions (`CS-EU12BKY3FM`, `CS-NU24BKY5W`) also get the **8-in-1** preset set.
- All other models fall back to the **7-in-1** preset set, preserving the original behaviour.

This means a household with a mix of old and new Panasonic AC units will correctly see different preset options per device.

---

## Tested On

- **Panasonic CS-CU-EU18CKY5XFM** (1.5 Ton, 2026 range, Firmware 3.02)
- **Panasonic CS-CU-SU18ZKYWT** (upstream integration)

---

## Installation

### Method 1: Using [HACS](https://hacs.xyz) (Recommended)

1. Open your Home Assistant UI.
2. Go to **HACS** (Home Assistant Community Store).
3. Click the three dots in the upper right corner and select **Custom repositories**.
4. Under **Add custom repository**, enter:
    - **URL:** `https://github.com/selvakk2k/ha-miraie-ac`
    - **Category:** Integration
5. Click **Add**.
6. Go back to the HACS search.
7. Search for **MirAIe** and select it from the list.
8. Click **Install** and follow any prompts to complete the installation.
9. Restart Home Assistant.

### Method 2: Manual Installation

1. Open the directory for your HA configuration (where `configuration.yaml` lives).
2. If you do not have a `custom_components` directory, create one.
3. Inside `custom_components`, create a new folder called `miraie`.
4. Download all the files from `custom_components/miraie/` in this repository.
5. Place them in the folder you just created.
6. Restart Home Assistant.

> **Note:** Because this fork depends on [selvakk2k/miraie-ac](https://github.com/selvakk2k/miraie-ac) (installed via the git URL in `manifest.json`) rather than the upstream PyPI release, Home Assistant will install the library from GitHub on first load. This requires your HA instance to have outbound internet access, which is standard for most setups.

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
4. Search for **MirAIe** and select it.

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
- This integration has only been tested on **Indian market Panasonic MirAIe-enabled ACs**. Compatibility with models sold in other regions is unknown.

---

## Enabling Debug Logs

```yaml
logger:
  logs:
    custom_components.miraie: debug
```

---

## Credits

- Original integration by [@rkzofficial](https://github.com/rkzofficial), [@deCodeIt](https://github.com/deCodeIt), and [@gutpull](https://github.com/gutpull).
- Fork changes (firmware 3.02+ temperature fix, Converti 8-in-1 model support) developed by [@selvakk2k](https://github.com/selvakk2k) with the assistance of [Claude](https://claude.ai) (Anthropic).
