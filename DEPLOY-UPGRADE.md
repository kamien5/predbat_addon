# Predbat v9.7.10 Deployment and Upgrade

**Branch**: `cursor/vendor-predbat-v9.7.0-2ba3`  
**PR**: [#5](https://github.com/kamien5/predbat_addon/pull/5)  
**Addon**: `1.7.1-kamien5.5`  
**Engine**: Predbat **v9.7.10** (`54a8cbb2b8bf66fd1005053cd89d6c80725c2801`)  
**Status**: Ready for parallel Security + QA review of the **same final commit SHA**. Do not merge until both approve. No live HA/Mac mutation from this document.

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

## CI (head SHA `6e88899bc8258336feea12aa1109c4df1c4e25b9` and later)

| Check | Result |
|-------|--------|
| Unit tests | **success** (not PENDING) |
| Docker build (amd64) | **success** |
| Docker build (aarch64) | **success** |

Re-run CI on the final commit of this PR before sign-off. All three must stay green.

---

## Why v9.7.10 (not stay on v9.7.0)

Upstream `springfall2008/batpred` latest release is **v9.7.10** (2026-11-11), commit `54a8cbb2b8bf66fd1005053cd89d6c80725c2801`. Live HA already sees that tag.

v9.7.0→v9.7.10 is a straight patch series (v9.7.1 … v9.7.10): Hanchu/Sunsynk/Octopus/GE Cloud fixes, kernel speed-ups, History billing, Growatt **experimental** (not used — this install is FoxESS), and MCP metadata/proxy-URL hardening on top of the v9.7.0 OAuth fixes. `github.py` / `download.py` are unchanged vs v9.7.0.

Vendored set: **118 files** (was 115; added `growatt.py`, `growatt_const.py`, `dummy_inverter.py`). MANIFEST verified.

**Unchanged fork controls** (not taken from upstream defaults):

- Self-update **OFF** (`launch.py` stubs + vendor `auto_update` default `False`)
- Min SoC **11%** is the live HA entity `number.min_soc_on_grid` (not rewritten here)
- FC PV exception (outside charge window only) is **external HA** automation — out of this repo
- MCP off + source-IP middleware (`FORBIDDEN_ENABLED_OPTIONS = ("mcp_enable",)`, ingress `172.30.32.2`)

---

## Blocker #1 — source pin (resolved: abandon local `build: true`)

Home Assistant Supervisor **cannot** prove a git SHA before a local `build: true`. The image field is `{image}:{addon version}` with `{arch}` substitution; a single `@sha256:` in `config.yaml` cannot cover both amd64 and aarch64.

**Chosen path** (works with Supervisor, no extra HA credentials, `hassio_api: false`):

1. CI `ci.yml` keeps **cache-only** multi-arch builds on every PR (prove Dockerfile).
2. `config.yaml` sets `image: ghcr.io/kamien5/predbat-addon/{arch}` — Supervisor **pulls**, it does not rebuild from git.
3. `.github/workflows/publish.yml` pushes **immutable** version tags from the reviewed SHA (`workflow_dispatch` or tag `kamien5-v*`). It **refuses** to overwrite an existing version tag.
4. Each image is labelled `org.opencontainers.image.revision=<git SHA>`.
5. After publish, record per-arch registry digests in [`predbat/IMAGE-DIGESTS.md`](./predbat/IMAGE-DIGESTS.md).
6. After HA install, inspect the running container: label SHA and `RepoDigests` must match.

The GHCR package must be **public** (Supervisor has no registry login). Do not deploy until both digests are recorded.

Local `build: true` is **not** used for this upgrade.

---

## Backup policy (Piotr, 31.10 — standing)

Before **any** mutation on live HA:

- **Only** a **full, unencrypted** Supervisor backup (`protected: false`).
- **No** password, **no** encryption key.
- Verify: backup info (`type=full`, `protected=false`, size > 0, `content.homeassistant=true`) before the addon update.
- Do not reuse an old backup as the pre-mutation copy.

---

## Fresh one-shot grants (do not reuse W32/W33)

Ledger is fail-closed. **W32** and **W33** are **consumed**. Identical payloads hash to the same digest and **must not** be sent again.

Canonicalisation: `sha256(json.dumps(msg, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("ascii"))`.

| Label | Purpose | canon_sha256 | Exact message |
|-------|---------|--------------|----------------|
| **W40** | Store reload (timeout 120 so the hash ≠ consumed W32) | `32e0b905acda79ce0561a3c30334eacf3466aa02b605ab0cd93f4e509b256df4` | `{"endpoint":"/store/reload","method":"post","timeout":120,"type":"supervisor/api"}` |
| **W41** | Addon update to **1.7.1-kamien5.5** (explicit version so the hash ≠ consumed W33) | `20d0c320501867a3c844be5e3cbd567fa1b9f743e84840e50d4b103726978412` | `{"data":{"version":"1.7.1-kamien5.5"},"endpoint":"/addons/fc83ef65_predbat/update","method":"post","timeout":1800,"type":"supervisor/api"}` |

W40/W41 require **new FAL entries** on the Mac helper (native approval). Do not reset ledgers. Do not send W32 (`cfd9c644…` `/store/reload` without timeout) or W33 (`a411a7ed…` update without `data`).

---

## Security + QA checklist (same final commit SHA)

Both reviewers sign the **same** git SHA of this PR head (not `6e88899` once further commits land).

### Security

- [ ] `predbat/VENDOR.txt` is `v9.7.10` / `54a8cbb2b8bf66fd1005053cd89d6c80725c2801` / 118 files
- [ ] `cd predbat/vendor && sha256sum --strict -c --quiet ../MANIFEST.sha256`
- [ ] `apps.yaml` has no `mcp_enable: true` and no `auto_update: true`
- [ ] `launch.py` still stubs download helpers; MCP fail-closed; ingress IP allowlist
- [ ] `config.yaml`: `image: ghcr.io/kamien5/predbat-addon/{arch}`, `hassio_api: false`, no `build: true`
- [ ] `build.yaml` base images still digest-pinned
- [ ] W40/W41 hashes above match the helper FAL entries (new, unused)
- [ ] GHCR package public; version tag not overwritten
- [ ] No merge, no live HA, no Mac helper install from this PR alone

### QA

- [ ] GitHub Actions on **this** SHA: Unit tests, Docker build (amd64), Docker build (aarch64) all **success**
- [ ] Local: `.venv/bin/python -m unittest discover -s tests -v` — no skipped tests in CI
- [ ] Addon version string `1.7.1-kamien5.5`
- [ ] After a future install (not now): Core reports v9.7.10; `switch.predbat_auto_update=off`; `min_soc_on_grid=11%`; FC PV exception still only outside `Charging*` windows (external HA)
- [ ] Backup taken immediately before any mutation is full + unencrypted

---

## Upgrade procedure (after both reviews + GHCR publish + digest fill-in)

```
T+0:   Full unencrypted backup; verify info (protected=false)
T+1:   Confirm IMAGE-DIGESTS.md has both arch sha256 values
T+2:   W40 store reload
T+3:   W41 addon update 1.7.1-kamien5.5 (Supervisor pulls GHCR; timeout 1800)
T+4:   Inspect container label revision + RepoDigests
T+5:   Confirm Core v9.7.10, auto_update off, min_soc 11%
T+6:   2–4h observation
```

Rollback: restore the **same** full unencrypted backup taken at T+0.

---

## Out of scope

- 5 kW cap removal (external HA package)
- 14 kW / 23 A guardian (external HA)
- Merge of PR #5
- Live HA or Mac helper changes

---

## References

- Upstream: [batpred v9.7.10](https://github.com/springfall2008/batpred/releases/tag/v9.7.10)
- Previous live: `kamien5-v3` (addon `1.7.1-kamien5.3`, engine v9.6.5)
- Proposed tag after merge: `kamien5-v4` (triggers publish.yml)

**Document status**: ACTIVE — single source of truth for this upgrade.  
**Updated**: 2026-11-13
