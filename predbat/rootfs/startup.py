#!/usr/bin/env python3
"""
Predbat add-on startup (kamien5 fork).

Every start:
  1. Verify the image-pinned vendor tree against MANIFEST.sha256.
  2. Strip dangerous/stale code from CONFIG_DIR (plugins, package shadows, staged updates).
  3. Reinstall every pinned file into CONFIG_DIR (overwrite local edits).
  4. Install apps.yaml from the image (sha256-pinned; HA lat/lon and notify device substituted).
  5. Write a local manifest.yaml so Predbat check_install never contacts GitHub.
  6. Launch Predbat via the image launch.py (self-update stubs).

Stdlib only. Network is used only to read Home Assistant /config for coordinates.
SUPERVISOR_TOKEN is read from the environment only and never printed.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

# Paths are overridable for tests; production uses /config and /opt/predbat.
CONFIG_DIR = os.environ.get("PREDBAT_CONFIG_DIR", "/config")
IMAGE_DIR = os.environ.get("PREDBAT_IMAGE_DIR", "/opt/predbat")
APPS_YAML_SRC = os.environ.get("PREDBAT_APPS_YAML_SRC", "/apps.yaml")
APPS_YAML_SHA256 = (
    "bc4b790e3a8f63230f6ce3e4b680a9cab51d4f6212cc6072dae3f2862da3f1ee"
)
HA_API_URL = os.environ.get("PREDBAT_HA_API_URL", "http://supervisor/core/api")
OPTIONS_JSON = os.environ.get("PREDBAT_OPTIONS_JSON", "/data/options.json")

# sha256sum --strict style: "<64 hex>  <safe filename>" (exactly two spaces).
MANIFEST_LINE_RE = re.compile(
    r"^([0-9a-f]{64})  ([A-Za-z0-9][A-Za-z0-9._-]*)$"
)
NOTIFY_DEVICE_RE = re.compile(r"^[a-z0-9_]+$")
PLACEHOLDER_RE = re.compile(r"__HA_[A-Z0-9_]*__")
NOTIFY_DEVICE_TOKEN = "[__HA_NOTIFY_DEVICE__]"

# Staged self-update leftovers such as predbat.py.v9.6.0 or foo.so.tag
STAGED_SUFFIX_RE = re.compile(r"\.(py|so)\.[^/]+$")

CODE_SUFFIXES = (".py", ".pyc", ".so")


def _error(message: str) -> None:
    print("Error: {}".format(message))
    sys.exit(1)


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_blob_sha1(data: bytes) -> str:
    """Git blob SHA1: sha1(b'blob <size>\\0' + data). Matches GitHub Contents API."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def check_supervisor_token() -> None:
    """
    Require SUPERVISOR_TOKEN unless PREDBAT_TEST_MODE=1 (unit tests only).

    Token is read only from os.environ; never logged, never taken from argv.
    """
    token = os.environ.get("SUPERVISOR_TOKEN")
    test_mode = os.environ.get("PREDBAT_TEST_MODE") == "1"
    if not token and not test_mode:
        print("Error: SUPERVISOR_TOKEN not set in environment")
        sys.exit(1)
    if token:
        print("SUPERVISOR_TOKEN present (value not logged)")


def load_manifest(path: str) -> dict:
    """
    Strict-parse MANIFEST.sha256.

    Returns an ordered mapping filename -> sha256 hex.
    Any bad line, duplicate name, or empty file causes exit 1.
    """
    if not os.path.isfile(path):
        _error("manifest not found: {}".format(path))

    mapping = {}
    with open(path, "r", encoding="utf-8") as handle:
        lines = handle.read().splitlines()

    if not lines:
        _error("manifest is empty: {}".format(path))

    for lineno, line in enumerate(lines, start=1):
        match = MANIFEST_LINE_RE.match(line)
        if not match:
            _error(
                "manifest line {}: malformed (expected '<sha256>  <filename>')".format(
                    lineno
                )
            )
        digest, name = match.group(1), match.group(2)
        if "/" in name or ".." in name:
            _error("manifest line {}: illegal filename {!r}".format(lineno, name))
        if name in mapping:
            _error("manifest line {}: duplicate filename {!r}".format(lineno, name))
        mapping[name] = digest

    return mapping


def verify_vendor() -> dict:
    """
    Ensure IMAGE_DIR/vendor matches the pinned manifest exactly.

    Regular files only; no extras, missing files, symlinks, or subdirectories.
    On failure, exit 1 before any CONFIG_DIR mutation.
    """
    manifest_path = os.path.join(IMAGE_DIR, "MANIFEST.sha256")
    vendor_dir = os.path.join(IMAGE_DIR, "vendor")
    manifest = load_manifest(manifest_path)

    if not os.path.isdir(vendor_dir):
        print(
            "Error: pinned Predbat code failed verification: vendor: "
            "directory missing"
        )
        sys.exit(1)

    on_disk = {}
    try:
        names = os.listdir(vendor_dir)
    except OSError as exc:
        print(
            "Error: pinned Predbat code failed verification: vendor: {}".format(exc)
        )
        sys.exit(1)

    for name in names:
        path = os.path.join(vendor_dir, name)
        # Reject symlinks and anything that is not a plain regular file.
        if os.path.islink(path) or not os.path.isfile(path):
            print(
                "Error: pinned Predbat code failed verification: {}: "
                "not a regular file".format(name)
            )
            sys.exit(1)
        on_disk[name] = path

    expected = set(manifest)
    actual = set(on_disk)

    for name in sorted(expected - actual):
        print(
            "Error: pinned Predbat code failed verification: {}: missing".format(name)
        )
        sys.exit(1)

    for name in sorted(actual - expected):
        print(
            "Error: pinned Predbat code failed verification: {}: unexpected".format(
                name
            )
        )
        sys.exit(1)

    for name, expected_hash in manifest.items():
        actual_hash = _sha256_file(on_disk[name])
        if actual_hash != expected_hash:
            print(
                "Error: pinned Predbat code failed verification: {}: "
                "sha256 mismatch".format(name)
            )
            sys.exit(1)

    print(
        "Verified {} pinned Predbat files in {}".format(len(manifest), vendor_dir)
    )
    return manifest


def _remove_path(path: str, label: str) -> None:
    """Remove a file, symlink, or directory; log the name only (never contents)."""
    print("removing: {}".format(label))
    try:
        if os.path.islink(path) or os.path.isfile(path):
            os.unlink(path)
        elif os.path.isdir(path):
            shutil.rmtree(path)
        else:
            # Unusual node types (fifo, etc.): best-effort unlink.
            os.unlink(path)
    except OSError as exc:
        _error("failed to remove {}: {}".format(label, exc))


def clean_config_dir(manifest: dict) -> None:
    """
    Remove code that could shadow or extend the pinned install.

    Never deletes apps.yaml (install_apps_yaml overwrites it), secrets.yaml,
    predbat.log, predbat_save/, or other non-code YAML settings.
    """
    manifest_names = set(manifest)
    py_stems = {name[:-3] for name in manifest_names if name.endswith(".py")}

    try:
        entries = os.listdir(CONFIG_DIR)
    except OSError as exc:
        _error("cannot list CONFIG_DIR {}: {}".format(CONFIG_DIR, exc))

    for name in sorted(entries):
        path = os.path.join(CONFIG_DIR, name)

        # Always drop bytecode caches and the plugins tree (plugin_system loads *_plugin.py).
        if name == "__pycache__" or name == "plugins":
            _remove_path(path, name)
            continue

        # Stale Predbat manifest must be regenerated from pinned files.
        if name == "manifest.yaml":
            _remove_path(path, name)
            continue

        # Package directories (or symlinks to them) that would beat foo.py on sys.path,
        # or whose name equals a vendored module stem (e.g. predbat/ vs predbat.py).
        if os.path.isdir(path):
            has_init = os.path.isfile(os.path.join(path, "__init__.py"))
            if has_init or name in py_stems:
                _remove_path(path, name)
            continue

        # Symlink pretending to be a pinned file: drop so install can place a real file.
        if os.path.islink(path) and name in manifest_names:
            _remove_path(path, name)
            continue

        # Top-level code / staged-update artifacts that are not pinned names.
        if name in manifest_names:
            continue

        is_code = name.endswith(CODE_SUFFIXES) or STAGED_SUFFIX_RE.search(name)
        if is_code and (os.path.isfile(path) or os.path.islink(path)):
            _remove_path(path, name)


def _destination_mode(source_path: str, dest_name: str) -> int:
    """0644 for .py by default; keep 0755 when the image source is executable."""
    try:
        source_mode = os.stat(source_path).st_mode
    except OSError:
        source_mode = 0
    if source_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
        return 0o755
    if dest_name.endswith(".py"):
        return 0o644
    return 0o644


def install_code(manifest: dict) -> None:
    """
    Copy every pinned vendor file into CONFIG_DIR via temp + os.replace.

    Always overwrites. Re-hashes the destination; mismatch exits 1.
    Logs restored: <name> for files that were missing or different beforehand.
    """
    vendor_dir = os.path.join(IMAGE_DIR, "vendor")
    restored = []

    for name, expected_hash in manifest.items():
        source = os.path.join(vendor_dir, name)
        dest = os.path.join(CONFIG_DIR, name)

        was_ok = False
        if os.path.isfile(dest) and not os.path.islink(dest):
            try:
                was_ok = _sha256_file(dest) == expected_hash
            except OSError:
                was_ok = False
        if not was_ok:
            restored.append(name)

        # Atomic replace within CONFIG_DIR so a crash mid-write cannot leave a partial file
        # as the only copy of a pinned module name.
        fd = None
        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(
                prefix=".{}.tmp.".format(name), dir=CONFIG_DIR
            )
            with os.fdopen(fd, "wb") as out_handle:
                fd = None  # ownership transferred
                with open(source, "rb") as in_handle:
                    shutil.copyfileobj(in_handle, out_handle)
            mode = _destination_mode(source, name)
            os.chmod(tmp_path, mode)
            os.replace(tmp_path, dest)
            tmp_path = None
        except OSError as exc:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            _error("failed to install {}: {}".format(name, exc))
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        actual_hash = _sha256_file(dest)
        if actual_hash != expected_hash:
            _error(
                "installed file hash mismatch for {}: expected {}, got {}".format(
                    name, expected_hash, actual_hash
                )
            )

    for name in restored:
        print("restored: {}".format(name))
    print(
        "Installed {} pinned Predbat files into {}".format(len(manifest), CONFIG_DIR)
    )


def _yaml_quote(value: str) -> str:
    """Minimal double-quoted YAML scalar (stdlib only)."""
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )
    return '"{}"'.format(escaped)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never follow redirects, so the Bearer token cannot be forwarded elsewhere."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


# No proxies from the environment and no redirects for the HA API call.
_HA_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())


def fetch_ha_location() -> tuple:
    """
    GET Home Assistant /config for latitude and longitude.

    Uses SUPERVISOR_TOKEN as Bearer auth. Token is never logged.
    Retries up to 5 times; sleep between attempts is 10s (PREDBAT_RETRY_SLEEP).
    """
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        print("Error: SUPERVISOR_TOKEN not set in environment")
        sys.exit(1)

    try:
        retry_sleep = float(os.environ.get("PREDBAT_RETRY_SLEEP", "10"))
    except ValueError:
        retry_sleep = 10.0

    url = HA_API_URL + "/config"
    last_detail = None

    for attempt in range(5):
        try:
            request = urllib.request.Request(
                url,
                headers={"Authorization": "Bearer " + token},
                method="GET",
            )
            with _HA_OPENER.open(request, timeout=10) as response:
                body = response.read()
            data = json.loads(body.decode("utf-8"))
            lat = float(data["latitude"])
            lon = float(data["longitude"])
            if not math.isfinite(lat) or not math.isfinite(lon):
                raise ValueError("non-finite coordinates")
            if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
                raise ValueError("coordinates out of range")
            if lat == 0.0 and lon == 0.0:
                raise ValueError("coordinates both zero")
            return lat, lon
        except urllib.error.HTTPError as exc:
            last_detail = "HTTP {}".format(exc.code)
        except Exception as exc:
            last_detail = type(exc).__name__
        if attempt < 4:
            time.sleep(retry_sleep)

    print("Error: unable to read latitude/longitude from Home Assistant config")
    if last_detail:
        print(last_detail)
    sys.exit(1)


def read_notify_device() -> str:
    """
    Read add-on option notify_device from OPTIONS_JSON.

    Missing file yields "". Non-empty values must match ^[a-z0-9_]+$;
    the option value is never printed.
    """
    if not os.path.isfile(OPTIONS_JSON):
        return ""
    try:
        with open(OPTIONS_JSON, "r", encoding="utf-8") as handle:
            options = json.load(handle)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        print(
            "Error: add-on option notify_device is invalid (allowed: a-z, 0-9, _)"
        )
        sys.exit(1)

    if not isinstance(options, dict):
        print(
            "Error: add-on option notify_device is invalid (allowed: a-z, 0-9, _)"
        )
        sys.exit(1)

    raw = options.get("notify_device")
    if raw is None:
        value = ""
    elif not isinstance(raw, str):
        print(
            "Error: add-on option notify_device is invalid (allowed: a-z, 0-9, _)"
        )
        sys.exit(1)
    else:
        value = raw.strip()
    if value and not NOTIFY_DEVICE_RE.fullmatch(value):
        print(
            "Error: add-on option notify_device is invalid (allowed: a-z, 0-9, _)"
        )
        sys.exit(1)
    return value


def render_apps_yaml(text, latitude, longitude, notify_device) -> str:
    """
    Substitute apps.yaml placeholders for coordinates and notify device.

    Latitude/longitude are written with str(float(...)) when provided.
    The notify-device list token becomes [name] or [] when empty.
    """
    result = text
    if latitude is not None:
        result = result.replace("__HA_LATITUDE__", str(float(latitude)))
    if longitude is not None:
        result = result.replace("__HA_LONGITUDE__", str(float(longitude)))
    if notify_device:
        result = result.replace(NOTIFY_DEVICE_TOKEN, "[" + notify_device + "]")
    else:
        result = result.replace(NOTIFY_DEVICE_TOKEN, "[]")
    return result


def check_no_placeholders(text) -> None:
    """Exit 1 if any unsubstituted __HA_...__ placeholder remains."""
    if PLACEHOLDER_RE.search(text):
        print("Error: apps.yaml still contains unsubstituted placeholders")
        sys.exit(1)


def install_apps_yaml() -> None:
    """
    Verify image apps.yaml, substitute placeholders, write CONFIG_DIR/apps.yaml.

    Always overwrites local edits. Coordinates, notify device, and
    SUPERVISOR_TOKEN are never logged.
    """
    try:
        actual_hash = _sha256_file(APPS_YAML_SRC)
    except OSError:
        print("Error: apps.yaml in image failed verification")
        sys.exit(1)

    if actual_hash != APPS_YAML_SHA256:
        print("Error: apps.yaml in image failed verification")
        sys.exit(1)

    try:
        with open(APPS_YAML_SRC, "r", encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        _error("failed to read apps.yaml source: {}".format(exc))

    notify_device = read_notify_device()
    latitude = None
    longitude = None
    if "__HA_LATITUDE__" in text or "__HA_LONGITUDE__" in text:
        latitude, longitude = fetch_ha_location()

    text = render_apps_yaml(text, latitude, longitude, notify_device)
    check_no_placeholders(text)

    dest = os.path.join(CONFIG_DIR, "apps.yaml")
    fd = None
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(prefix=".apps.yaml.tmp.", dir=CONFIG_DIR)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            fd = None
            handle.write(text)
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, dest)
        tmp_path = None
    except OSError as exc:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        _error("failed to install apps.yaml: {}".format(exc))
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    notify_status = "set" if notify_device else "not set"
    print(
        "Installed apps.yaml (pinned sha256 {}, coordinates from Home Assistant "
        "config, notify device {})".format(APPS_YAML_SHA256, notify_status)
    )


def write_predbat_manifest(manifest: dict) -> None:
    """
    Write CONFIG_DIR/manifest.yaml in the shape check_install expects.

    Sorted YAML list of {name, size, sha (git blob sha1), type: file}.
    Hand-written emitter so we never depend on PyYAML in startup.
    """
    entries = []
    for name in sorted(manifest):
        path = os.path.join(CONFIG_DIR, name)
        with open(path, "rb") as handle:
            data = handle.read()
        entries.append(
            {
                "name": name,
                "size": len(data),
                "sha": git_blob_sha1(data),
                "type": "file",
            }
        )

    lines = []
    for entry in entries:
        lines.append("- name: {}".format(_yaml_quote(entry["name"])))
        lines.append("  size: {}".format(entry["size"]))
        lines.append("  sha: {}".format(_yaml_quote(entry["sha"])))
        lines.append("  type: {}".format(_yaml_quote(entry["type"])))

    dest = os.path.join(CONFIG_DIR, "manifest.yaml")
    payload = "\n".join(lines) + "\n"
    fd = None
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(prefix=".manifest.yaml.tmp.", dir=CONFIG_DIR)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            fd = None
            handle.write(payload)
        os.chmod(tmp_path, 0o644)
        os.replace(tmp_path, dest)
        tmp_path = None
    except OSError as exc:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        _error("failed to write manifest.yaml: {}".format(exc))
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    print("Wrote Predbat manifest.yaml ({} entries)".format(len(entries)))


def launch() -> None:
    """
    Run image launch.py with an isolated interpreter (-I -B).

    Env (including SUPERVISOR_TOKEN) is inherited; token is never placed in argv.
    PREDBAT_SKIP_LAUNCH=1 skips execution (tests only) after all checks/install.
    """
    if os.environ.get("PREDBAT_SKIP_LAUNCH") == "1":
        print("PREDBAT_SKIP_LAUNCH=1: skipping Predbat launch")
        return

    launch_py = os.path.join(IMAGE_DIR, "launch.py")
    if not os.path.isfile(launch_py):
        _error("launch.py not found: {}".format(launch_py))

    return_code = subprocess.call(
        [sys.executable, "-I", "-B", launch_py],
        cwd=CONFIG_DIR,
    )
    print("Shutdown, sleeping 20 seconds before restarting")
    time.sleep(20)
    sys.exit(return_code)


def main() -> None:
    check_supervisor_token()

    if not os.path.isdir(CONFIG_DIR):
        _error(
            "CONFIG_DIR does not exist: {} (no fallback)".format(CONFIG_DIR)
        )

    # Verify before any CONFIG_DIR mutation so a bad image never installs.
    manifest = verify_vendor()
    clean_config_dir(manifest)
    install_code(manifest)
    install_apps_yaml()
    write_predbat_manifest(manifest)
    launch()


if __name__ == "__main__":
    main()
