"""Universal IR Generator Engine for Panasonic Air Conditioners.

Supports output formats:
- raw: Microsecond pulse interval array (for Home Assistant `infrared` platform / ESPHome)
- ahea: Hex string and Tasmota JSON payload
- broadlink: Base64 encoded payload for Broadlink RM4 / RM Pro
- tuya: Base64 encoded payload for Tuya IR blasters
- pronto: Raw Pronto Hex string
"""

import base64
import struct
from typing import Dict, List, Any, Optional, Union

# Base Physical Pulse Template for COOL mode (24°C, Low Fan, V1 Vane)
COOL_PHYSICAL_PULSES = [
    3435, -1749, 469, -437, 438, -1312, 437, -469, 469, -437, 437, -438, 437, -469, 437, -469,
    468, -407, 437, -468, 438, -469, 437, -437, 438, -468, 469, -437, 469, -1281, 437, -469,
    437, -438, 468, -437, 438, -468, 438, -437, 438, -468, 439, -470, 435, -1312, 468, -1312,
    469, -1281, 437, -469, 437, -437, 469, -1312, 438, -437, 469, -437, 437, -500, 438, -406,
    468, -438, 437, -500, 406, -469, 437, -469, 406, -500, 406, -469, 437, -468, 407, -499,
    407, -468, 438, -468, 438, -437, 469, -437, 437, -438, 437, -500, 438, -437, 437, -469,
    406, -500, 437, -438, 437, -481, 425, -468, 407, -468, 438, -468, 438, -472, 434, -437,
    437, -469, 437, -438, 469, -1312, 406, -1343, 469, -437, 438, -468, 438, -437, 469, -437,
    437, -469, 406, -9997, 3499, -1750, 437, -468, 438, -1312, 437, -469, 437, -469, 406, -469,
    437, -469, 406, -503, 434, -437, 438, -469, 437, -469, 437, -437, 438, -468, 452, -454,
    438, -1312, 473, -433, 406, -483, 437, -500, 392, -468, 438, -437, 469, -437, 438, -468,
    406, -1344, 437, -1346, 404, -1343, 406, -500, 437, -469, 406, -1344, 437, -469, 406, -468,
    438, -472, 434, -468, 438, -437, 437, -469, 406, -500, 406, -469, 437, -469, 437, -469,
    406, -468, 438, -474, 404, -496, 406, -1350, 431, -469, 406, -500, 406, -1343, 406, -1344,
    437, -1343, 407, -499, 406, -469, 437, -469, 406, -1344, 437, -469, 406, -501, 406, -1344,
    407, -1344, 469, -437, 407, -500, 406, -469, 469, -438, 437, -469, 407, -468, 469, -438,
    406, -501, 437, -438, 438, -1344, 438, -1313, 437, -469, 438, -469, 440, -435, 406, -1376,
    437, -438, 438, -1344, 406, -469, 438, -469, 438, -1313, 437, -469, 406, -1345, 469, -437,
    407, -500, 438, -437, 438, -469, 406, -501, 406, -469, 438, -468, 407, -500, 438, -437,
    438, -469, 406, -500, 407, -469, 437, -469, 438, -1313, 437, -1344, 438, -1313, 438, -469,
    437, -438, 438, -469, 406, -500, 406, -500, 438, -438, 406, -500, 438, -437, 469, -441,
    435, -1344, 406, -1356, 426, -1313, 437, -469, 407, -500, 437, -438, 438, -469, 437, -470,
    409, -465, 438, -469, 406, -500, 407, -469, 437, -469, 438, -469, 406, -469, 438, -469,
    406, -500, 406, -469, 438, -469, 406, -1344, 438, -469, 406, -501, 406, -1344, 407, -500,
    406, -469, 438, -469, 406, -1344, 438, -469, 441, -465, 407, -469, 445, -461, 407, -500,
    406, -469, 438, -469, 406, -502, 405, -469, 437, -469, 406, -501, 406, -469, 438, -469,
    406, -469, 437, -469, 407, -500, 406, -1344, 407, -1375, 407, -468, 438, -469, 406, -501,
    406, -469, 406, -1376, 406, -1344, 407
]

# Dedicated 16-Byte Short Frames for Special Commands (Byte 13 & Byte 14 index mapping per reverse engineering spec)
SHORT_FRAME_COMMANDS = {
    "powerful":     (0x86, 0x35, "SPECIAL FEATURE: POWERFUL / TURBO"),
    "display":      (0x9E, 0x32, "SPECIAL FEATURE: DISPLAY LED TOGGLE"),
    "clean":        (0xCB, 0xF2, "SPECIAL FEATURE: SELF CLEAN"),
    "converti_110": (0x01, 0xAA, "CONVERTI MODE: 110% HIGH CAPACITY"),
    "converti_100": (0x02, 0xAA, "CONVERTI MODE: 100% FULL CAPACITY"),
    "converti_90":  (0x03, 0xAA, "CONVERTI MODE: 90% CAPACITY"),
    "converti_80":  (0x04, 0xAA, "CONVERTI MODE: 80% CAPACITY"),
    "converti_70":  (0x05, 0xAA, "CONVERTI MODE: 70% CAPACITY"),
    "converti_60":  (0x08, 0xAA, "CONVERTI MODE: 60% CAPACITY"),
    "converti_55":  (0x08, 0xAA, "CONVERTI MODE: 55% CAPACITY"),
    "converti_50":  (0x09, 0xAA, "CONVERTI MODE: 50% CAPACITY"),
    "converti_40":  (0x07, 0xAA, "CONVERTI MODE: 40% CAPACITY"),
    "converti_0":   (0x07, 0xAA, "CONVERTI MODE: MIN CAPACITY"),
}

def _pulses_to_bytes(pulses: List[int]) -> List[int]:
    bytes_list = []
    current_byte = 0
    bit_count = 0
    idx = 0
    while idx < len(pulses) - 1:
        m, s = pulses[idx], pulses[idx+1]
        if (m > 3000 and -2000 < s < -1500) or s < -8000:
            if bit_count > 0:
                bytes_list.append(current_byte)
                current_byte = 0
                bit_count = 0
            idx += 2
            continue
        if m > 0 and s < 0:
            bit = 1 if abs(s) > 800 else 0
            current_byte |= (bit << bit_count)
            bit_count += 1
            if bit_count == 8:
                bytes_list.append(current_byte)
                current_byte = 0
                bit_count = 0
        idx += 2
    if bit_count > 0:
        bytes_list.append(current_byte)
    return bytes_list

def pulses_to_broadlink_b64(pulses: List[int], tick: float = 32.84) -> str:
    """Encodes microsecond pulses to Broadlink RM4/RM Pro Base64 format."""
    broadlink_data = bytearray([0x26, 0x00])
    payload = bytearray()
    for p in pulses:
        val = int(round(abs(p) / tick))
        if val > 255:
            payload.append(0x00)
            payload.append((val >> 8) & 0xFF)
            payload.append(val & 0xFF)
        else:
            payload.append(val & 0xFF)
    payload.extend([0x0D, 0x05])
    pad = (-len(payload)) % 16
    payload.extend([0x00] * pad)
    broadlink_data.extend(struct.pack("<H", len(payload)))
    broadlink_data.extend(payload)
    return base64.b64encode(broadlink_data).decode("utf-8")

def pulses_to_tuya_b64(pulses: List[int]) -> str:
    """Encodes microsecond pulses to Tuya IR Base64 format."""
    raw_bytes = bytearray()
    for p in pulses:
        val = min(65535, abs(int(round(p))))
        raw_bytes.extend(struct.pack(">H", val))
    return base64.b64encode(raw_bytes).decode("utf-8")

def pulses_to_pronto_hex(pulses: List[int], frequency: int = 38000) -> str:
    """Encodes microsecond pulses to Pronto Hex string format."""
    freq_code = int(round(1000000.0 / (frequency * 0.241246)))
    pronto = [0x0000, freq_code]
    pairs = []
    for i in range(0, len(pulses)-1, 2):
        m_ticks = int(round(abs(pulses[i]) / (1000000.0 / frequency)))
        s_ticks = int(round(abs(pulses[i+1]) / (1000000.0 / frequency)))
        pairs.append((m_ticks, s_ticks))
    pronto.append(len(pairs))
    pronto.append(0x0000)
    for m, s in pairs:
        pronto.append(m)
        pronto.append(s)
    return " ".join([f"{x:04X}" for x in pronto])

def bytes_to_ahea_hex(bytes_list: List[int]) -> str:
    """Formats byte list to Panasonic AHEA Hex string (e.g. 0x02201000...)."""
    hex_str = "".join([f"{x:02X}" for x in bytes_list])
    return f"0x{hex_str}"

def bytes_to_short_frame_pulses(b: List[int]) -> List[int]:
    """Encodes a 16-byte Panasonic short-frame byte list to raw microsecond pulses."""
    pulses = [3435, -1749]
    for byte_val in b[:8]:
        for bit_i in range(8):
            bit = (byte_val >> bit_i) & 1
            pulses.append(438)
            pulses.append(-1344 if bit == 1 else -469)
    pulses.extend([406, -9997, 3499, -1750])
    for byte_val in b[8:]:
        for bit_i in range(8):
            bit = (byte_val >> bit_i) & 1
            pulses.append(438)
            pulses.append(-1344 if bit == 1 else -469)
    pulses.append(438)
    return pulses

def generate_ir_code(
    mode: str = "cool",
    target_temp: int = 24,
    fan: str = "low",
    v_vane: str = "V1",
    h_vane: Optional[str] = None,
    eco: bool = False,
    nanoe: bool = False,
    series: str = "EU"
) -> Dict[str, Any]:
    mode_key = mode.lower()

    # 1. Handle Special 16-Byte Short Frame Commands
    if mode_key in SHORT_FRAME_COMMANDS:
        b13, b14, label = SHORT_FRAME_COMMANDS[mode_key]
        header2 = [0x02, 0x20, 0xE0, 0x04, 0x80, b13, b14]
        checksum = sum(header2) & 0xFF
        b = [0x02, 0x20, 0xE0, 0x04, 0x00, 0x00, 0x00, 0x06, 0x02, 0x20, 0xE0, 0x04, 0x80, b13, b14, checksum]
        pulses = bytes_to_short_frame_pulses(b)
        ahea = bytes_to_ahea_hex(b)
        return {
            "raw": pulses,
            "ahea_hex": ahea,
            "tasmota_json": f'{{"Protocol":"PANASONIC_AC","Bits":128,"Data":"{ahea}"}}',
            "broadlink_b64": pulses_to_broadlink_b64(pulses),
            "tuya_b64": pulses_to_tuya_b64(pulses),
            "pronto_hex": pulses_to_pronto_hex(pulses),
            "description": label
        }

    # 2. Build Standard Full 27-Byte Frame
    b = _pulses_to_bytes(COOL_PHYSICAL_PULSES)
    series_upper = series.upper()

    if series_upper in ["HU", "VU", "WU"]:
        mode_map = {"cool": 0x31, "heat": 0x41, "dry": 0x21, "fan_only": 0x61, "fan": 0x61, "auto": 0x01, "off": 0x30}
        b[23] = 0x8C
        series_label = f"{series_upper} Premium Series"
    elif series_upper in ["EZ", "KZ"]:
        mode_map = {"cool": 0x39, "heat": 0x49, "dry": 0x29, "fan_only": 0x69, "fan": 0x69, "auto": 0x09, "off": 0x38}
        b[23] = 0x89
        series_label = f"{series_upper} Hot & Cold Series"
    else:
        mode_map = {"cool": 0x39, "heat": 0x49, "dry": 0x29, "fan_only": 0x69, "fan": 0x69, "auto": 0x09, "off": 0x38}
        b[23] = 0x89
        series_label = f"{series_upper} Series"

    b[13] = mode_map.get(mode_key, 0x39)

    if mode_key not in ["fan_only", "fan"]:
        t_val = max(16, min(30, int(target_temp)))
        b[14] = (t_val - 16) * 2 + 0x20

    if mode_key == "dry":
        fan_nibble = 0x3
    else:
        fan_nibble_map = {"quiet": 0x2, "off": 0x2, "low": 0x3, "mid": 0x5, "medium": 0x5, "high": 0x7, "auto": 0xA}
        fan_nibble = fan_nibble_map.get(str(fan).lower(), 0x3)

    v_nibble_map = {"V0": 0xF, "V1": 0x1, "V2": 0x2, "V3": 0x3, "V4": 0x4, "V5": 0x5, "AUTO": 0xF}
    v_nibble = v_nibble_map.get(str(v_vane).upper(), 0x1)
    b[16] = (fan_nibble << 4) | v_nibble

    single_vane_h_map = {"V0": 0x0D, "V1": 0x06, "V2": 0x09, "V3": 0x0A, "V4": 0x0B, "V5": 0x0C, "AUTO": 0x0D}
    h_map = {"H0": 0x0D, "H1": 0x06, "H2": 0x09, "H3": 0x0A, "H4": 0x0B, "H5": 0x0C, "AUTO": 0x0D}

    if h_vane is None and str(v_vane).upper() in single_vane_h_map:
        b[17] = single_vane_h_map[str(v_vane).upper()]
        louver_type = "Single-Vane"
    else:
        h_upper = str(h_vane).upper() if h_vane else "H0"
        b[17] = h_map.get(h_upper, 0x0D)
        louver_type = "Dual-Vane"

    # Preset / Convertible Byte (Byte 21 -> Frame 2 Byte 13)
    preset_byte = 0x00
    if mode_key in ("powerful", "boost"):
        preset_byte = 0x01
    elif eco:
        preset_byte = 0x02
    elif mode_key.startswith("converti_"):
        perc = mode_key.split("_")[1]
        perc_map = {
            "110": 0x03,
            "100": 0x00,
            "90": 0x04,
            "80": 0x05,
            "70": 0x06,
            "55": 0x07,
            "50": 0x07,
            "40": 0x08,
        }
        preset_byte = perc_map.get(perc, 0x00)
    else:
        preset_byte = 0x00

    b[21] = preset_byte
    b[22] = 0x08 if eco else 0x00
    b[24] = 0x01 if nanoe else 0x00
    b[26] = sum(b[8:26]) & 0xFF

    # Patch frame 2 pulses
    gap_idx = 0
    for i, p in enumerate(COOL_PHYSICAL_PULSES):
        if p < -8000:
            gap_idx = i
            break

    bit_start_idx = gap_idx + 3
    new_pulses = list(COOL_PHYSICAL_PULSES)

    def set_frame2_byte(byte_offset_in_f2, byte_val):
        bit_base = bit_start_idx + (byte_offset_in_f2 * 8 * 2)
        for bit_i in range(8):
            bit_val = (byte_val >> bit_i) & 1
            space_idx = bit_base + (bit_i * 2) + 1
            if bit_val == 1:
                new_pulses[space_idx] = -1344
            else:
                new_pulses[space_idx] = -469

    set_frame2_byte(5, b[13])
    set_frame2_byte(6, b[14])
    set_frame2_byte(7, b[15])
    set_frame2_byte(8, b[16])
    set_frame2_byte(9, b[17])
    set_frame2_byte(13, b[21])
    set_frame2_byte(14, b[22])
    set_frame2_byte(15, b[23])
    set_frame2_byte(16, b[24])
    set_frame2_byte(18, b[26])

    ahea = bytes_to_ahea_hex(b)
    desc = f"{series_label} | {mode_key.upper()} {target_temp}°C (Fan: {fan}, V-Vane: {v_vane}, H-Vane: {h_vane or 'Mirrored'} [{louver_type}], ECO: {'ON' if eco else 'OFF'}, NANOE: {'ON' if nanoe else 'OFF'})"

    return {
        "raw": new_pulses,
        "ahea_hex": ahea,
        "tasmota_json": f'{{"Protocol":"PANASONIC_AC","Bits":216,"Data":"{ahea}"}}',
        "broadlink_b64": pulses_to_broadlink_b64(new_pulses),
        "tuya_b64": pulses_to_tuya_b64(new_pulses),
        "pronto_hex": pulses_to_pronto_hex(new_pulses),
        "description": desc
    }
