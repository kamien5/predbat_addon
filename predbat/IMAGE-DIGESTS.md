# GHCR image digests — 1.7.1-kamien5.5

Supervisor does **not** accept a single `@sha256:` pin in `config.yaml` for
both `amd64` and `aarch64`. It substitutes `{arch}` and tags with `version`:

```
ghcr.io/kamien5/predbat-addon/{arch}:1.7.1-kamien5.5
```

## Before publish

| Arch | Image | Digest | Git SHA |
|------|-------|--------|---------|
| amd64 | `ghcr.io/kamien5/predbat-addon/amd64:1.7.1-kamien5.5` | *pending `.github/workflows/publish.yml`* | reviewed PR head |
| aarch64 | `ghcr.io/kamien5/predbat-addon/aarch64:1.7.1-kamien5.5` | *pending `.github/workflows/publish.yml`* | reviewed PR head |

Version tags are **immutable**: publish.yml refuses to push if the tag already exists.

## After publish (fill from the workflow artifact / summary)

Copy the two `sha256:...` lines from the publish job into this table **before**
the HA store reload. Then on the HA host, after the addon starts:

```
docker inspect <container> --format '{{index .Config.Labels "org.opencontainers.image.revision"}}'
docker inspect <container> --format '{{json .RepoDigests}}'
```

`org.opencontainers.image.revision` must equal the reviewed git SHA.
`RepoDigests` must equal the amd64 or aarch64 digest recorded above.

The GHCR package must be **public** so Supervisor can pull without registry credentials (`hassio_api: false`, no extra docker login on HA).
