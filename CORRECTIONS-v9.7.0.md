# Corrections and Clarifications — v9.7.0 Upgrade

**Document status**: ACTIVE corrections record  
**Created**: 2026-11-07  
**Deployment procedure**: See [DEPLOY-UPGRADE.md](./DEPLOY-UPGRADE.md)

---

## Policy vs. Implementation

### ✅ Corrected Understanding

**5kW Charge Cap**:
- **User policy**: Obsolete 5kW cap REMOVED; charge at inverter/BMS max subject to 14kW house and 23A phase limits
- **Addon repository**: Contains Predbat engine only; **does NOT** implement house/phase limits
- **External HA config**: Guardian automations enforce limits (external to this repository)
- **Status**: HA 5kW cap removal patch under separate development (not part of this PR)

**Hardware Limits** (5.1kW charge, 5.3kW max observed):
- **Source**: Live telemetry measurements, **NOT** addon configuration
- **Distinction**: Measured vs. configured vs. software-capped
- **Addon scope**: Predbat engine does not enforce these limits directly
- **Guardian scope**: HA-side enforcement (external config, unverifiable from repo alone)

### ✅ FC PV Threshold Exception

**Complete rule**:
- **Outside** Predbat charge windows: FC blocked when PV > 0.5kW (unless cost < 0)
- **Inside** Predbat `Charging*` windows: FC stays regardless of PV
- **Implementation**: Verified in automation `bateria_fc_przy_pv` condition check

**All documentation** updated to include "outside charge window" qualifier.

---

## Repository vs. External Configuration

### In This Repository (Verifiable)

✅ **Predbat engine**: v9.7.0 from upstream commit `4cbf6333...`  
✅ **Vendor file integrity**: 115 files checksummed and verified  
✅ **Self-update**: Disabled in `apps.yaml`  
✅ **Min SoC config**: Shows 11% in config (engine enforcement)  
✅ **FC Charging exception**: Logic present in code

### External HA (NOT Verifiable From Repo)

⚠️ **Guardian automations**: 14kW house budget, 23A phase limits  
⚠️ **Min SoC enforcement**: HA-side 11% floor guardian  
⚠️ **5kW cap removal**: Requires separate HA config patch  
⚠️ **No forced export**: HA configuration, not addon config  
⚠️ **Hardware BMS ceiling**: Runtime telemetry, not config

**Verification of external HA config** requires separate read-only helper access (Stage 1 patch under development, not part of this deployment).

---

## Build and Deployment Method

### ✅ Actual Method

**Supervisor local build**:
- `build: true` in repository configuration
- Supervisor clones and builds locally on deployment
- **No published image** to registry
- **No manual docker build/push** by coordinator

### ⚠️ Source Pin Issue (Blocker)

**Problem**: Supervisor build source resolution **undocumented**
- Tag alone may not pin checkout SHA
- No proven prebuild verification mechanism
- Cannot confirm built image = reviewed tree

**Status**: **BLOCKS DEPLOYMENT** until resolved  
See [DEPLOY-UPGRADE.md](./DEPLOY-UPGRADE.md) Critical Blockers section.

---

## One-Shot Approval Hashes

### ✅ Current State

**W32 (store reload)**: **CONSUMED** — cannot be reused  
**W33 (addon update)**: **CONSUMED** — cannot be reused

**Ledger mechanism**:
- `flock(LOCK_EX)` + check + write + `fsync` before send
- Consumed state **permanent** (ledger cannot be reset)
- Identical payload hash **cannot be reactivated**

### ✅ Deployment Requirement

**Fresh approval hashes required** for any deployment attempt:
- New W-labels must be generated
- Exact payloads reviewed and approved separately
- Security/QA must approve new hashes before use

**NO deployment possible** with existing W32/W33 (already consumed).

---

## CI and Architecture

### ✅ Build Configuration

**Method**: `build: true` (Supervisor local build)  
**CI**: `cache-only` (no publication to registry)  
**config.yaml**: No `image:` field (local build)

**CI status**:
- Unit tests: 45/45 pass (no aiohttp locally, all pass in CI)
- amd64 build: ✅ Green
- aarch64 build: ✅ Green (both arches required)

### ✅ Deployment Mechanics

**Real deployment path**:
1. Supervisor receives addon update command (new W-label required)
2. Supervisor clones repository at selected ref
3. Supervisor builds image locally (`build: true`)
4. Supervisor installs built image
5. **Source verification**: Currently **unproven** (blocker)

**NOT**: Pre-built image, NOT manual docker push, NOT registry pull

---

## MCP and Security

### ✅ Corrected MCP Protection

**Actual implementation**:
- MCP **default OFF** (no config file shipped)
- Fail-closed startup check on `mcp_enable`
- Source-IP middleware enforcement
- **NOT an unconditional path blacklist**

**Previous misstatement**: Documentation incorrectly described unconditional path blacklist. Corrected to reflect actual source-IP + default-off design.

---

## Testing Scope

### ✅ What Was Tested

**Unit tests** (45 total):
- Predbat engine logic
- Config parsing
- Entity state handling
- Plan generation algorithms

**Integration tests** (mocked):
- HA service call patterns
- Entity write sequences
- Fail-safe trigger paths

**Architecture** (CI verified):
- amd64 build succeeds
- aarch64 build succeeds

### ⚠️ What Was NOT Tested

**Not verifiable from repo/CI**:
- Live HA guardian behavior (external config)
- Actual BMS response to commands
- Physical inverter write safety
- House phase load measurement
- Min SoC drop protection (runtime)
- EV charging coordination (live system)

**Mocked tests** do NOT prove container execution safety or live system behavior.

---

## FC PV Charging Window Exception

### ✅ Complete Implementation

**Code location**: `automation.bateria_fc_przy_pv`

**Logic**:
1. Trigger: FC mode **OR** PV > 0.5kW for 1 min
2. Condition: `bateria_blokada_fc_przy_pv` ON **AND** `work_mode = Force Charge`
3. **Exception check**: `NOT (status == 'Charging' OR status.startswith('Charging'))`
4. Action: Set work_mode to Self Use (only if exception check passes)

**Result**:
- Outside charge window (`status != Charging*`): FC blocked when PV > 0.5kW
- Inside charge window (`status == Charging*`): FC stays despite PV

**All documentation** updated with complete rule including exception.

---

## Document Consolidation

**Previous state**: 4 separate deployment/procedure documents with contradictions

**Current state**: Single source of truth in [DEPLOY-UPGRADE.md](./DEPLOY-UPGRADE.md)

**Obsoleted documents** (marked with explicit notice):
- DEPLOYMENT-PROVENANCE.md
- DEPLOY.md
- UPGRADE-v9.7.0.md
- DEPLOYMENT-BLOCKERS.md

**Remaining active docs**:
- **DEPLOY-UPGRADE.md**: Single deployment procedure (blockers, steps, rollback)
- **CORRECTIONS-v9.7.0.md**: This file (clarifications and corrections)
- **SECURITY-REVIEW-v9.7.0.md**: Security assessment
- **TASK-5KW-CAP-REMOVAL.md**: Separate HA config task (not part of addon deployment)

---

## External HA Configuration (Separate Task)

**5kW cap removal** is **NOT part of this PR**:
- Requires HA automation/guardian configuration changes
- Separate patch under development (HA v2)
- Separate approval/testing/deployment process
- **NOT included** in addon v9.7.0 upgrade

**Status**: Stage 1 read-only helper patch + HA v2 automation patch in development as separate artifacts. See [TASK-5KW-CAP-REMOVAL.md](./TASK-5KW-CAP-REMOVAL.md).

---

## Summary of Corrections

1. ✅ **5kW cap**: Policy vs. addon vs. HA config distinction clarified
2. ✅ **FC PV exception**: Complete rule with charge window qualifier
3. ✅ **Build method**: Supervisor local build (not manual/published image)
4. ✅ **Source pin**: Identified as unresolved blocker
5. ✅ **W32/W33 consumed**: Fresh hashes required for deployment
6. ✅ **MCP protection**: Corrected to source-IP + default-off (not unconditional blacklist)
7. ✅ **External HA config**: Clearly marked as unverifiable from repo
8. ✅ **Documentation consolidated**: Single procedure in DEPLOY-UPGRADE.md

**All active documentation** reviewed for consistency. No contradictions remain.

---

**Last updated**: 2026-11-07  
**Next review**: After Security/QA final approval
