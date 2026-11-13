# Predbat v9.7.10 Deployment and Upgrade

**Branch**: `cursor/vendor-predbat-v9.7.0-2ba3`  
**PR**: [#5](https://github.com/kamien5/predbat_addon/pull/5)  
**Addon**: `1.7.1-kamien5.5`  
**Engine**: Predbat **v9.7.10** (`54a8cbb2b8bf66fd1005053cd89d6c80725c2801`)  
**Status**: Ready for parallel Security + QA review of the **same PR #5 head SHA**. Do not merge until both approve. No live HA/Mac mutation from this document.

This file is the **single source of truth** for the upgrade. Historical notes in `CORRECTIONS-v9.7.0.md` / `SECURITY-REVIEW-v9.7.0.md` do not override it.

---

## Live HA audit (2026-11-13 15:42 CET)

Recorded on the production host **before** this upgrade (read-only):

| Item | Live value |
|------|------------|
| Installed addon | `1.7.1-kamien5.3` |
| Predbat Core | `v9.6.5` |
| `switch.predbat_auto_update` | `off` |
| `min_soc_on_grid` | `11%` |
| `update.predbat_version` | sees upstream **`v9.7.10`** |

This PR vendors that same upstream tag into the hardened fork. It does **not** change live HA.

---

## CI (PR #5 head)

Sign-off is on the **current head of PR #5**, not on historical SHAs `6e88899…` or `2499317…`. Those earlier heads were green; they are superseded by the B1–B6 fix commit. Exact SHA and Actions run URL: the PR description.

| Check | Required result on the signed SHA |
|-------|-----------------------------------|
| Unit tests | **success** |
| Docker build (amd64) | **success** |
| Docker build (aarch64) | **success** |

`.github/workflows/publish.yml` does **not** run on the PR. It runs only after merge to `main` (see procedure below).

---

## Why v9.7.10 (not stay on v9.7.0)

Upstream `springfall2008/batpred` latest release is **v9.7.10** (2026-11-11), commit `54a8cbb2b8bf66fd1005053cd89d6c80725c2801`. Live HA already sees that tag.

v9.7.0→v9.7.10 is a straight patch series (v9.7.1 … v9.7.10): Hanchu/Sunsynk/Octopus/GE Cloud fixes, kernel speed-ups, History billing, Growatt **experimental** (not used — this install is FoxESS), and MCP metadata/proxy-URL hardening on top of the v9.7.0 OAuth fixes. `github.py` / `download.py` are unchanged vs v9.7.0.

Vendored set: **118 files** (was 115; added `growatt.py`, `growatt_const.py`, `dummy_inverter.py`). MANIFEST verified.

**Unchanged fork controls** (not taken from upstream defaults):

- Self-update **OFF** (`launch.py` stubs + vendor `auto_update` default `False`)
- Min SoC **11%** is the live HA entity `number.min_soc_on_grid` (not rewritten here)
- FC/PV (external HA automation): **inside** a `Charging*` window Force Charge stays **on** despite high PV; **outside** `Charging*` windows high PV **blocks** Force Charge (inverter switches to `Self Use`)
- MCP off + source-IP middleware (`FORBIDDEN_ENABLED_OPTIONS = ("mcp_enable",)`, ingress `172.30.32.2`)

---

## Blocker #1 — source pin (resolved: abandon local `build: true`)

Home Assistant Supervisor **cannot** prove a git SHA before a local `build: true`. The image field is `{image}:{addon version}` with `{arch}` substitution; a single `@sha256:` in `config.yaml` cannot cover both amd64 and aarch64.

**B4 closed (Piotr, 2026-11-13 17:00 CET, `t429s1509`)**: switching from Supervisor local build to the public image `ghcr.io/kamien5/predbat-addon/{arch}` is **accepted**.

**Chosen path** (works with Supervisor, no extra HA credentials, `hassio_api: false`):

1. CI `ci.yml` keeps **cache-only** multi-arch builds on every PR (prove Dockerfile).
2. `config.yaml` sets `image: ghcr.io/kamien5/predbat-addon/{arch}` — Supervisor **pulls**, it does not rebuild from git.
3. Merge PR #5 to **`main` first**. Supervisor reads `config.yaml` from the default branch.
4. `.github/workflows/publish.yml` on `main` pushes **immutable** version tags. `workflow_dispatch` requires `expected_sha` (40-char hex) and asserts `github.sha == expected_sha`. Tag `kamien5-v*` is the other trigger. GHCR login happens **before** the tag probe. The probe is **fail-closed**: only a clean missing-manifest response allows publish; auth/network/401/403/5xx/rate-limit abort.
5. Each image is labelled `org.opencontainers.image.revision=<merge commit SHA on main>`.
6. Before W41, verify those labels and digests **from the operator box against GHCR**. Do **not** commit a digest fill-in to `IMAGE-DIGESTS.md` before deploy (that would move HEAD after review). Optional post-deploy documentation only.

The GHCR package must be **public** (Supervisor has no registry login).

Local `build: true` is **not** used for this upgrade.

---

## Backup policy (Piotr, 31.10 — standing)

Before **any** mutation on live HA:

- **Only** a **full, unencrypted** Supervisor backup (`protected: false`).
- **No** password, **no** encryption key.
- Verify: backup info (`type=full`, `protected=false`, size > 0, `content.homeassistant=true`) before the addon update.
- Do not reuse an old backup as the pre-mutation copy.

---

## Fresh one-shot grants (do not reuse W32 / W33 / old W41)

Ledger is fail-closed. These hashes are **consumed or invalid** and must not be sent:

| Label | Status | canon_sha256 | Why invalid |
|-------|--------|--------------|-------------|
| **W32** | consumed | `cfd9c644…` | `/store/reload` without `timeout` |
| **W33** | consumed | `a411a7ed…` | addon update without `data` |
| old **W41** | invalid / do not issue | `20d0c320501867a3c844be5e3cbd567fa1b9f743e84840e50d4b103726978412` | payload `{"data":{"version":"1.7.1-kamien5.5"},...}` — Supervisor `SCHEMA_UPDATE` accepts only `backup` and `background`; HTTP 400 would burn a one-shot grant |

Canonicalisation: `sha256(json.dumps(msg, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8"))`.

| Label | Purpose | canon_sha256 | Exact message |
|-------|---------|--------------|----------------|
| **W40** | Store reload (timeout 120 so the hash ≠ consumed W32) | `32e0b905acda79ce0561a3c30334eacf3466aa02b605ab0cd93f4e509b256df4` | `{"endpoint":"/store/reload","method":"post","timeout":120,"type":"supervisor/api"}` |
| **W41** | Addon update; Supervisor schema `{backup, background}` only | `c93f100b55152cf300a2dc4473fecea2a2cad32e38da6c37d3f7be84f79b7074` | `{"data":{"backup":false},"endpoint":"/addons/fc83ef65_predbat/update","method":"post","timeout":1800,"type":"supervisor/api"}` |

**Hard pre-check before W41:** GET `/store/addons/fc83ef65_predbat` (or `/addons/fc83ef65_predbat/info`) must show `version_latest == "1.7.1-kamien5.5"`. If not, **STOP** — do not send W41.

W40/W41 require **new FAL entries** on the Mac helper (native approval). Do not reset ledgers.

---

## Security + QA checklist (same current PR #5 head SHA)

Both reviewers sign the **same** git SHA of this PR head (the SHA in the PR description, not `6e88899` / `2499317`).

### Security

- [ ] `predbat/VENDOR.txt` is `v9.7.10` / `54a8cbb2b8bf66fd1005053cd89d6c80725c2801` / 118 files
- [ ] `cd predbat/vendor && sha256sum --strict -c --quiet ../MANIFEST.sha256`
- [ ] `apps.yaml` has no `mcp_enable: true` and no `auto_update: true`
- [ ] `launch.py` still stubs download helpers; MCP fail-closed; ingress IP allowlist
- [ ] `config.yaml`: `image: ghcr.io/kamien5/predbat-addon/{arch}`, `hassio_api: false`, no `build: true`
- [ ] `build.yaml` base images still digest-pinned
- [ ] `publish.yml`: `expected_sha` required on `workflow_dispatch`; `github.sha == expected_sha`; GHCR login **before** tag probe; tag probe fail-closed; permissions only `contents: read` + `packages: write` (no `id-token` / `attestations`)
- [ ] W40 hash `32e0b905…` and W41 hash `c93f100b…` match helper FAL entries (new, unused). W32 / W33 / `20d0c320…` not issued
- [ ] GHCR package public; version tag not overwritten
- [ ] No merge, no live HA, no Mac helper install from this PR alone (merge is a **later** human step after both TAK)

### QA

- [ ] GitHub Actions on **this** SHA: Unit tests, Docker build (amd64), Docker build (aarch64) all **success**
- [ ] Local: `.venv/bin/python -m unittest discover -s tests -v` — no skipped tests in CI
- [ ] Addon version string `1.7.1-kamien5.5`
- [ ] After a future install (not now): Core reports v9.7.10; `switch.predbat_auto_update=off`; `min_soc_on_grid=11%`; FC/PV: **inside** `Charging*` Force Charge stays on despite high PV; **outside** `Charging*` high PV blocks Force Charge (inverter → `Self Use`) — external HA
- [ ] Backup taken immediately before any mutation is full + unencrypted

---

## Upgrade procedure (after both TAK — humans only)

Supervisor reads `config.yaml` from default branch **`main`**. Do not publish GHCR or send W40/W41 from the PR branch.

```
T−2:  Piotr or Marcin merge PR #5 into main
      (only after Security TAK and QA TAK on the same PR head SHA).
T−1:  Record the merge commit SHA on main.
      Optional git tag: kamien5-v5 (addon 1.7.1-kamien5.5, engine v9.7.10).
      Do not use the leftover name kamien5-v4.

T0:   On main, run .github/workflows/publish.yml
      — workflow_dispatch with expected_sha=<merge commit SHA>
        (github.sha must equal that SHA), or
      — push tag kamien5-v5 pointing at that merge commit.

T1:   From the operator box, inspect GHCR (not HAOS docker inspect):
        ghcr.io/kamien5/predbat-addon/amd64:1.7.1-kamien5.5
        ghcr.io/kamien5/predbat-addon/aarch64:1.7.1-kamien5.5
      Require org.opencontainers.image.revision == <merge SHA>
      and org.opencontainers.image.version == 1.7.1-kamien5.5.
      Record digests locally. Do not commit IMAGE-DIGESTS.md before deploy.

T2:   Full unencrypted backup; verify info (protected=false, type=full, size>0)

T3:   W40 store reload
      32e0b905acda79ce0561a3c30334eacf3466aa02b605ab0cd93f4e509b256df4

T4:   Pre-check W41 (hard STOP if it fails):
      GET /store/addons/fc83ef65_predbat
      (or GET /addons/fc83ef65_predbat/info)
      must show version_latest == "1.7.1-kamien5.5".
      If not, STOP — do not send W41.

T5:   W41 addon update (backup:false; Supervisor pulls GHCR; timeout 1800)
      c93f100b55152cf300a2dc4473fecea2a2cad32e38da6c37d3f7be84f79b7074

T6:   Post-update via Supervisor API and HA entities only
      (no HAOS debug SSH, no docker inspect on the appliance):
      GET /addons/fc83ef65_predbat/info
      GET /addons/fc83ef65_predbat/logs  (must show v9.7.10)
      HA: Core v9.7.10, switch.predbat_auto_update=off, min_soc_on_grid=11%

T7:   2–4h observation
```

Rollback: restore the **same** full unencrypted backup taken at T2.

---

## Out of scope (this iteration)

- 5 kW cap removal (external HA package)
- 14 kW / 23 A guardian (external HA)
- Merging PR #5 **now** (allowed only after both TAK, as T−2 above)
- Live HA or Mac helper changes from this agent

---

## References

- Upstream: [batpred v9.7.10](https://github.com/springfall2008/batpred/releases/tag/v9.7.10)
- Previous live: `kamien5-v3` (addon `1.7.1-kamien5.3`, engine v9.6.5)
- After merge to `main`: record **merge commit SHA**; optional tag `kamien5-v5` for addon `1.7.1-kamien5.5`
- GHCR decision: Piotr 2026-11-13 17:00 CET, `t429s1509`

**Document status**: ACTIVE — single source of truth for this upgrade.  
**Updated**: 2026-11-13
