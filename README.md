<p align="center">
  <img src="https://github.com/user-attachments/assets/b430eac3-5971-4d6e-83e1-d216cddf8600">
</p>

# Home Assistant Integration for the Panasonic MirAIe Air Conditioner

*Integration for **[Panasonic MirAIe App enabled ACs](https://store.in.panasonic.com/air-conditioners/split-ac.html)***

> **Note:** This integration is designed around Panasonic India air conditioners that use the [MirAIe App](https://play.google.com/store/apps/details?id=com.panasonic.in.miraie&hl=en_IN&gl=US). It has not been tested on models sold outside India and may not work with them.

---

## About This Fork

This is a fork of [rkzofficial/ha-miraie-ac](https://github.com/rkzofficial/ha-miraie-ac), renamed to `ha-miraie-ac-in` as a clean split focused on Indian-market MirAIe models. The `v1.0.0` release marks the fork point — depending on [`miraie-ac-in`](https://pypi.org/project/miraie-ac-in/), the matching library fork — and includes the following changes developed with the assistance of [Claude](https://claude.ai) (Anthropic):

### 1. Room Temperature Sensor Fix (Firmware 3.02+)
Panasonic AC units running firmware 3.02 and above report the room temperature (`rmtmp`) in a packed string format where the actual temperature value is encoded in the decimal portion of the string (e.g., `"134.30"` means `30°C`, not `134.3°C`). The upstream library (`miraie-ac`) used a plain `float()` cast which produced wildly incorrect room temperature readings on affected firmware.

This fix is implemented in the companion library fork [selvakk2k/miraie-ac-in](https://github.com/selvakk2k/miraie-ac-in), published to PyPI as `miraie-ac-in`, and this integration's `manifest.json` points to that package instead of the upstream `miraie-ac` release. The fix is firmware-version-aware: units on older firmware (pre-3.02) continue to use the original parsing behaviour.

### 2. Converti Mode: 7-in-1 vs 8-in-1 Support
Panasonic's Converti variable-capacity mode comes in two variants:

| Variant | Capacity Steps |
|---|---|
| Converti 7-in-1 | 110% / 100% / 90% / 80% / 70% / **55%** / 40% / 0% |
| Converti 8-in-1 | 110% / 100% / 90% / 80% / 70% / **60% / 50%** / 40% / 0% |

The upstream integration exposed the 7-in-1 preset list to all devices. This fork selects the correct preset set automatically based on the device's model number.

**Methodology:** this was verified directly against Panasonic's own `store.in.panasonic.com` `/2025-model/` and `/2026-model/` catalog pages — not third-party retailers or trackers, which were found during development to have inconsistent year labelling for the same model. Every model confirmed under the 2026 catalog is 8-in-1; every one still under the 2025 catalog is 7-in-1. However, the generation letter in the model number that marks "2026" is **not the same across every series** — it's a per-series revision counter, not a fleet-wide year code:

| Series group | 2025 (7-in-1) | 2026 (8-in-1) |
|---|---|---|
| `NU`, `SU` | letter `A` | letter `B` |
| `EZ`, `HU`, `EU` | letter `B` | letter `C` |

A model is classified as 8-in-1 if its series matches one of the groups above **and** its generation letter is at or past that group's threshold. Anything unrecognised (unknown series, missing model number, or an older generation letter like `Z`) safely falls back to the original 7-in-1 preset list.

**Known gaps:**
- `QU` (e.g. `CS-CU-QU26BKYFM`) is confirmed 7-in-1 for 2025, but isn't in either group above — its 2026 behaviour is unverified, so it currently defaults to 7-in-1.
- Older (pre-2024) generation letters are unmapped by design, since older models are out of scope for this fork.

There are currently no confirmed exceptions to the two-group rule above. An earlier version of this fix incorrectly listed `CS-EU12BKY3FM` as an 8-in-1 exception, based on unverified early research — Panasonic's own retailer listings (Croma, Amazon, and others) explicitly describe it as **7-in-1 Convertible**, and it's correctly classified as such by the general rule (its generation letter `B` is below the `EU` group's `C` threshold). If you find a genuine exception, please open an issue/PR with a link to an official Panasonic listing confirming it.

This means a household with a mix of AC models will correctly see different preset options per device.

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
- This integration has only been tested on **Indian market Panasonic MirAIe-enabled ACs**. Compatibility with models sold in other regions is unknown.

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
- Fork changes (firmware 3.02+ temperature fix, Converti 8-in-1 model support) developed by [@selvakk2k](https://github.com/selvakk2k) with the assistance of [Claude](https://claude.ai) (Anthropic).
