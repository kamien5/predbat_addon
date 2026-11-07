# Deployment Blockers and Evidence Requirements

**PR:** #5 https://github.com/kamien5/predbat_addon/pull/5  
**Reviewed Code:** HEAD will be updated after this correction commit  
**Status:** HOLD — Critical blockers identified

---

## CRITICAL FINDINGS from Live Evidence (2026-11-07 08:05 CET)

### Finding 1: 5kW Cap EXISTS in External HA (Out of Scope)

**Evidence:**
```
# Guardian trace automation.bateria_straznik_przepisanie
Power = min(request, dynamic_limit, phase_headroom, 5.0)

# Live state 2026-11-07 08:05:02 CET
force_charge_power: 5.0 kW
dynamic_grid_charge_limit: 5.46 kW (calculated from phase currents)
```

**Analysis:**
- User requirements: "obsolete 5kW cap removed; charge at inverter/BMS allowed maximum"
- Repo apps.yaml: `inverter_limit_charge: [5100]` (measured value)
- **External HA guardian ADDS 5kW cap**: `min(..., 5.0)` hardcoded

**Implication:**
- Vendor upgrade v9.6.5 → v9.7.0 does NOT change this (guardian external)
- 5kW cap removal requires SEPARATE HA automation change (outside vendor upgrade scope)
- **Action:** Document deviation, scope separately, do NOT claim removed in this PR

### Finding 2: FC+PV Charge Window Exception CONFIRMED

**Evidence:**
```
# script.bateria_force_charge
pred_chg matches Charging or startswith Charging* → Force Charge (precedence over PV block)

# automation.bateria_fc_przy_pv  
Requires Predbat status NOT Charging* → PV block only when NOT charging
```

**Analysis:**
- Guardian explicitly checks `pred_chg` (predicted charging status)
- When Predbat plans charging (Charging*), PV block bypassed
- **DURING charge windows:** FC stays regardless of PV
- **OUTSIDE charge windows:** PV > 0.5kW + cost ≥ 0 → Self Use

**Status:** Policy correctly implemented, confirmed in traces

### Finding 3: Existing Backup Protected/Encrypted

**Evidence:**
```
GET /backups/0a866c47/info:
- created: 2026-11-05 19:29:06 CET
- partial: true
- protected: true (encrypted with password)
- size: 615884800 bytes
- addon fc83ef65_predbat: version 1.7.1-kamien5.3, size 0.0 (metadata only)
```

**User Standing Instruction (31 Oct):**
- Backups NOT encrypted
- NO encryption key
- Never ask for password

**Implication:**
- Existing backup payload contains `password: __SECRET__`
- Cannot reuse for fresh backup without revealing password
- **Required:** NEW unencrypted backup payload with separate approval

---

## HIGH Priority Blockers

### HIGH-1: Mutation Approval Mechanism (W32/W33 Consumed)

**Problem:**
- Previous deployments used work periods W32/W33
- Those periods already consumed
- Identical payload hashes cannot be reactivated
- History cannot be erased

**Current helpers:**
- Existing hass_ws.py expects SHA256 allowlist
- Helper hash: `d2574818e6613efde1ed36a4a1ac2c89b73c7f104cbb9b57a969efce7f5ac284`

**Required:**
1. **Fresh unencrypted backup payload:**
   ```json
   {
     "name": "pre-upgrade-kamien5-v4-[timestamp]",
     "addons": ["fc83ef65_predbat"],
     "folders": ["addons/local", "addons/git"]
   }
   ```
   NO `password` field (user requirement)

2. **NEW approval identity mechanism:**
   - Option A: Timestamped approval tokens (one-shot, time-bound)
   - Option B: Deployment-scoped approval IDs (links to specific upgrade)
   - Option C: Combined: `approval-kamien5-v4-[ISO8601]`
   
3. **Fail-closed implementation:**
   - Deployment script checks for approval
   - Rejects if approval missing/expired/mismatched
   - Logs rejection reason

**Blocked:** Cannot proceed with deployment until NEW approval mechanism designed and approved

### HIGH-2: Tree Equivalence After Merge

**Problem:**
- Reviewed HEAD: (will be new SHA after corrections)
- Merge creates new commit SHA
- Must prove merged tree = reviewed tree

**Verification Method:**
```bash
# After merge:
MERGE_SHA=$(git rev-parse main)
MERGE_TREE=$(git rev-parse main^{tree})
REVIEWED_TREE=$(git rev-parse <reviewed-sha>^{tree})

if [ "$MERGE_TREE" != "$REVIEWED_TREE" ]; then
  echo "TREE MISMATCH - REJECT MERGE"
  exit 1
fi
```

**Required:**
- Execute verification immediately after merge
- Document results in deployment evidence
- Tag only if trees match

---

## MEDIUM Priority Issues

### MED-1: Supervisor Build Source Verification

**Mechanism Determined:**
```yaml
# predbat/config.yaml
# NO "image:" field → Supervisor local build

# HA Supervisor behavior (documented + observed):
1. User adds repo: https://github.com/kamien5/predbat_addon
2. Supervisor fetches from default_branch: main (unless user selects version)
3. Builds: docker build -f predbat/Dockerfile predbat/
4. No remote image push/pull
```

**Source Selection:**
- **Default:** Latest commit on main branch
- **User choice:** Version dropdown → can select tags/branches/commits
- **NO automatic tag usage:** Tag creation alone insufficient

**Required Live Evidence:**
1. **Pre-deployment:** Screenshot version dropdown showing available refs
2. **Deployment:** Document which ref selected (tag kamien5-v4 vs main vs other)
3. **Post-deployment:** 
   ```bash
   docker inspect addon_fc83ef65_predbat | jq '.[0].Config.Labels."org.opencontainers.image.revision"'
   # OR
   docker inspect addon_fc83ef65_predbat | jq '.[0].Config.Labels."io.hass.version"'
   ```
4. **Verification:** Compare fetched SHA with approved merge commit

**Recommendation:**
- Deploy from tag kamien5-v4 (immutable, explicit choice)
- NOT from main (race condition: concurrent pushes possible)
- Document selected ref and verify match

### MED-2: Runtime Guard Effectiveness

**Cannot Verify from Repo:**
- Guardian scripts (external HA, provided via traces)
- Min SoC enforcement (external monitoring)
- Phase current monitoring (external automation)
- 5kW cap enforcement (external, confirmed present)

**Required:**
- Post-deployment monitoring (2-4h)
- Live logs collection
- Behavioral verification against traces

---

## Evidence Collection Requirements

### Pre-Merge
- [x] CI completion: unittest + amd64 build SUCCESS, aarch64 IN_PROGRESS
- [ ] CI final: all 45 tests pass, both arches build on corrected HEAD
- [ ] External approvals: backup plan, mutation mechanism, timing

### At Merge
- [ ] Merge commit SHA documented
- [ ] Tree equivalence verified (`git rev-parse main^{tree}` = reviewed tree)
- [ ] Tag kamien5-v4 created → merge commit
- [ ] Tag pushed to origin

### Pre-Deployment
- [ ] Fresh UNENCRYPTED backup payload approved
- [ ] NEW mutation approval mechanism approved
- [ ] Backup created and verified (download, size check, not encrypted)
- [ ] Version dropdown screenshot (showing kamien5-v4 available)

### At Deployment  
- [ ] Selected ref documented (kamien5-v4 recommended)
- [ ] Supervisor build log captured
- [ ] Time window confirmed (outside charge window 09:00-10:00 CET)

### Post-Deployment (30 min)
- [ ] sensor.predbat_status = 9.7.0 verified
- [ ] Container source SHA verified (docker inspect)
- [ ] VENDOR.txt commit = 4cbf6333 verified
- [ ] MANIFEST.sha256 115 files OK verified
- [ ] Work mode allowlist enforced (Self Use/Back-up/Force Charge only)
- [ ] Guardian still active (trace new execution)

### Observation (2-4h)
- [ ] FC+PV charge window exception working (next charge window test)
- [ ] SoC behavior per policy
- [ ] No log anomalies (MANIFEST mismatch, self-update attempts, etc.)

---

## Out of Scope (Separate Remediation)

### 5kW External Cap Removal
**Current:** Guardian hardcodes `min(..., 5.0)` in automation.bateria_straznik_przepisanie  
**Desired:** Remove 5.0 cap, use only `min(request, dynamic_limit, phase_headroom)`  
**Action:** Separate PR/change to HA automations (NOT vendor upgrade)  
**Evidence:** Guardian trace config SHA 3dba333910657ee82ad33826463b6c1885adb64c34fd6a935a984eec416a8850

### Branch Protection / Ruleset Changes
**Requested:** Protected branch, tag rulesets  
**Status:** Outside vendor upgrade scope, requires separate approval  
**Action:** Document recommendation, implement post-deployment if desired

---

## Coordination with Provenance Work

See DEPLOYMENT-PROVENANCE.md for:
- Full merge → tag → Supervisor fetch chain
- Tree equivalence verification script
- Race condition prevention
- Evidence archive structure

**Integration:** This document defines WHAT evidence is required.  
**Provenance doc:** Defines HOW to collect and verify that evidence.

---

## Current Status

**Code:** Corrections in progress (this commit)  
**CI:** Pending final run on corrected HEAD  
**External evidence:** Guardian traces received, analyzed  
**Blockers:** HIGH-1 (mutation approval) and backup payload not yet resolved  
**Next:** Coordinator designs NEW approval mechanism, backup payload reviewed

**Do NOT proceed with merge/tag/deployment until all blockers resolved.**

---

**Prepared by:** Cursor Agent  
**Date:** 2026-11-07  
**Supersedes:** FINAL-STATUS.md, SECURITY-ANALYSIS-CORRECTED.md (deleted)  
**Coordinates with:** DEPLOYMENT-PROVENANCE.md, SECURITY-REVIEW-v9.7.0.md
