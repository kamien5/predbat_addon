# Predbat add-on startup tests

## Automated

From the repository root (Python 3.9+):

```bash
python3 -m unittest discover -s tests -v
```

These tests use the standard library only. They exercise `predbat/rootfs/startup.py`
against a temporary copy of the pinned `predbat/vendor` tree, plus config/build
static checks and launch web hardening. They do not start Home Assistant or
Predbat (`PREDBAT_SKIP_LAUNCH=1`). aiohttp-dependent web tests skip when aiohttp
is not installed.

Defensive hardening covered here: mask secret-like and location fields in web
UI/API responses, restrict UI to ingress, disable raw apps.yaml editor/export
endpoints (apps.yaml is regenerated on every start).

## Manual on-device check

After installing/rebuilding the add-on:

1. In the add-on config share (e.g. `/addon_configs/<slug>/`), replace a pinned file such as `predbat.py` with different contents.
2. Restart the add-on.
3. In the add-on log, confirm a line `restored: predbat.py`.
4. Confirm the restored file matches the image pin, e.g. its sha256 equals the corresponding line in the image `MANIFEST.sha256` (also under `/opt/predbat/MANIFEST.sha256` inside the container).
5. After a restart, confirm `/addon_configs/<slug>/apps.yaml` is the pinned image copy with latitude/longitude taken from Home Assistant config and `notify_device` from add-on options (no unsubstituted placeholders).
6. In Home Assistant, change `select.predbat_update` (or otherwise trigger a Predbat version update). The log should show that self-update is disabled in the kamien5 fork (pinned v9.5.0), and the files under the config share must stay on the pinned hashes.
