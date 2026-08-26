import ast
import json
import os
import re
import pytest

INTEGRATION_DIR = os.path.join(os.path.dirname(__file__), "../custom_components/miraie_in")
STRINGS_PATH = os.path.join(INTEGRATION_DIR, "strings.json")
TRANSLATIONS_PATH = os.path.join(INTEGRATION_DIR, "translations/en.json")


def _get_leaf_keys(d, prefix=""):
    keys = set()
    for k, v in d.items():
        full = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            keys.update(_get_leaf_keys(v, full))
        else:
            keys.add(full)
    return keys


def test_strings_json_and_en_json_parity():
    """Verify strings.json and translations/en.json have identical key schemas."""
    with open(STRINGS_PATH, "r", encoding="utf-8") as f:
        strings = json.load(f)
    with open(TRANSLATIONS_PATH, "r", encoding="utf-8") as f:
        translations = json.load(f)

    strings_keys = _get_leaf_keys(strings)
    translations_keys = _get_leaf_keys(translations)

    diff_st = strings_keys - translations_keys
    diff_ts = translations_keys - strings_keys

    assert not diff_st, f"Keys present in strings.json but missing in en.json: {diff_st}"
    assert not diff_ts, f"Keys present in en.json but missing in strings.json: {diff_ts}"


def test_entity_translation_keys_in_strings_json():
    """Verify that all _attr_translation_key attributes in platforms are declared in strings.json."""
    with open(STRINGS_PATH, "r", encoding="utf-8") as f:
        strings = json.load(f)

    entity_strings = strings.get("entity", {})

    platforms = ["sensor", "binary_sensor", "switch", "button"]
    for platform in platforms:
        py_file = os.path.join(INTEGRATION_DIR, f"{platform}.py")
        if not os.path.exists(py_file):
            continue

        with open(py_file, "r", encoding="utf-8") as f:
            code = f.read()

        found_keys = re.findall(r'_attr_translation_key\s*=\s*[\'"]([^\'"]+)[\'"]', code)
        declared_keys = set(entity_strings.get(platform, {}).keys())

        for key in found_keys:
            assert key in declared_keys, (
                f"Platform '{platform}.py' uses translation_key '{key}', but it is missing "
                f"under entity.{platform} in strings.json"
            )


def test_no_common_spelling_typos():
    """Scan all integration Python and JSON files for common typos."""
    common_typos = [
        "temparature",
        "celcius",
        "horisontal",
        "verticle",
        "desription",
        "unsuccesful",
        "recieve",
        "untill",
        "blater",
        "controll",
        "convertable",
    ]

    typos_found = []
    for root, _, files in os.walk(INTEGRATION_DIR):
        for file in files:
            if file.endswith((".py", ".json")):
                full_path = os.path.join(root, file)
                with open(full_path, "r", encoding="utf-8", errors="ignore") as fh:
                    content = fh.read()
                    for typo in common_typos:
                        if re.search(rf"\b{typo}\b", content, re.IGNORECASE):
                            typos_found.append((file, typo))

    assert not typos_found, f"Common spelling typos found in integration: {typos_found}"


def test_strings_capitalization():
    """Verify that all strings in strings.json begin with an uppercase character or valid placeholder."""
    with open(STRINGS_PATH, "r", encoding="utf-8") as f:
        strings = json.load(f)

    def verify_capitalization(d, path=""):
        for k, v in d.items():
            curr_path = f"{path}.{k}" if path else k
            if isinstance(v, dict):
                verify_capitalization(v, curr_path)
            elif isinstance(v, str) and v.strip():
                # Allow placeholder / bracket syntax like [%key:...%], {device_name}, **{device_name}**
                stripped = v.strip()
                if not (stripped.startswith(("[%key", "{", "**{"))):
                    first_alpha = next((c for c in stripped if c.isalpha()), None)
                    if first_alpha:
                        assert first_alpha.isupper(), (
                            f"String at {curr_path} does not start with an uppercase letter: '{v}'"
                        )

    verify_capitalization(strings)
