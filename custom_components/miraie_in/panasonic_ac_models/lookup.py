import json
import os
import re
from typing import Dict, Any, Optional
from .decoder import decode_model_string

PKG_DIR = os.path.dirname(__file__)
PARENT_DIR = os.path.dirname(PKG_DIR)

DEFAULT_JSON_PATH = os.path.join(PKG_DIR, "models.json")
if not os.path.exists(DEFAULT_JSON_PATH):
    DEFAULT_JSON_PATH = os.path.join(PARENT_DIR, "models.json")


def normalize_code(raw_code: str) -> str:
    """Normalizes input model strings across Split (CS-), Window (CW-), and Cassette (S-) formats."""
    cleaned = raw_code.strip().upper()
    
    # Window AC series (LN, XN, CW)
    if re.search(r'(?:CW|LN|XN)', cleaned):
        body = re.sub(r'^(CS[-_/\s]?CU|CS/CU|CS|CU|CW)[-_\s]?', '', cleaned)
        return f'CW-{body}'
        
    # Commercial Cassette / Ductable series (S-18PU..., S-24PD...)
    if cleaned.startswith('S-') or re.search(r'\d{2}P[UD]', cleaned):
        body = re.sub(r'^(CS[-_/\s]?CU|CS/CU|CS|CU|S)[-_\s]?', '', cleaned)
        return f'S-{body}'

    # Standard Split AC series (CS-)
    body = re.sub(r'^(CS[-_/\s]?CU|CS/CU|CS|CU)[-_\s]?', '', cleaned)
    return f'CS-{body}'


class ACModelLookup:
    """O(1) normalized lookup engine for Panasonic AC models."""

    def __init__(self, json_path: Optional[str] = None):
        path = json_path or DEFAULT_JSON_PATH
        with open(path, "r", encoding="utf-8") as f:
            self.db = json.load(f)

        # O(1) Normalized Lookup Index
        self._index: Dict[str, Dict[str, Any]] = {}
        for family in self.db.get("families", []):
            for unit in family.get("indoor_units", []):
                norm = normalize_code(unit)
                self._index[norm] = family

    def get_capabilities(self, model_code: str) -> Dict[str, Any]:
        """Resolves capability flags using exact index matching or regex decoding."""
        norm = normalize_code(model_code)

        # 1. Exact Match from Index
        if norm in self._index:
            result = dict(self._index[norm])
            result["resolved_via"] = "database"
            # Suffix-level override: -1 and -2 variants (e.g. CS-RU18CKY-1), plus SU-T series are non-Wi-Fi IR models
            if re.search(r'-(?:1|2)$', norm) or (result.get("series") == "SU" and re.search(r'T[A-Z0-9-]*$', norm)):
                result["has_wifi"] = 0
            return result

        # 2. Dynamic Fallback
        dynamic = decode_model_string(model_code)
        if dynamic:
            return dynamic

        # 3. Default Safe Fallback
        return {
            "family_key": "UNKNOWN",
            "has_wifi": 1,
            "has_heat_mode": 0,
            "has_nanoe": 0,
            "converti_type": "7-in-1",
            "resolved_via": "safe_default"
        }
