# Deployment and Rollback Procedure

This document describes the safe deployment and rollback procedure for Predbat add-on updates in the kamien5 fork.

## Pre-deployment Checklist

### 1. Backup (MANDATORY)

Before any upgrade:

1. Create a full Home Assistant backup: **Settings → System → Backups → Create backup** (include add-ons)
2. Record current state:
   - Version from `sensor.predbat_status` (or version attribute)
   - Current `select.work_mode`
   - Current `number.min_soc_on_grid` (expected: ≥ 11% in normal operation)
   - FC guardian status (`input_boolean.bateria_blokada_fc_przy_pv`)
   - Screenshot of current Predbat plan
3. Optionally backup `/addon_configs/<prefix>_predbat/` from host (log + generated apps files)

**Do not proceed without a successful backup.**

### 2. Timing Constraints

Deploy during:
- Daytime hours with operator present
- Outside G13 charge windows
- Allow 2–4 hours observation period post-deployment

## Deployment Procedure

### Path A: kamien5 Fork (Current/Recommended)

The kamien5 fork vendors Predbat and **disables self-update**. The `select.predbat_update` entity will **not** install new versions.

#### Steps:

1. Update repository: The new add-on image (e.g., `1.7.1-kamien5.3` with Predbat v9.6.5) is published to the repository
2. In Home Assistant: **Settings → Add-ons → Predbat (kamien5 fork)** → refresh repository
3. When Supervisor shows an update available for `update.predbat_kamien5_fork_update`:
   - Click **Update** (or manually install the new version)
4. After installation: **Restart** the Predbat add-on
5. Verify deployment (see Verification section below)
6. Observe for 2–4 hours

**Note:** Do NOT rely on `select.predbat_update` to upgrade the engine on current kamien5 versions (1.7.1-kamien5.1/2/3) — it will log that self-update is disabled and keep the existing vendor version.

## Post-Deployment Verification

After add-on restart, verify within 15–30 minutes:

1. **Version**: `sensor.predbat_status` shows the expected Predbat version (e.g., 9.6.5, not 9.5.0)
2. **Work Mode**: `select.work_mode` is in allowed set:
   - Self Use
   - Back-up (for Freeze operations per Variant A)
   - Force Charge (when scheduled)
   - Guardian prevents Force Discharge / Feed-in First
3. **Min SoC**: `number.min_soc_on_grid` ≈ **11%** (not 100% "stuck" after Freeze without reason)
4. **Freeze behavior** (Variant A):
   - During planned Freeze: work_mode **Back-up** as configured
   - After Freeze window: returns to Self Use and allows discharge
5. **Force Charge + PV guardian**:
   - When PV > 0.5 kW and cost ≥ 0: guardian switches to **Self Use** (not leaving Force Charge during solar)
   - Guardian allows FC with PV only when cost is **negative** (intentional)
6. **No forced export**: Predbat must not set discharge/export modes (services discharge_* = Self Use)
7. **Log health**:
   - No MANIFEST hash mismatch errors (kamien5)
   - No OAuth/rate-limit loops (we use HA sensors, not cloud API)
   - At kamien5, if someone touches `select.predbat_update`, log shows "Predbat self-update is disabled" and no actual download
8. **Plan generation**: Fresh plan generated (v9.5.1+: old version plans are replaced on first cycle after upgrade)

### Observation Period (2–4 hours)

Monitor:

1. `work_mode` transitions follow plan + guardian rules
2. During PV oscillation ~0.4–0.7 kW: no rapid FC/Self Use loop; 0.5 kW threshold working
3. `min_soc_on_grid` and actual SoC: floor stays ~11%; post-Freeze hold releases when plan dictates
4. Import from grid during expensive G13/Pstryk vs plan: no "holes" in control (~clock skew / stalled scheduler; unlikely on HA add-on but verify ~30 min cycles)
5. Predbat log: no flood of Fox warnings; no spurious download attempts (with disabled stub)
6. Guardian notifications / emergency mode `input_boolean`: should not trigger without real anomaly
7. Marginal/cheap-moderate sensor labels: changed labels OK; alert only if HA automations depend on "cheap" label and suddenly go silent

## Rollback Procedure

### When to Rollback

Escalate to rollback if:
- `work_mode` persistently outside allowlist (e.g., stuck in Force Discharge)
- SoC drops < 11% while on-grid without plan justification
- Force Charge persists during PV > 0.5 kW with cost ≥ 0
- No new plan generated for > 1 planning cycle
- Critical automation failures tied to changed sensor behavior

### Rollback Steps

#### Method 1: Restore Previous Add-on Version

1. **Settings → Add-ons → Predbat (kamien5 fork)** → version dropdown
2. Select previous version (e.g., `1.7.1-kamien5.2` if rolling back from .3)
3. Restart the add-on
4. Verify `sensor.predbat_status` returns to previous Predbat version
5. Verify operation per post-deployment checklist

#### Method 2: Restore Full Backup

1. **Settings → System → Backups**
2. Select backup created in pre-deployment step
3. Restore full backup
4. After system restart, verify `sensor.predbat_status` and operation

## Emergency Fail-safe (Non-Predbat Issues)

If issues arise outside Predbat control (inverter, network, etc.):

1. Stop Predbat add-on
2. Manually set:
   - `select.work_mode` → **Self Use**
   - `number.min_soc_on_grid` → **11%**
3. Observe system behavior
4. When stable, investigate root cause before restarting Predbat

## Configuration Constraints (kamien5 fork)

### MUST NOT Change

- `hassio_api: false` (security constraint)
- Launch.py self-update stubs (self-update disabled)
- `apps.yaml` APPS_YAML_SHA256 pin (currently `bfb291ea64dfd221d7dd46d7f76538035652bf9801ebff2b16d93c9af21e4d6e`)
  - apps.yaml is regenerated on every start from image template
  - User must not manually edit `/addon_configs/.../apps.yaml` (overwritten)
- Dockerfile base image digests (must match kamien5-v2 TARGETARCH pattern)

### Policy Settings

- **Minimum SoC on grid**: 11% (policy, enforced by guardian fail-safe)
- **Self-update**: Disabled (vendored Predbat version pinned in add-on image)
- **Force Charge guardian**: At PV > 0.5 kW and cost ≥ 0, switches to Self Use
- **Export blocking**: All discharge services set to Self Use (no forced export from battery)

## Tag Management

- Production tag (e.g., `kamien5-v2`) remains on last stable release until new version is validated
- Do NOT delete or move production tags (e.g., `kamien5-v2` stays; `kamien5-v3` created later by human on merge commit after validation)
- Development versions (e.g., `1.7.1-kamien5.3`) are released for testing but tag movement occurs only after human approval

## Security Notes

- Requirements installed with `--require-hashes --only-binary=:all:`
- Build fails on MANIFEST.sha256 mismatch (integrity enforcement)
- Supervisor token kept out of logs and CLI arguments
- Web UI restricted to Home Assistant ingress
- Admin endpoints restricted
- Reduced permissions: no `hassio_api`, `addon_config` only

## References

- Current version tracking: `predbat/config.yaml` → `version:`
- Vendor source: `predbat/VENDOR.txt`
- Vendor script: `tools/vendor_predbat.sh`
- Vendor integrity: `predbat/MANIFEST.sha256`
- Changes: `CHANGELOG.md`
