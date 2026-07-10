"""Constants for the mirAIe integration."""

DOMAIN = "miraie_in"
PACKAGE_NAME = "custom_components.miraie_in"

# Possible swing state
H0 = "H0"
H1 = "H1"
H2 = "H2"
H3 = "H3"
H4 = "H4"
H5 = "H5"

V0 = "V0"
V1 = "V1"
V2 = "V2"
V3 = "V3"
V4 = "V4"
V5 = "V5"

# Preset for Clean
PRESET_CLEAN = "clean"

# Preset for Converti
# Shared across both Converti variants.
PRESET_CONVERTI_C110 = "cv 110"
PRESET_CONVERTI_C100 = "cv 100"
PRESET_CONVERTI_C90 = "cv 90"
PRESET_CONVERTI_C80 = "cv 80"
PRESET_CONVERTI_C70 = "cv 70"
PRESET_CONVERTI_C40 = "cv 40"
PRESET_CONVERTI_C0 = "cv 0"

# Converti 7-in-1 only.
PRESET_CONVERTI_C55 = "cv 55"

# Converti 8-in-1 only (replaces the 55% step with 60%/50%).
PRESET_CONVERTI_C60 = "cv 60"
PRESET_CONVERTI_C50 = "cv 50"

# Converti 7-in-1 capacity steps: 110/100/90/80/70/55/40/0.
CONVERTI_7IN1_PRESET_MODES = [
    PRESET_CONVERTI_C110,
    PRESET_CONVERTI_C100,
    PRESET_CONVERTI_C90,
    PRESET_CONVERTI_C80,
    PRESET_CONVERTI_C70,
    PRESET_CONVERTI_C55,
    PRESET_CONVERTI_C40,
    PRESET_CONVERTI_C0,
]

# Converti 8-in-1 capacity steps: 110/100/90/80/70/60/50/40/0.
CONVERTI_8IN1_PRESET_MODES = [
    PRESET_CONVERTI_C110,
    PRESET_CONVERTI_C100,
    PRESET_CONVERTI_C90,
    PRESET_CONVERTI_C80,
    PRESET_CONVERTI_C70,
    PRESET_CONVERTI_C60,
    PRESET_CONVERTI_C50,
    PRESET_CONVERTI_C40,
    PRESET_CONVERTI_C0,
]

# --- Converti 7-in-1 vs 8-in-1 model support ---
#
# Verified directly against Panasonic's own store.in.panasonic.com
# /2025-model/ and /2026-model/ catalog pages (not third-party
# retailers/trackers, which were found to have inconsistent year
# labelling). Every model confirmed under the 2026 catalog is 8-in-1;
# every one still under 2025 is 7-in-1 -- but the generation letter
# that marks "2026" differs by series group:
#
#   Group A (NU, SU):      2025 = "A" (7-in-1)  ->  2026 = "B" (8-in-1)
#   Group B (EZ, HU, EU):  2025 = "B" (7-in-1)  ->  2026 = "C" (8-in-1)
#
# The generation letter is a per-series revision counter, not a
# fleet-wide year code -- it cannot be compared across series, only
# against its own group's threshold below. Only letters from the
# current (2024 onward) A/B/C cycle are recognised; older codes (e.g.
# "Z") are intentionally left unmapped and fall back to 7-in-1, since
# there's no evidence either way for that older generation and older
# models are out of scope for now.
_CONVERTI_LETTER_ORDER = {"A": 1, "B": 2, "C": 3}

CONVERTI_GROUP_A_SERIES = ("NU", "SU")
CONVERTI_GROUP_A_8IN1_THRESHOLD = "B"

CONVERTI_GROUP_B_SERIES = ("EZ", "HU", "EU")
CONVERTI_GROUP_B_8IN1_THRESHOLD = "C"

# Known gap: "QU" (e.g. CS-CU-QU26BKYFM) is a confirmed 7-in-1 model in
# the 2025 catalog, but not yet in either group above -- its 2026
# behaviour is unconfirmed. It currently falls through to the 7-in-1
# default, which is correct for the 2025 unit but unverified for any
# 2026 QU model. If you can confirm a 2026 QU model's Converti step
# count from an official Panasonic listing, please open an issue/PR.

# No confirmed exceptions to the pattern above at this time. An earlier
# version of this file listed CS-EU12BKY3FM as one, based on unverified
# early research -- Panasonic's own retailer listings (Croma, Amazon,
# and others) explicitly describe it as "7-in-1 Convertible", and it's
# correctly classified as 7-in-1 by the general rule below anyway (EU
# group threshold for 8-in-1 is "C"; EU12BKY3FM carries letter "B").
# If you find a real exception, please open an issue/PR with a link to
# an official Panasonic listing confirming it.
CONVERTI_8IN1_MODEL_EXCEPTIONS: set[str] = set()


def _extract_generation_letter(model_number: str, series: str) -> str | None:
    """Pull the single generation-letter character that follows a
    known series prefix in a model number, e.g. "EU18CKY5XFM" with
    series "EU" -> "C" (the letter right after the tonnage digits).
    """
    idx = model_number.find(series)
    if idx == -1:
        return None

    pos = idx + len(series)
    while pos < len(model_number) and model_number[pos].isdigit():
        pos += 1

    if pos < len(model_number) and model_number[pos].isalpha():
        return model_number[pos]

    return None


# --- Heat mode ("Hot & Cold") model support ---
#
# Verified directly against Panasonic's own store.in.panasonic.com
# listings: EZ-series and KZ-series models are explicitly labelled
# "Hot & Cold" in their product titles/descriptions. Series such as
# NU, SU, and HU carry no such designation and are cooling-only.
# Unlike Converti gating, this isn't generation-letter-dependent --
# every EZ/KZ model found (2024 through 2026 catalogs) supports heat,
# so a simple series-prefix match is sufficient. If a cooling-only
# EZ/KZ variant or a heat-capable model outside these two series turns
# up, please open an issue/PR with a link to the official listing.
HEAT_CAPABLE_SERIES = ("EZ", "KZ")


def supports_heat_mode(model_number: str | None) -> bool:
    """Return whether a given model supports heat ("Hot & Cold") mode."""
    if not model_number:
        return False

    model_number = model_number.upper()
    return any(series in model_number for series in HEAT_CAPABLE_SERIES)


def get_converti_preset_modes(model_number: str | None) -> list[str]:
    """Return the Converti preset list appropriate for a given model.

    See the comment block above CONVERTI_GROUP_A_SERIES for how this
    is derived. Falls back to the 7-in-1 preset set (the original
    stock behaviour) for anything unrecognised, so unknown or older
    models are never offered presets they can't actually use.
    """
    if not model_number:
        return CONVERTI_7IN1_PRESET_MODES

    model_number = model_number.upper()

    if model_number in CONVERTI_8IN1_MODEL_EXCEPTIONS:
        return CONVERTI_8IN1_PRESET_MODES

    for series_group, threshold in (
        (CONVERTI_GROUP_A_SERIES, CONVERTI_GROUP_A_8IN1_THRESHOLD),
        (CONVERTI_GROUP_B_SERIES, CONVERTI_GROUP_B_8IN1_THRESHOLD),
    ):
        for series in series_group:
            if series not in model_number:
                continue

            letter = _extract_generation_letter(model_number, series)
            if (
                letter in _CONVERTI_LETTER_ORDER
                and threshold in _CONVERTI_LETTER_ORDER
                and _CONVERTI_LETTER_ORDER[letter] >= _CONVERTI_LETTER_ORDER[threshold]
            ):
                return CONVERTI_8IN1_PRESET_MODES

    return CONVERTI_7IN1_PRESET_MODES


# --- Nanoe air purifier gating (Untested - no physical device to verify) ---
#
# nanoe-G and nanoe-X air purification technologies are available on premium
# series (primarily the XU series and HU Amaze Grey series) in the Panasonic
# India catalog.
NANOE_CAPABLE_SERIES = ("XU", "HU")


def supports_nanoe(model_number: str | None) -> bool:
    """Return whether a given model supports nanoe air purification."""
    if not model_number:
        return False

    model_number = model_number.upper()
    return any(series in model_number for series in NANOE_CAPABLE_SERIES)
