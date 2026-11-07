# Task: Remove 5kW Hardcoded Charging Cap from External HA Guardian

**Scope:** SEPARATE from PR #5 vendor upgrade  
**Ordered:** 2026-11-07 08:07 CET by Piotr  
**Type:** External HA automation patch  
**Status:** PENDING source files  

---

## Requirement

Remove hardcoded `5.0` cap from external HA charging power calculations while preserving ALL safety guards:
- 15kW whole-house cap (grid limit)
- 25A per-phase cap (with existing 23A headroom margin)  
- Hardware/BMS dynamic ceiling (sensor-driven)
- 11% min SoC enforcement
- No forced battery export
- FC Charging* PV-block exception

**Desired:** Charging power = `min(Predbat_request, dynamic_BMS_limit, phase_headroom_kW, 15kW_house_total)`

**Current:** Power = `min(Predbat_request, dynamic_BMS_limit, phase_headroom_kW, 5.0)` ← hardcoded cap

---

## Evidence from Live Traces (2026-11-07 08:05 CET)

### Affected Automation/Script

**automation.bateria_straznik_przepisanie**
- Config SHA256: `3dba333910657ee82ad33826463b6c1885adb64c34fd6a935a984eec416a8850`
- Trace: 2026-11-07 08:00:00 CET
- Current formula: `Power = min(request, dynamic_limit, phase_headroom, 5.0)`
- Phase headroom: `max(0, (23 - max(L1,L2,L3) + estimated_battery_A) * 690/1000)`

**script.bateria_force_charge**  
- Config SHA256: `47329b0d8991e89252a938c100366b44025ac7ced0934cc34e3afebbfd970f51`
- Trace: 2026-11-07 03:30:04–08 CET
- Same formula includes `5.0` cap
- Writes to: `number.force_charge_power` (gated by data validity)

**Live State (08:05:02 CET):**
- `force_charge_power`: 5.0 kW (capped)
- `dynamic_grid_charge_limit`: 5.46 kW (calculated from BMS/phase)
- Actual limit used: 5.0 kW (hardcoded minimum wins)

---

## Desired Minimal Change

### Remove from automation.bateria_straznik_przepisanie
```yaml
# CURRENT (lines approximate, awaiting actual YAML):
power: >
  {{ min(
      states('input_number.predbat_charge_rate_request')|float(0),
      states('input_number.bateria_dynamiczny_limit_ladowania_z_sieci')|float(0),
      phase_headroom_calculation,
      5.0
  ) | round(2) }}

# DESIRED:
power: >
  {{ min(
      states('input_number.predbat_charge_rate_request')|float(0),
      states('input_number.bateria_dynamiczny_limit_ladowania_z_sieci')|float(0),
      phase_headroom_calculation,
      15.0  # whole-house cap, not battery-specific cap
  ) | round(2) }}
```

**OR** remove `5.0` entirely if 15kW house limit is enforced elsewhere.

### Remove from script.bateria_force_charge
Same change in corresponding power calculation.

---

## Preservation Requirements

### MUST Keep Unchanged

1. **Phase current safety:**
   - 23A headroom margin preserved
   - Formula: `(23 - max(L1,L2,L3) + battery_contribution) * 690/1000`
   - This already enforces 25A limit per phase (23A + ~2A margin)

2. **House total cap:**
   - 15kW whole-house limit must remain enforced
   - Check if enforced in this formula or elsewhere (awaiting source review)

3. **Dynamic BMS limit:**
   - `input_number.bateria_dynamiczny_limit_ladowania_z_sieci` (5.46kW at trace time)
   - Calculated from sensor data, changes dynamically

4. **Data validity gates:**
   - `dane_ok` check (requires known Predbat status, valid phase currents, no missing flags)
   - Writes gated by validity
   - Invalid data → no power change (fail-safe)

5. **FC Charging* exception:**
   - `pred_chg` (predicted charging) bypasses PV block
   - Already implemented correctly per traces

6. **11% min SoC:**
   - Enforced by `automation.bateria_watchdog_failsafe`
   - Not modified in this task

7. **No forced export:**
   - Export-block automation (enabled, not traced)
   - Not modified in this task

### Test Requirements

**After 5kW cap removal, verify:**

1. **>5kW charging possible:**
   - When Predbat requests 5.5kW
   - AND dynamic limit > 5.5kW (e.g., 5.8kW)
   - AND phase headroom > 5.5kW (e.g., all phases < 18A)
   - AND house total < 15kW (e.g., 8kW consumed, 7kW available)
   - THEN: charge at 5.5kW (not capped to 5.0)

2. **Phase safety preserved:**
   - Any phase approaches 23A → power reduced
   - Never exceeds 25A on any phase

3. **House cap enforced:**
   - Total consumption + charge power never exceeds 15kW
   - Test with CWU (domestic hot water) ~3.2kW running
   - Test with future EV charging scenario

4. **BMS limit respected:**
   - If dynamic limit drops to 4.8kW → charge at 4.8kW (not 5.0)
   - Verifies BMS limit still has priority

5. **Fail-closed on invalid data:**
   - Missing phase current → no power change
   - Missing Predbat status → no power change
   - Unchanged behavior (not bypassed by 5kW removal)

---

## Blocked: Awaiting Source Files

**Cannot implement without:**

1. **Current YAML files:**
   - `automation.bateria_straznik_przepisanie` (full config export)
   - `script.bateria_force_charge` (full config export)
   - Related helpers: phase current sensors, dynamic limit calculation

2. **Helper baseline:**
   - Current hass_ws.py hash: `d2574818...` (confirmed)
   - Mutation approval mechanism for HA config changes
   - Test harness for validation

3. **House total enforcement location:**
   - Is 15kW cap in these automations or separate?
   - Where is CWU 3.2kW accounted for?
   - How is future EV load planned?

**Do NOT fabricate YAML from trace descriptions** — need actual byte-for-byte source exports.

---

## Implementation Plan (Once Sources Available)

### Phase 1: Source Analysis
1. Receive full YAML exports of affected automations/scripts
2. Identify exact lines with `5.0` hardcode
3. Verify 15kW house cap enforcement location
4. Map all safety guards (phase, BMS, validity, fail-closed)

### Phase 2: Patch Design
1. Remove `5.0` from min() calculations
2. Add/verify 15kW house cap (if not already enforced)
3. Preserve all other safety guards
4. Design test cases for validation

### Phase 3: Testing (Pre-Deployment)
1. Dry-run with test scenarios (5.5kW request with valid conditions)
2. Verify phase limits not exceeded in simulation
3. Verify house cap enforced
4. Verify fail-closed behavior unchanged

### Phase 4: Deployment
1. Fresh backup (separate from addon upgrade backup)
2. Apply automation changes via HA UI or YAML mode
3. Reload automations
4. Test in live system during low-risk window
5. Monitor for 24h, rollback if issues

---

## Coordination with PR #5 Vendor Upgrade

**SEPARATE tasks:**
- **PR #5:** Vendor Predbat v9.6.5 → v9.7.0 (addon code)
- **This task:** Remove 5kW cap (external HA automations)

**No dependencies:**
- Can deploy PR #5 without this task
- Can deploy this task without PR #5
- Or deploy both together (coordinator choice)

**Shared evidence:**
- Guardian traces used for both analyses
- Both require backup before deployment
- Both require post-deployment monitoring

**Documentation:**
- PR #5: DEPLOYMENT-PROVENANCE.md, DEPLOYMENT-BLOCKERS.md
- This task: TASK-5KW-CAP-REMOVAL.md (this file)

---

## Current Status

**Scoped:** 2026-11-07 08:07 CET by Piotr  
**Source files:** PENDING (being gathered)  
**Implementation:** BLOCKED until sources received  
**Testing plan:** Defined (pending implementation)  
**Deployment:** BLOCKED until testing complete

**Do NOT claim implemented.** This is a separate pending task.

---

**Prepared by:** Cursor Agent  
**Date:** 2026-11-07  
**Status:** Awaiting source files for implementation  
**Related:** PR #5 vendor upgrade (separate task, progressing in parallel)
