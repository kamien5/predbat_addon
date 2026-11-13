# Corrections and Clarifications — v9.7.0 Upgrade

**Document status**: HISTORICAL clarifications for the v9.7.0 pass (2026-11-07).  
**Current deployment specification**: [DEPLOY-UPGRADE.md](./DEPLOY-UPGRADE.md) (Predbat **v9.7.10**, addon `1.7.1-kamien5.5`, public GHCR images, grants W40 / W41). Statements below in the present tense that mention `build: true`, “No published image”, 45 tests, or W32/W33 as the live grants are **superseded**.  
**Created**: 2026-11-07

---

## Policy vs. Implementation

### ✅ Corrected Understanding

**5kW Charge Cap**:
- **User policy**: Obsolete 5kW cap REMOVED; charge at inverter/BMS max subject to 14kW house and 23A phase limits
- **Addon repository**: Contains Predbat engine only; **does NOT** implement house/phase limits
- **External HA config**: Guardian automations enforce limits (external to this repository)
- **Status**: HA 5kW cap removal patch under separate development (not part of this PR)

**Observed Hardware Behavior**:
- Live measurements show ~5.1-5.5kW charging observed (hardware/BMS dependent)
- **NOT** proven from repository configuration or addon code
- Addon repository contains Predbat engine only
- Actual hardware limits enforced by inverter/BMS at runtime

### ✅ FC PV Threshold Exception

**Complete rule**:
- **Outside** Predbat charge windows: FC blocked when PV > 0.5kW (unless cost < 0)
- **Inside** Predbat `Charging*` windows: FC stays regardless of PV
- **Implementation**: Verified in automation `bateria_fc_przy_pv` condition check

**Complete rule** is the inside/outside pair above (Force Charge **stays** inside `Charging*`; high PV **blocks** it outside). Do not read this as “exception only outside windows”.

---

## Repository vs. External Configuration

### In This Repository (Verifiable)

✅ **Predbat engine (then)**: v9.7.0 from upstream commit `4cbf6333...` — **now v9.7.10 / 118 files**; see [DEPLOY-UPGRADE.md](./DEPLOY-UPGRADE.md)  
✅ **Vendor file integrity (then)**: 115 files checksummed and verified  
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

### Historical (v9.7.0 pass, 2026-11-07)

At that time the addon still used Supervisor local build (`build: true`, no `image:` field, no published registry image). Source pin before that local build was an open blocker.

### Current (supersedes the above)

See [DEPLOY-UPGRADE.md](./DEPLOY-UPGRADE.md):

- `config.yaml` has `image: ghcr.io/kamien5/predbat-addon/{arch}` and **no** `build: true`
- Images are published by `.github/workflows/publish.yml` to public GHCR after merge to `main`
- Piotr accepted this GHCR path on 2026-11-13 17:00 CET (`t429s1509`, B4)
- Label `org.opencontainers.image.revision` is the merge commit SHA on `main`

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

### Historical (v9.7.0 pass)

Then: Supervisor local `build: true`, no `image:` in `config.yaml`, unit tests 45/45 in CI (aiohttp-dependent tests skipped without a pinned venv). Deployment was a Supervisor clone + local build; source verification before that build was unproven.

### Current (supersedes the above)

- PR CI (`ci.yml`): unit tests with **zero skipped**, cache-only Docker builds for amd64 and aarch64
- Publish (`publish.yml`): GHCR push from `main` only, `expected_sha` gate, fail-closed tag probe
- `config.yaml`: `image: ghcr.io/kamien5/predbat-addon/{arch}`
- Test count is no longer 45 — see `tests/` and [DEPLOY-UPGRADE.md](./DEPLOY-UPGRADE.md)

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

**Unit tests** (45 total at the 2026-11-07 pass; current count is in `tests/` / CI on PR #5):
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

**Remaining docs**:
- **DEPLOY-UPGRADE.md**: Single current deployment procedure (authoritative)
- **CORRECTIONS-v9.7.0.md**: This file (historical clarifications for the v9.7.0 pass)
- **SECURITY-REVIEW-v9.7.0.md**: Historical MCP/security assessment; procedure is in DEPLOY-UPGRADE.md
- 5 kW cap removal is **out of this repository** (external HA package). The former `TASK-5KW-CAP-REMOVAL.md` was removed and is not a live spec.

---

## External HA Configuration (Separate Task)

**5kW cap removal** is **NOT part of this PR**:
- Requires HA automation/guardian configuration changes
- Separate patch under development (HA v2)
- Separate approval/testing/deployment process
- **NOT included** in addon v9.7.0 upgrade

**Status**: Stage 1 read-only helper patch + HA v2 automation patch remain **outside this repository**. There is no in-tree `TASK-5KW-CAP-REMOVAL.md`.

---

## Summary of Corrections

Historical (2026-11-07) items 1–8 still describe the v9.7.0 pass. They are **not** the live procedure:

1. **5kW cap**: Policy vs. addon vs. HA config distinction — still valid as a boundary
2. **FC PV exception**: **Inside** `Charging*` Force Charge stays on despite high PV; **outside** `Charging*` high PV blocks Force Charge (inverter → `Self Use`)
3. **Build method**: then Supervisor local build — **now** public GHCR image (see DEPLOY-UPGRADE.md)
4. **Source pin**: then an open blocker — **now** resolved by GHCR labels + merge-to-`main` before publish
5. **W32/W33 consumed**: still true; live grants are W40/W41 in DEPLOY-UPGRADE.md (`20d0c320…` is invalid)
6. **MCP protection**: source-IP + default-off (not an unconditional path blacklist)
7. **External HA config**: still unverifiable from this repo
8. **Documentation**: single live procedure in DEPLOY-UPGRADE.md; this file is historical

Do not treat this file as internally contradiction-free relative to the current tree. If anything here disagrees with [DEPLOY-UPGRADE.md](./DEPLOY-UPGRADE.md), DEPLOY-UPGRADE.md wins.

---

**Last updated**: 2026-11-13  
**Next review**: After Security/QA final approval of the current PR #5 head
