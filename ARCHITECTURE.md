# MirAIe India 2.0 — Architecture & Migration Reference

This document outlines the architectural design decisions, migration mechanics, and registry continuity model implemented in MirAIe India 2.0.

---

## 1. Per-Device `ConfigEntry` Architecture

MirAIe India 2.0 models each physical AC unit as an independent, top-level `ConfigEntry` (`domain: "miraie_in"`).

### Design Rationale
1. **Symmetric Support for Wi-Fi & Standalone IR Models**:
   - Standalone IR-only units have no Panasonic cloud account credentials.
   - Using top-level `ConfigEntry` per device ensures that Standalone IR units and Wi-Fi Cloud units share the exact same first-class entry lifecycle, options flow, and entity registration architecture.
2. **Native Per-Device Options Flow & Settings Cog**:
   - In Home Assistant (**Settings → Devices & Services → MirAIe India**), every AC unit features its own dedicated `Configure (Settings Cog)` button.
   - Clicking Configure directly manages that specific AC unit's options:
     - IR Blaster entity selection (`blaster_entity_id`)
     - Primary transport backend (`primary_backend`: Cloud vs IR)
     - Hybrid failover mode (`hybrid_submode`: Auto vs Manual)
     - Energy history start date (`install_date`)
3. **Decoupled Lifecycle**:
   - Users can delete, disable, or reconfigure a single AC unit without impacting or re-authenticating other units on the account.

---

## 2. Legacy v1.x Auto-Split Migration Protocol

### Detection
Legacy v1.x single-parent account entries are automatically identified on startup during `async_setup_entry`:
```python
if "device_id" not in entry.data:
    # Legacy flat account entry detected
```

### Execution & Safety Guarantees
1. **Option Extraction & Inheritance**:
   - For each discovered device, the auto-split routine extracts device-specific overrides from `entry.options["devices"][device.id]` and falls back to account-level settings (`entry.options["install_date"]`, `entry.options["blaster_entity_id"]`, etc.).
2. **Per-Device Exception Isolation**:
   - Each device creates its independent entry via `await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_IMPORT}, data={..., "options": new_options})` wrapped inside its own `try/except` block.
3. **Guarded Parent Removal**:
   - The legacy parent entry is **only** removed if **all** discovered devices successfully create their new entries.
   - If any device fails to migrate, the legacy parent entry is **preserved intact** to prevent any configuration or data loss, and a Home Assistant Repair Issue (`manual_migration_required`) is generated.

---

## 3. Entity & Registry Continuity

### Deterministic Unique IDs
Entity `unique_id`s are strictly deterministic based on the hardware `device_id`:
- **Climate Entity**: `f"{device_id}"`
- **Energy Statistics Sensor**: `f"{device_id}_energy_history"`
- **Auxiliary Controls**: `f"{device_id}_display"`, `f"{device_id}_nanoe"`, `f"{device_id}_hybrid_submode"`, `f"{device_id}_active_backend"`
- **Diagnostics**: `f"{device_id}_wifi_signal"`, `f"{device_id}_last_controlled_via"`

### Long-Term Energy Statistics
Because `unique_id` strings are byte-for-byte identical to v1.x, Home Assistant's Entity Registry and `recorder` long-term statistics attach to the exact same database records without creating duplicate or orphaned entities.
