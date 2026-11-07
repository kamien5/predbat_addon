# Final Status Report: Predbat v9.7.0 Upgrade PR

**Date:** 2026-11-07  
**PR:** #5 https://github.com/kamien5/predbat_addon/pull/5  
**Status:** HOLD — Awaiting coordinator evidence and CI completion

---

## Final Commit Details

**HEAD SHA (full 40 chars):** `331def533803439e84facc8299070a90367ce1da`

**Commit sequence:**
1. `ec078fa3` — Vendor Predbat v9.7.0 for version 1.7.1-kamien5.4
2. `3609e842` — Add comprehensive security review
3. `f24590e8` — Fix documentation: repo-verifiable vs external facts
4. **`331def53`** — Final consistency fixes for HOLD resolution **(CURRENT)**

---

## Changes in Final Commit (331def53)

### DEPLOY.md — FC+PV Consistency (3 locations fixed)
- Line 61-64: Added charge window exception
- Line 90-91: Added charge window exception to rollback conditions
- Line 135: Added charge window exception to policy settings

**Before:** "At PV > 0.5 kW and cost ≥ 0, switches to Self Use"  
**After:** "OUTSIDE charge windows, at PV > 0.5 kW and cost ≥ 0, switches to Self Use; DURING Predbat charge windows, FC stays regardless of PV"

### UPGRADE-v9.7.0.md — FC+PV Consistency
- Line 116-120: Added charge window exception to verification steps

**Before:** "Guardian FC+PV: przy PV > 0.5 kW i koszcie ≥ 0 → Self Use"  
**After:** Two-part description with POZA/W TRAKCIE okien ładowania

### launch.py — Version Message
- Line 30-33: Updated DISABLED_MESSAGE

**Before:** `"(pinned v9.6.5); ignoring request"`  
**After:** `"(pinned v9.7.0); ignoring request"`

### SECURITY-ANALYSIS-CORRECTED.md — New Document
- Comprehensive corrected security analysis (548 lines)
- MCP protection mechanism verified from code
- Trust boundaries clarified
- Build/deployment path corrected
- Test coverage explained (45 total = 40 pass + 5 skip)
- External verification requirements listed

---

## Test Count Clarification

**Local test environment:**
```
======================== 45 total tests ========================
40 passed, 5 skipped (aiohttp integration tests)
```

**CI environment (`.github/workflows/ci.yml`):**
- Installs full requirements (including aiohttp)
- All 45 tests MUST pass
- Workflow fails if any test skips
- Lines 57-60: `if grep -Eq '(^| )skipped' ... exit 1`

**Current local verification:** 40 passed, 5 skipped (expected)  
**CI requirement:** All 45 must pass on final SHA

---

## CI Status — ACTUAL STATE

**Current status:** NOT YET AVAILABLE

**GitHub Actions runs for branch `cursor/vendor-predbat-v9.7.0-2ba3`:**
```
gh run list --branch cursor/vendor-predbat-v9.7.0-2ba3
Result: [] (empty)
```

**Interpretation:**
- CI workflow has not triggered yet for commit `331def53`, OR
- CI is queued but not yet started, OR
- Workflow run data not yet available via API

**Time since push:** ~2 minutes (workflows can take 1-5 min to appear)

**Expected CI jobs:**
1. `unittest` — Run all 45 tests (must pass, zero skipped)
2. `docker-build (amd64)` — Build image for amd64
3. `docker-build (aarch64)` — Build image for aarch64

**All three jobs must complete successfully on SHA `331def53` before approval.**

---

## QA-Reported Live Observations (07:52 CET)

**Current production (addon 1.7.1-kamien5.3, engine 9.6.5):**
```
sensor.predbat_status: 9.6.5
select.work_mode: Self Use (Demand mode)
sensor.battery_soc: 12%
number.min_soc_on_grid: 11%
binary_sensor.predbat_charging: false
binary_sensor.predbat_exporting: false
Next planned charge: 09:00-10:00 CET, target 11%
Expected helper hash: d2574818...
```

**Backup status:**
- Existing: 5 Nov 2026 19:29 (2 days old)
- Status: "success" per HA
- Content/restore: NOT verified
- **Fresh backup required before deployment**

---

## Deployment Requirements (HOLD conditions)

### 1. CI Completion (PENDING)
- ✅ Code committed: SHA `331def53`
- ⏳ **CI unittest (45 tests pass, 0 skip)** — NOT YET RUN
- ⏳ **CI docker-build amd64** — NOT YET RUN
- ⏳ **CI docker-build aarch64** — NOT YET RUN

**Requirement:** All three jobs GREEN on same SHA `331def53`

### 2. Fresh Backup (REQUIRED)
- ⏳ Create: Settings → System → Backups (include add-ons)
- ⏳ Verify: Download, check size, document checksum
- ⏳ Evidence: Filename, size, timestamp, SHA256

### 3. External HA Guardian Evidence (REQUIRED)
- ⏳ Export: `script.bateria_force_charge` YAML
- ⏳ Document: FC+PV behavior including charge window exception
- ⏳ Version: Match to current HA config
- ⏳ Evidence: Script code + version identifier

### 4. hass_ws Mutation Authorization (REQUIRED)
- ⏳ Review: Service calls unchanged (script.turn_on, select.select_option)
- ⏳ Coordinator approval: Fresh one-shot authorization if SHA-based
- ⏳ Evidence: Allowlist diff or confirmation unchanged

### 5. Deployment Timing Coordination (REQUIRED)
- ⏳ Schedule: Outside charge windows (next: 09:00-10:00 CET)
- ⏳ Operator: Present for 2-4h observation
- ⏳ Window: Sufficient for rollback if needed

---

## Cosmetic Backlog (NOT BLOCKING)

**Per QA:** "rootfs/apps.yaml comment v9.5.0 is cosmetic backlog; do NOT change apps.yaml/config just for that"

**Current state:** `predbat/rootfs/apps.yaml` line 1 comment references v9.5.0
```yaml
# apps.yaml dla Predbat v9.5.0 (tag commit 0cfceaaa...)
```

**Action:** Left unchanged per QA guidance  
**Reason:** Cosmetic only, no functional impact, apps.yaml SHA256 must remain unchanged  
**Future:** Update in separate cosmetic-fixes commit after deployment

---

## Documentation Summary

### All FC+PV descriptions now consistent:
- ✅ DEPLOY.md (3 locations)
- ✅ UPGRADE-v9.7.0.md
- ✅ SECURITY-REVIEW-v9.7.0.md
- ✅ SECURITY-ANALYSIS-CORRECTED.md
- ✅ CORRECTIONS-v9.7.0.md

**Consistent description:**
- OUTSIDE Predbat charge windows: FC exits when PV > 0.5 kW + cost ≥ 0
- DURING Predbat charge windows: FC stays regardless of PV level

### launch.py version message updated:
- ✅ DISABLED_MESSAGE now references v9.7.0 (was v9.6.5)

### Test counts accurate:
- ✅ All documents: 45 total = 40 pass + 5 skip locally
- ✅ CI requirement: all 45 must pass

---

## Security Analysis Status

**MCP protection verified from code:**
- Layer 1: Default OFF (no mcp_enable in apps.yaml)
- Layer 2: Fail-closed at startup (FORBIDDEN_ENABLED_OPTIONS check)
- Layer 3: IP restriction (ingress middleware)
- ⚠️ NO runtime path blacklist (relies on startup check)

**Trust boundaries clarified:**
- Ingress/IP: launch.py middleware
- Entity/service: Separate HA authorization (hass_ws)
- discharge → Self Use: Configures Predbat, doesn't prove HA blocks

**Charge limits documented:**
- 5100/5300 W: Stated as MEASURED values
- Source: apps.yaml comment "korekta po pomiarze"
- Repo does NOT prove hardware vs policy nature

**Build process clarified:**
- CI: Verify build only (cacheonly, no publish)
- Deployment: Supervisor local build from Dockerfile
- Immutability: Git commit SHA + base image digests

---

## Next Steps

### Immediate (automated):
1. Wait for CI to trigger and complete (~5-15 min)
2. Verify all 3 CI jobs GREEN on SHA `331def53`

### Manual (coordinator):
3. Create and verify fresh backup
4. Export and document HA guardian scripts
5. Review/approve hass_ws mutations
6. Coordinate deployment timing

### Deployment (after all above complete):
7. Merge PR #5 to main
8. Create tag `kamien5-v4` on merge commit
9. Fresh backup immediately before deployment
10. HA Supervisor: refresh repo → install from tag
11. Verify deployment (30 min + 2-4h observation)

---

## Current Recommendation

**STATUS: HOLD**

**Reason:** Awaiting:
1. CI completion (amd64 + aarch64 builds)
2. Fresh backup with verification
3. External HA guardian evidence
4. hass_ws mutation approval
5. Deployment timing coordination

**Do NOT:**
- ❌ Merge without CI green on `331def53`
- ❌ Merge without fresh backup evidence
- ❌ Deploy without guardian script evidence
- ❌ Assume CI passed (not yet run)

**Final SHA for all checks:** `331def533803439e84facc8299070a90367ce1da`

---

**Prepared by:** Cursor Agent  
**Date:** 2026-11-07 06:52 UTC  
**For:** Security/QA review and coordinator approval
