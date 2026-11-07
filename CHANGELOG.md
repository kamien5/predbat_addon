# Predbat_addon CHANGELOG

## 1.7.1-kamien5.4 (kamien5 fork)

- Vendor Predbat v9.7.0 (4cbf633355525ea62ddf8e47e647ee215b38f1ca, 25 commits from v9.6.5)
- Upstream MCP OAuth security hardening (#5847, #5992) — not applicable (MCP disabled, endpoints blocked)
- New billing.py module (Octopus/Kraken billing API) — inactive in this installation
- Upstream improvements: plan export gate (#5977), Solcast P10/P90 calibration (#5974), execute Control SOC (#6001), Sunsynk BMS battery size (#6007), GE Cloud optimization (#6005)
- All security tests passing; kamien5 hardening preserved
- apps.yaml configuration unchanged (guardian FC+PV 0.5kW, min SoC 11%, no forced export)
- See UPGRADE-v9.7.0.md for detailed review and deployment plan

## 1.7.1-kamien5.3 (kamien5 fork)

- Vendor Predbat v9.6.5 (86b01646e09bdc1594a9ffd361e5880c05fd3089)
- Self-update remains disabled (kamien5 fork policy); `select.predbat_update` stubs unchanged
- MANIFEST.sha256 regenerated and verified; apps.yaml hash preserved (bfb291ea...)
- See upstream release notes v9.5.1–v9.6.5 for Predbat engine improvements (plan stability, car charging, clock-change, load spike handling, Fox logging, marginal cost sensors)

## 1.7.1-kamien5.2 (kamien5 fork)

- Fix Dockerfile to use pinned Ubuntu base images regardless of BUILD_FROM arg passed by Supervisor (prevents fallback to Alpine base which lacks apt-get)

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
