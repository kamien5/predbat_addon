# Predbat_addon CHANGELOG

## 1.7.1-kamien5.1 (kamien5 fork)

- Predbat v9.5.0 vendored into the image and verified against `MANIFEST.sha256` on every start; runtime download and self-update disabled
- Supervisor token kept out of logs and command-line arguments
- Reduced add-on permissions (`hassio_api: false`, `addon_config` only, no host ports), aarch64 and amd64 only
- Hash-pinned Python requirements and base images pinned by digest
- `apps.yaml` shipped with the add-on and rendered on every start; new `notify_device` option (empty means no notifications, `notify_devices: []`)
- Web UI limited to Home Assistant ingress, sensitive fields masked, admin endpoints restricted
- Unit tests

## 1.2.2

- Add Jinja2 to the addon requirements by @iainfogg in #22
- Update DOCS.md, add link to Predbat upgrade instructions by @gcoan in #19

## 1.2.0

- Change to using Ingress for web i/f
- Allows installation of Predbat addon by @ASTPlatinum in #7
- Increase number of file generations of logfile retained by @gcoan in #11
