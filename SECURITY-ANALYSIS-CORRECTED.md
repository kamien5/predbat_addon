# Security Analysis: Predbat v9.7.0 Upgrade (CORRECTED)

**Date:** 2026-11-07  
**PR:** #5 https://github.com/kamien5/predbat_addon/pull/5  
**HEAD SHA:** `f24590e81c3424c53a5d3e82a5c35ad938751d0b` (full 40 chars)  
**Status:** HOLD — corrections based on preliminary security review feedback

---

## CRITICAL CORRECTIONS FROM REVIEWER FEEDBACK

### 1. MCP Protection Mechanism — VERIFIED FROM CODE

**Reviewer finding:** No unconditional MCP path blacklist found

**CODE VERIFICATION** (`predbat/rootfs/opt/predbat/launch.py`):

#### Protection layer 1: Default OFF
```yaml
# predbat/rootfs/apps.yaml — NO mcp_enable config present
# Predbat defaults mcp_enable to False when absent
```

#### Protection layer 2: Fail-closed on mcp_enable
```python
# launch.py lines 85, 338-340
FORBIDDEN_ENABLED_OPTIONS = ("mcp_enable",)

def refuse_unsupported_options(apps_yaml_path: str):
    # Exits 1 if mcp_enable is enabled
    for option in FORBIDDEN_ENABLED_OPTIONS:
        if option in root and (root[option] is secret_ref or not _option_is_off(root[option])):
            _refuse(option)  # sys.exit(1)
```

**Verification:** If `mcp_enable: true` added to apps.yaml → startup.py calls launch.py → exit 1 before Predbat starts

#### Protection layer 3: Source-IP middleware (ingress trust boundary)
```python
# launch.py lines 34-35, 250-252
ALLOWED_REMOTES = {"172.30.32.2", "127.0.0.1", "::1"}  # HA ingress + loopback

# Middleware injected into web.Application:
middlewares.insert(0, ingress_only)  # Returns 403 for other IPs
```

**Applied to:** Main web server AND `web_mcp` module (line 82, 259-269)

#### ⚠️ NO PATH-BASED MCP BLACKLIST

```python
# launch.py lines 38-52
BLOCKED_PATHS = {
    "/apps_editor",
    "/debug_apps",
    "/component_config_save",
    "/download",
    "/browse",
    "/api/kraken_key",
    # ... other admin paths
}
# ❌ NO MCP paths (/oauth/*, /mcp/*, /tools/*) in BLOCKED_PATHS
```

**Implication:** If mcp_enable was somehow bypassed, MCP paths would be accessible to ingress IPs (172.30.32.2). Defense relies on startup-time check, not runtime path blocking.

**Conclusion:** MCP protection is **fail-closed at startup** + **IP restriction**, NOT path blacklist.

---

### 2. Trust Boundaries — CORRECTED

#### Trust boundary: Ingress/IP, NOT entity/service allowlist

**Incorrect claim (previous docs):** "discharge services → Self Use proves no forced export"

**CORRECTED:** 
- `discharge_*_service` config in apps.yaml sets **Predbat's service calls**
- Trust boundary: Ingress middleware (launch.py) restricts **web UI access**
- Entity/service allowlist: Separate HA authorization for **Predbat's calls to HA**
- Setting discharge → Self Use configures Predbat's behavior, does NOT prove HA blocks all export paths

**Repo-verifiable:**
```yaml
# predbat/rootfs/apps.yaml lines 35-47
discharge_start_service:
  service: select.select_option
  option: "Self Use"
# (all discharge services → Self Use)
```

**NOT verifiable from repo:**
- HA service call authorization (hass_ws allowlist)
- Whether HA actually blocks Force Discharge mode writes
- Other paths to inverter export mode (external automations, HA UI, direct writes)

---

### 3. Charge Limits — Policy vs Repository Mapping

#### What repo contains:
```yaml
# predbat/rootfs/apps.yaml lines 62-65
inverter_limit: [10000]                      # 10 kW inverter spec
battery_rate_max: [5300]                     # MEASURED: ~26 A × nominal voltage
inverter_limit_charge: [5100]                # MEASURED operational limit
inverter_limit_discharge: [5300]             # MEASURED operational limit
# Comment: "korekta po pomiarze Force Charge" — correction after measurement
```

#### What repo does NOT contain:
- How measurements were taken
- When measurements were taken
- Environmental conditions during measurement
- Whether values represent continuous or peak limits
- Relationship to user policy "obsolete 5kW cap removed"

#### CORRECTED interpretation:
- Values 5100/5300 W exist in apps.yaml
- Source: comment says "po pomiarze" (after measurement)
- **Repo cannot prove these are hardware limits vs policy decisions**
- External HA guardian (not in repo) applies additional throttling (15kW grid, 25A phase)

**Coordinator live observation (07:52 CET):**
- Current addon 1.7.1-kamien5.3 uses these same values
- System operational with these limits
- Live helper hash `d2574818...` (expected unchanged post-upgrade)

---

### 4. FC+PV Guardian — Exception During Charge Windows

#### User policy requirement:
> "FC PV guard threshold 0.5kW and resume FC below it, but during Predbat charge windows FC stays regardless of PV"

#### Repo evidence:
```yaml
# predbat/rootfs/apps.yaml line 22-25
# [ZMIANA] Force Charge przez skrypt strażnika: przy PV > 0,5 kW i koszcie >= 0 skrypt wybiera Self Use
charge_start_service:
  service: script.turn_on
  entity_id: script.bateria_force_charge
```

#### What repo proves:
- apps.yaml references `script.bateria_force_charge` (external HA script)
- Comment describes PART of behavior: "przy PV > 0,5 kW i koszcie >= 0 → Self Use"

#### What repo does NOT prove:
- Complete guardian logic (script code not in repo)
- Exception during Predbat charge windows
- PV threshold exact value (0.5 kW mentioned in comment only)
- Cost threshold behavior

**Requires:** Separate versioned HA evidence (guardian script export, test logs showing exception)

---

### 5. Build and Deployment Path — ACTUAL PROCESS

#### CI workflow (`.github/workflows/ci.yml`):
```yaml
# Lines 93-109
- name: Build image (no publish)
  run: |
    docker buildx build \
      --platform "$PLATFORM" \
      --output type=cacheonly \  # ← NOT published
      predbat
```

**CI does:** Verify build succeeds for both arches, NO image push

#### config.yaml — NO image reference:
```yaml
# predbat/config.yaml
name: Predbat (kamien5 fork)
version: 1.7.1-kamien5.4
# ❌ NO "image:" field
# Supervisor builds locally from Dockerfile in repo
```

#### Actual deployment path (Supervisor local build):

**Method: HA Supervisor local build**
1. User adds GitHub repository URL to HA Supervisor (Add-on Store → Repositories)
2. Supervisor fetches repository at commit SHA
3. Supervisor runs local Docker build:
   ```bash
   docker build \
     --build-arg BUILD_FROM=<from build.yaml> \
     --build-arg BUILD_ARCH=<detected> \
     --build-arg BUILD_VERSION=<from config.yaml> \
     --file predbat/Dockerfile \
     predbat/
   ```
4. Image stored in local Supervisor registry (not pushed to remote)
5. Container created from local image

**Source SHA for deployment:**
- User installs from GitHub branch or tag
- Supervisor fetches exact commit SHA user selected
- `git rev-parse <branch|tag>` determines source
- **After merge:** main branch HEAD SHA (not current PR head)
- **Recommended:** Create tag `kamien5-v4` → Supervisor installs from tag SHA

**Image immutability:**
- NO remote image push (no digest)
- Each Supervisor builds locally
- Immutability: Git commit SHA + Dockerfile base image digests (build.yaml)

#### Deployment sequencing (CORRECTED):

1. **PR review and approval** (human)
2. **CI must pass** (both arches, all 45 tests, no skips)
3. **Merge to main** → new HEAD SHA on main
4. **Tag creation** (manual, post-merge):
   ```bash
   git checkout main && git pull
   git tag -a kamien5-v4 -m "Predbat v9.7.0 addon 1.7.1-kamien5.4"
   git push origin kamien5-v4
   TAG_SHA=$(git rev-parse kamien5-v4^{commit})
   echo "Tag kamien5-v4 points to $TAG_SHA"
   ```
5. **Backup fresh** (HA: Settings → Backups → Create)
6. **HA Supervisor deployment:**
   - Add-on Store → Predbat → Check for updates
   - OR: refresh repository → install specific tag
   - Supervisor builds from tag SHA locally
7. **Install** → Supervisor builds image (2-5 min per arch)
8. **Restart** add-on
9. **Verify** (30 min + 2-4h observation)

---

### 6. Vendor Integrity — Container Execution vs Mocked Tests

**Reviewer note:** "Vendor 115 files match upstream/no new hardening regression, but mocked tests don't prove container execution"

#### What tests verify:
```python
# tests/test_startup.py
def test_a_clean_start_installs_all_pinned_files(self):
    # Verifies MANIFEST.sha256 file count and checksums
    
def test_b_self_update_tamper_is_restored(self):
    # Verifies startup.py restores pinned vendor on tamper
    
# tests/test_web_hardening.py  
def test_restricted_paths_exist_in_vendor_routes(self):
    # Verifies BLOCKED_PATHS still exist in vendor/web.py routes
```

**What tests do NOT verify:**
- Container build succeeds
- Dockerfile COPY operations succeed
- Runtime module imports work
- startup.py actually runs in container
- Vendored files load correctly

**CI verification:**
```yaml
# .github/workflows/ci.yml
- docker-build job: both arches
  - Builds complete image (cacheonly, no push)
  - Build failure → CI fails
```

**CI proves:** Image builds without errors on both arches

**CI does NOT prove:**
- Container starts
- startup.py succeeds
- Predbat runs
- Web server responds

**Recommendation:** Post-deployment smoke test (verify sensor updates, UI accessible, plan generated)

---

### 7. hass_ws Mutation Authorizations — W32/W33 Context

**Reviewer note:** "W32/W33 already consumed, fresh one-shot authorizations required"

**Previous incorrect claim:** "Existing allowlists sufficient"

**CORRECTED:**
- W32/W33: Context windows or work periods (consumed)
- One-shot authorizations: HA hass_ws mutation calls need fresh approval per deployment
- Repo does NOT contain allowlist configuration
- Deployment may require new allowlist entries if:
  - Payload structure changed
  - New entities written
  - SHA-based allowlist needs update

**apps.yaml service calls (unchanged v9.6.5 → v9.7.0):**
```yaml
charge_start_service: script.turn_on              # entity_id: script.bateria_force_charge
charge_freeze_service: select.select_option       # entity_id: select.work_mode, option: "Back-up"
charge_stop_service: select.select_option         # option: "Self Use"
discharge_*_service: select.select_option         # option: "Self Use"
```

**Entities written (unchanged):**
- `input_number.predbat_charge_rate_request`
- `input_number.predbat_discharge_rate_request`

**v9.7.0 new vendor code:**
- `billing.py` — reads Kraken API, publishes `sensor.predbat_billing` (read-only sensor, no writes)

**Assessment:** Service calls and entities unchanged → likely NO new allowlist hashes

**Requirement:** Coordinator must verify allowlist status and approve fresh mutations

---

### 8. Backup Evidence — Required Before Deployment

**Reviewer note:** "Existing backup 5 Nov 19:29 success but content/restore not verified; fresh backup still needed"

**Live observation (coordinator-reported, 07:52 CET):**
- Existing backup: 5 Nov 2026 19:29 (2 days old)
- Status: "success" (per HA)
- Content/restore: NOT verified

**Required before deployment:**
1. **Fresh full backup** (include add-ons)
2. **Verify backup content:**
   - Backup file exists and is readable
   - Size reasonable (not empty/truncated)
   - Contains add-on config (expected size > X MB)
3. **Optional: Test restore** to separate HA instance if available
4. **Document backup:**
   - Filename
   - Timestamp
   - Size
   - SHA256 checksum

**Deployment MUST NOT proceed without verified fresh backup**

---

### 9. Live System Observations (Coordinator-Reported)

**Source:** Coordinator pre-flight read, 07:52 CET on 2026-11-07

**Current state (addon 1.7.1-kamien5.3, engine 9.6.5):**
```
sensor.predbat_status: 9.6.5
select.work_mode: Self Use (Demand mode healthy)
sensor.battery_soc: 12%
number.min_soc_on_grid: 11%
binary_sensor.predbat_charging: false
binary_sensor.predbat_exporting: false
Next planned charge: 09:00-10:00 CET, target 11%
```

**Expected helper hash:** `d2574818...` (unchanged post-upgrade)

**Live guardian behavior:** Operating correctly (pre-upgrade baseline)

**These are coordinator observations, NOT repo-derived proof.**

---

## Security Assessment — CORRECTED

### ✅ VERIFIED FROM REPO (vendor integrity)

| Check | Method | Status |
|-------|--------|--------|
| Vendor SHA256 | MANIFEST.sha256 vs v9.7.0 tag | ✅ 115 files match |
| Self-update stubs | launch.py code review | ✅ Present, tests pass |
| mcp_enable check | launch.py lines 85, 338-340 | ✅ Fail-closed at startup |
| Ingress middleware | launch.py lines 250-270 | ✅ IP restriction enforced |
| apps.yaml SHA256 | startup.py check | ✅ Unchanged (bfb291ea...) |
| Token handling | startup.py code review | ✅ Never logged |
| CI build | .github/workflows/ci.yml | ✅ Both arches, cacheonly |

### ⚠️ PROTECTION MECHANISMS (nuanced)

| Mechanism | Implementation | Limitation |
|-----------|----------------|------------|
| MCP blocking | Startup-time fail-closed | ❌ No runtime path blacklist |
| IP restriction | Ingress middleware | ✅ But trusts ingress IP |
| Discharge config | apps.yaml → Self Use | ❌ Doesn't prove HA blocks writes |
| Charge limits | apps.yaml values 5100/5300 | ❌ Source/nature unclear from repo |
| FC+PV guardian | External script reference | ❌ Logic not in repo |

### ❌ REQUIRES EXTERNAL VERIFICATION

| Item | Verification Method | Status |
|------|---------------------|--------|
| Guardian scripts | HA config export | ⏳ Pending |
| Min SoC enforcement | Live monitoring logs | ⏳ Pending |
| FC+PV charge window exception | Test during deployment | ⏳ Pending |
| Grid/phase limits | Live charge rate logs | ⏳ Pending |
| hass_ws allowlist | Mutation approval review | ⏳ Pending |
| Fresh backup | HA backup + verification | ⏳ **REQUIRED** |

---

## Deployment Requirements (CORRECTED)

### Pre-deployment (MANDATORY, no checkboxes):

1. **Fresh backup**
   - Create: Settings → System → Backups → Create backup (include add-ons)
   - Verify: Download, check size, document checksum
   - **Evidence required:** Backup filename, size, timestamp

2. **hass_ws mutation authorization**
   - Review: Service calls unchanged (script.turn_on, select.select_option)
   - Coordinator approval: Fresh one-shot authorization if SHA-based
   - **Evidence required:** Allowlist diff or confirmation unchanged

3. **External HA guardian evidence**
   - Export: `script.bateria_force_charge` code
   - Document: FC+PV behavior (including charge window exception)
   - Version: Match to current HA config
   - **Evidence required:** Script YAML + version identifier

4. **Timing**
   - Schedule: Outside charge windows (current: 09:00-10:00 CET next)
   - Operator: Present for 2-4h observation
   - Window: Sufficient for rollback if needed

### Deployment verification (30 min):

**Repo-verifiable:**
1. `sensor.predbat_status` = `9.7.0` (not 9.6.5)
2. Log: no "MANIFEST mismatch", no "self-update attempted"
3. Log: "mcp_enable is not supported" if someone tries to enable
4. Work mode: Self Use / Back-up / Force Charge (allowlist)
5. New plan generated

**External verification:**
6. Helper hash: `d2574818...` unchanged (coordinator expected)
7. Min SoC value: matches policy (coordinator-reported: 11%)
8. `sensor.predbat_billing`: does not exist (billing.py inactive)

### Observation (2-4h):

**Behavioral tests (EXTERNAL, not repo-provable):**
1. FC+PV guardian:
   - Wait for PV > 0.5 kW OUTSIDE charge window → work_mode Self Use
   - During next charge window: work_mode Force Charge regardless of PV
2. Work mode transitions: follow Predbat plan
3. SoC behavior: respects policy floor
4. Import during cheap hours: per plan
5. No log flood (Fox warnings, download attempts)

### Rollback conditions:

**Immediate:**
- work_mode outside allowlist (Force Discharge, Feed-in First)
- Log: MANIFEST mismatch or self-update attempted
- Add-on crash/restart loop

**After observation:**
- FC+PV guardian exception violated (FC exits during charge window)
- SoC drops below policy floor on-grid without cause
- No new plan generated > 1 planning cycle
- External guardian malfunction

### Rollback procedure:

1. Settings → System → Backups → [fresh backup name]
2. Restore → Select: Predbat add-on only (partial restore)
3. Wait for restore completion
4. Verify: `sensor.predbat_status` = `9.6.5`
5. Monitor: 30 min recovery verification

---

## Test Coverage — 5 Skipped

**Local environment:** 40 passed, 5 skipped (aiohttp not installed)
**CI environment:** All 45 MUST pass (workflow fails on any skip)

**Skipped tests** (integration, require aiohttp server):
1. `test_admin_endpoints_forbidden` — HTTP 403 for blocked paths
2. `test_blocked_paths_forbidden_from_ingress` — ingress source filtering
3. `test_extra_listener_modules_get_access_policy` — listener restrictions
4. `test_restrict_remote_allowlist` — IP allowlist enforcement
5. `test_missing_optional_listener_module_is_logged` — log message check

**Critical test PASSED:**
- `test_restricted_paths_exist_in_vendor_routes` — verifies BLOCKED_PATHS still exist in vendor/web.py after update (catches upstream renames)

**CI enforcement:** `.github/workflows/ci.yml` lines 57-60 fail build if any test skips

---

## Upstream Changes — Risk Assessment

### v9.6.5 → v9.7.0 (25 commits)

**Security-relevant:**
1. MCP OAuth fix (#5847, #5992) — ❌ NOT APPLICABLE (MCP disabled + fail-closed)
2. billing.py added — ❌ INACTIVE (no Octopus/Kraken config)

**Functional:**
3. execute.py Control SOC — ❌ NOT APPLICABLE (Sunsynk/SolaX only)
4. sunsynk.py BMS battery size — ❌ NOT APPLICABLE (not FoxESS)
5. gecloud.py optimizations — ❌ NOT APPLICABLE (not used)
6. plan.py export gate (#5977) — ✅ RELEVANT (general improvement)
7. solcast.py P10/P90 (#5974) — ⚠️ MINIMAL (using Forecast.Solar)

**All upstream changes:** Either not applicable OR general improvements. No regressions expected.

---

## CONCLUSION — HOLD STATUS

**Recommendation:** HOLD pending:

1. ✅ **Fresh backup** with verification evidence
2. ✅ **hass_ws authorization** review and approval
3. ✅ **External HA guardian evidence** (script export, version)
4. ✅ **CI green** for both arches (all 45 tests pass, no skips)
5. ✅ **Coordinator approval** of corrected security analysis
6. ✅ **Deployment timing** coordination (outside charge windows)

**Do NOT:**
- ❌ Merge without above evidence
- ❌ Tag until merge complete and CI green on main
- ❌ Deploy without fresh backup
- ❌ Assume existing allowlists sufficient without verification

**Current PR HEAD:** `f24590e81c3424c53a5d3e82a5c35ad938751d0b`  
**Expected next:** Corrections commit, then HOLD for evidence gathering

---

**Prepared by:** Cursor Agent  
**Date:** 2026-11-07  
**Status:** HOLD — awaiting evidence and coordinator approval
