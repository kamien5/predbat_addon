# GHCR image digests — 1.7.1-kamien5.5

Supervisor does **not** accept a single `@sha256:` pin in `config.yaml` for
both `amd64` and `aarch64`. It substitutes `{arch}` and tags with `version`:

```
ghcr.io/kamien5/predbat-addon/{arch}:1.7.1-kamien5.5
```

## Provenance (do not mutate this file before deploy)

After PR #5 is merged to `main`, `.github/workflows/publish.yml` builds from
**that merge commit**. Each image is labelled:

```
org.opencontainers.image.revision = <merge commit SHA on main>
org.opencontainers.image.version  = 1.7.1-kamien5.5
```

Do **not** add a follow-up commit that fills the table below before deploy.
That would move HEAD after Security + QA review. Digests are verified **in
flight** from GHCR on the operator box before W41. Filling this file is
optional **post-deploy documentation**, not a deploy gate.

## Verify from the operator box (before W41)

Replace `MERGE_SHA` with the merge commit on `main`:

```
for arch in amd64 aarch64; do
  img="ghcr.io/kamien5/predbat-addon/${arch}:1.7.1-kamien5.5"
  docker buildx imagetools inspect "$img"
  # Confirm:
  #   Digest: sha256:...
  #   org.opencontainers.image.revision == MERGE_SHA
  #   org.opencontainers.image.version  == 1.7.1-kamien5.5
done
```

Do **not** use `docker inspect` on HAOS (that would need debug SSH). After the
addon update, confirm via Supervisor API (`/addons/fc83ef65_predbat/info` and
`/addons/fc83ef65_predbat/logs`) plus HA entity states.

Version tags are **immutable**: `publish.yml` logs into GHCR first, then
fail-closed refuses to push if the tag already exists or if the probe is not a
clean missing-manifest response.

## Recorded digests (optional post-deploy)

| Arch | Image | Digest | Git SHA (merge on `main`) |
|------|-------|--------|---------------------------|
| amd64 | `ghcr.io/kamien5/predbat-addon/amd64:1.7.1-kamien5.5` | *optional post-deploy record; not a deploy gate* | merge SHA on `main` |
| aarch64 | `ghcr.io/kamien5/predbat-addon/aarch64:1.7.1-kamien5.5` | *optional post-deploy record; not a deploy gate* | merge SHA on `main` |

The GHCR package must be **public** so Supervisor can pull without registry
credentials (`hassio_api: false`, no extra docker login on HA).
