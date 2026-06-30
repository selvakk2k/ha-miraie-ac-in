"""Constants for the mirAIe integration."""

DOMAIN = "miraie"
PACKAGE_NAME = "custom_components.miraie"

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

# --- Converti 8-in-1 model support ---
# All 2026-range models use the "CKY" indoor-unit code and support
# Converti 8-in-1 (variable capacity) presets.
CONVERTI_8IN1_SERIES_MARKER = "CKY"

# A small number of 2025-range models (non-CKY) also support Converti 8-in-1.
# These are hard-coded exceptions until a more reliable capability flag
# becomes available from the MirAIe API/device details.
CONVERTI_8IN1_MODEL_EXCEPTIONS = {
    "CS-EU12BKY3FM",
    "CS-NU24BKY5W",
}


def get_converti_preset_modes(model_number: str | None) -> list[str]:
    """Return the Converti preset list appropriate for a given model.

    - 2026-range ("CKY") models and the known 2025 exceptions get the
      8-in-1 preset set (110/100/90/80/70/60/50/40/0).
    - All other recognised Converti-capable models fall back to the
      7-in-1 preset set (110/100/90/80/70/55/40/0), which was the
      original stock behaviour and remains correct for them.
    """
    if model_number and model_number.upper() in CONVERTI_8IN1_MODEL_EXCEPTIONS:
        return CONVERTI_8IN1_PRESET_MODES

    if model_number and CONVERTI_8IN1_SERIES_MARKER in model_number.upper():
        return CONVERTI_8IN1_PRESET_MODES

    return CONVERTI_7IN1_PRESET_MODES