# Predbat v9.7.0 Deployment and Upgrade

**Branch**: `cursor/vendor-predbat-v9.7.0-2ba3`  
**PR**: [#5](https://github.com/kamien5/predbat_addon/pull/5)  
**Status**: BLOCKED - awaiting reviews and source pin solution  
**CI**: Unit tests 45/45 pass, amd64 build green, aarch64 pending

---

## Critical Blockers

###  1. **NO PROVEN SOURCE PIN** ⛔

Home Assistant Supervisor local build (`build: true`) does **NOT** pin source SHA before build.

- **Tag alone is insufficient** — Supervisor may fetch from branch/main
- **No documented prebuild checkout verification** for installed version
- **Cannot prove** built image corresponds to reviewed tree
- **STOP deployment until**:
  - Confirmed Supervisor prebuild checkout mechanism documented OR
  - Alternative proven source-pin method implemented OR
  - Image published to registry with immutable digest

**DO NOT** proceed with "deploy immediately from main" or tag dropdown without proven source pin.

### 2. **Backup Required BEFORE Any Mutation** 

 - **Current backup** (5 Nov 19:29): Metadata present, content/restore **NOT verified**
- **Fresh unencrypted full backup** required before first mutation
- **Test restore** to confirm backup integrity
- **User policy**: NO encryption, NO encryption key (standing decision 31 Oct)

### 3. **One-Shot Approval Hashes Consumed**

- **W32** (store reload): **CONSUMED**
- **W33** (addon update): **CONSUMED**
- **Identical payloads CANNOT be reactivated** (flock + fsync ledger)
- **NEW approval hashes required** for any deployment attempt
- Fresh scoped approvals must be reviewed and authorized separately

### 4. **Security and QA Review Required**

- **Both reviews** must approve **SAME final SHA**
- **Green CI** on both amd64 and aarch64 required
- **No active contradictions** in documentation
- **Current status**: Documentation audit in progress

### 5. **External HA Configuration** (Separate Scope)

- **5kW cap removal**: HA v2 patch under development (separate from this PR)
- **NOT verified** from addon repository alone
- **Live config hash/CAS precondition** required before HA writes
- **Atomic rollback mechanism** must be designed and tested

---

## Upgrade Procedure (After Blockers Resolved)

### Phase 1: Pre-Deployment Verification

1. **Resolve source pin blocker**
   - Document Supervisor checkout mechanism OR
   - Publish image to registry with immutable digest OR
   - Implement alternative proven source tracking

2. **Fresh backup**
   ```
   Backup type: Full (addon + HA config)
   Protected: false (NO encryption)
   Verify: Download and inspect archive
   ```

3. **New approval hashes**
   - Generate fresh W-labels for store reload and addon update
   - Review exact payloads
   - Coordinate Security/QA approval

4. **Final SHA verification**
   - Both Security and QA approve SAME commit SHA
   - CI green (45/45 tests, both arches)
   - Documentation consolidated and contradiction-free

### Phase 2: Deployment

**Order** (T = trigger time):

```
T+0:   BACKUP FIRST (fresh unencrypted full backup)
T+5:   Verify backup integrity (download, inspect)
T+10:  Execute store reload (new W-label)
T+15:  Execute addon update (new W-label, build: true, timeout 1800)
T+20:  Wait for build completion
T+25:  Verify addon version sensor
T+30:  Check Predbat startup (sensor.predbat_status)
T+35:  Collect evidence (version, logs, image ID if accessible)
T+40:  Begin 2-4h observation window
```

**Critical**: If any step fails, restore from backup immediately.

### Phase 3: Post-Deployment Verification

1. **Version confirmation**
   - Addon UI shows correct version
   - `sensor.predbat_status` shows engine v9.7.0
   - VENDOR.txt contains upstream commit `4cbf6333...`

2. **Behavior validation**
   - Min SoC stays >= 11%
   - Self-update OFF (confirmed disabled)
   - Guardian/fail-safe behavior preserved
   - Force Charge respects Charging window exception

3. **Observation window**
   - 2-4 hours minimum
   - Monitor for unexpected mode changes
   - Check SoC does not drop below 11%
   - Verify no unintended export

---

## Rollback Procedure

### Immediate Rollback (Within 1 Hour)

If critical failure detected:

1. **STOP Predbat** (via button.predbat_stop or UI)
2. **Restore from backup** (fresh backup taken T+0)
3. **Verify restoration**:
   - Addon version matches pre-upgrade
   - Engine version confirms rollback
   - Guardian configuration intact
4. **Document failure** (logs, symptoms, timeline)

### Delayed Rollback (After Observation)

If issues found during observation window:

1. **Capture evidence** (logs, sensor states, timeline)
2. **Fresh backup of current state** (for forensics)
3. **Restore original backup** (pre-upgrade)
4. **Root cause analysis** before retry

---

## Current Limitations and Constraints

### Proven Behaviors (From Repository)

✅ **Min SoC**: Config shows 11% floor  
✅ **Self-update**: Disabled in config  
✅ **Vendor files**: 115 files verified against upstream  
✅ **CI tests**: 45/45 pass locally, both arches build  
✅ **Force Charge PV exception**: Charging window logic present

### Unverified (External HA Configuration)

⚠️ **5kW cap**: HA automation not visible from addon repo  
⚠️ **14kW/23A limits**: Guardian config external to addon  
⚠️ **11% SoC enforcement**: HA-side guardian unverified from repo  
⚠️ **No forced export**: Cannot prove from addon config alone  
⚠️ **Hardware ceiling**: BMS behavior not repository-testable

**Note**: HA configuration verification requires separate read-only helper access (Stage 1 patch under development).

---

## Open Questions

1. **Supervisor build source resolution**
   - How does Supervisor determine git ref for `build: true`?
   - Is checkout SHA logged/accessible post-build?
   - Can we verify built tree matches reviewed tree?

2. **Image publication alternative**
   - Should we publish to registry instead of local build?
   - What is approval process for image publication?
   - Digest-based pull eliminates ambiguity

3. **One-shot approval refresh**
   - Fresh W-labels required for deployment
   - Review/approval workflow for new hashes?
   - Ledger cannot be reset (consumed state permanent)

---

## References

- **Upstream**: [batpred v9.7.0](https://github.com/springfall2008/batpred/releases/tag/v9.7.0) (commit `4cbf6333`)
- **Vendor PR**: [kamien5/predbat_addon#5](https://github.com/kamien5/predbat_addon/pull/5)
- **Previous tag**: `kamien5-v3` (v9.6.5 addon 1.7.1-kamien5.3)
- **Proposed tag**: `kamien5-v4` (after blockers resolved)

---

## Document Status

**Created**: 2026-11-07  
**Replaces**: DEPLOYMENT-PROVENANCE.md, DEPLOY.md, UPGRADE-v9.7.0.md  
**Supersedes**: DEPLOYMENT-BLOCKERS.md (blockers consolidated above)  
**Status**: ACTIVE — single source of truth for deployment procedure

**DO NOT** create additional deployment docs. Update this file only.
