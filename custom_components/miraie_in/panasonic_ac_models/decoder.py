import re
from typing import Dict, Any, Optional

PANASONIC_MODEL_REGEX = re.compile(
    r"^(?:CS[-_/\s]?CU|CS/CU|CS|CU|CW|S)?[-_\s]?"
    r"(?P<series>[A-Z]{2})"
    r"(?P<capacity>\d{2})"
    r"(?P<gen>[A-Z])"
    r"(?:KY)?"
    r"(?P<rating>\d)?"
    r"(?P<suffix>[A-Z0-9-]*)$",
    re.IGNORECASE
)

CAPACITY_MAP = {
    "09": "0.75T",
    "11": "0.9T",
    "12": "1T",
    "17": "1.4T",
    "18": "1.5T",
    "24": "2T",
    "26": "2.2T",
    "30": "2.5T",
}

HEAT_MODE_SERIES = {"EZ", "KZ"}
NANOE_SERIES = {"HU", "XU"}
NON_WIFI_SERIES = {"KN", "KU", "CW", "LN", "XN", "PD"}

def decode_model_string(model_code: str) -> Optional[Dict[str, Any]]:
    """Parses capability flags from a Panasonic AC model code string via deterministic rules."""
    cleaned = model_code.strip().upper()

    # CW- prefix = window AC — non-smart, no Wi-Fi, no converti regardless of variant
    if cleaned.startswith("CW"):
        return {
            "family_key": "CW-window",
            "series": "CW",
            "generation": None,
            "capacity_class": None,
            "speed_type": "fixed",
            "has_wifi": 0,
            "has_heat_mode": 0,
            "has_nanoe": 0,
            "converti_type": "none",
            "resolved_via": "regex_decoder"
        }

    match = PANASONIC_MODEL_REGEX.match(cleaned)
    if not match:
        return None

    data = match.groupdict()
    series = data["series"]
    gen = data["gen"]
    suffix = data.get("suffix", "")

    # Converti Generation Logic
    if series in {"EZ", "KZ", "HU", "EU", "AU"}:
        converti = "8-in-1" if gen >= "C" else "7-in-1"
    elif gen in {"B", "C"}:
        converti = "8-in-1"
    elif gen in {"Y", "Z", "A"}:
        converti = "7-in-1"
    else:
        converti = "none"

    is_non_wifi = (series in NON_WIFI_SERIES) or (series == "SU" and suffix.startswith("T")) or bool(re.search(r'-(?:1|2)$', cleaned))

    # Swing Type (2-way vs 4-way) Logic
    if series in {"KN", "LN", "XN", "PD", "CW"}:
        swing_type = "2-way"
    elif series in {"SU", "RU"}:
        swing_type = "2-way" if data["capacity"] in {"09", "11", "12", "17", "18"} else "4-way"
    else:
        swing_type = "4-way"

    return {
        "family_key": f"{series}-{data['capacity']}-{gen}",
        "series": series,
        "generation": gen,
        "capacity_class": CAPACITY_MAP.get(data["capacity"], f"{data['capacity']} Ton"),
        "speed_type": "fixed" if series in {"KN", "LN", "XN", "PD"} else "variable",
        "has_wifi": 0 if is_non_wifi else 1,
        "has_heat_mode": 1 if series in HEAT_MODE_SERIES else 0,
        "has_nanoe": 1 if series in NANOE_SERIES else 0,
        "converti_type": converti,
        "swing_type": swing_type,
        "resolved_via": "regex_decoder"
    }

