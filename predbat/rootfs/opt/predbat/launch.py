#!/usr/bin/env python3
"""
Launch Predbat with self-update disabled (kamien5 fork).

Runs from the image (/opt/predbat/launch.py). Working directory and sys.path
use CONFIG_DIR so hass.py and the freshly installed download.py are used.
block_self_update() must run before predbat is imported so that
`from download import predbat_update_download, ...` binds the stubs.

Defensive hardening: mask secret-like and location fields in web UI/API
responses, restrict UI to ingress, disable raw apps.yaml editor/export
endpoints (apps.yaml is regenerated on every start). Patches run before
importing web/predbat/components via hass.py.
"""

from __future__ import annotations

import functools
import importlib
import json
import os
import re
import runpy
import sys
import types

CONFIG_DIR = os.environ.get("PREDBAT_CONFIG_DIR", "/config")

DISABLED_MESSAGE = (
    "Predbat self-update is disabled in the kamien5 fork "
    "(pinned v9.5.0); ignoring request"
)

# HA ingress proxy (Supervisor) plus local loopback for health checks.
ALLOWED_REMOTES = {"172.30.32.2", "127.0.0.1", "::1"}

# Paths disabled for all remotes (apps.yaml is regenerated on every start).
BLOCKED_PATHS = {
    "/apps_editor",
    "/apps_editor_checksum",
    "/debug_apps",
    "/debug_apps_live",
    "/apps_value",
    # Admin endpoints: configuration is owned by the add-on, not the UI.
    "/component_config_save",
    "/component_restart",
    "/download",
    "/browse",
    "/internals",
    "/api/internals",
    "/api/internals/download",
    "/api/kraken_key",
}

# Path prefixes disabled for all remotes and methods: the prefix itself and
# everything below it ("/chat" and "/chat/...", but not "/chatter").
BLOCKED_PREFIXES = ("/chat",)

# (method, path) pairs disabled for all remotes; other methods stay available.
BLOCKED_METHOD_PATHS = {
    ("POST", "/apps"),
}


def _normalize_path(path: str) -> str:
    path = path or "/"
    if len(path) > 1:
        path = path.rstrip("/") or "/"
    return path


def is_blocked_request(method: str, path: str) -> bool:
    norm = _normalize_path(path)
    if norm in BLOCKED_PATHS:
        return True
    for prefix in BLOCKED_PREFIXES:
        if norm == prefix or norm.startswith(prefix + "/"):
            return True
    return ((method or "GET").upper(), norm) in BLOCKED_METHOD_PATHS

# Vendor modules that open an additional aiohttp listener.
EXTRA_LISTENER_MODULES = ("web_mcp",)

# apps.yaml options that must stay off in this fork (each opens an extra listener).
FORBIDDEN_ENABLED_OPTIONS = ("mcp_enable",)

_FALSE_VALUES = {"", "false", "no", "off", "0", "null", "~"}

SECRET_MASK = "***configured***"

_SECRET_SUBSTRINGS = ("_key", "token", "password", "secret", "latitude", "longitude")

# Location key names treated like credentials by Predbat's own masking/redaction.
LOCATION_KEYS = ("latitude", "longitude", "temperature_latitude", "temperature_longitude")


def block_self_update() -> None:
    """
    Replace download module update helpers with no-op stubs.

    Import download from CONFIG_DIR (caller must put it on sys.path first).
    Stubs return the same failure/skip values as a failed network update so
    PredBat.download_predbat_version and import-time check_install paths
    cannot pull or install remote code.
    """
    # Late import: CONFIG_DIR must already be on sys.path (see main()).
    import download

    def predbat_update_download(*_args, **_kwargs):
        print(DISABLED_MESSAGE)
        return None

    def predbat_update_move(*_args, **_kwargs):
        print(DISABLED_MESSAGE)
        return False

    def get_github_directory_listing(*_args, **_kwargs):
        print(DISABLED_MESSAGE)
        return None

    download.predbat_update_download = predbat_update_download
    download.predbat_update_move = predbat_update_move
    download.get_github_directory_listing = get_github_directory_listing


def extend_secret_names() -> None:
    """
    Extend utils.SECRET_KEY_EXTRA_NAMES with location field names.

    Consulted by utils.is_secret_key() at call time. Fail closed if the
    attribute is missing.
    """
    # Late import: CONFIG_DIR must already be on sys.path (see main()).
    import utils

    if not hasattr(utils, "SECRET_KEY_EXTRA_NAMES"):
        print("Error: utils.SECRET_KEY_EXTRA_NAMES is missing")
        sys.exit(1)
    old = utils.SECRET_KEY_EXTRA_NAMES
    utils.SECRET_KEY_EXTRA_NAMES = tuple(old) + LOCATION_KEYS


def _should_mask_config_key(config_key, secret_keys, utils_mod) -> bool:
    if config_key in secret_keys:
        return True
    try:
        if utils_mod.is_secret_key(config_key):
            return True
    except Exception:
        return True
    if config_key in ("latitude", "longitude"):
        return True
    key_lower = str(config_key).lower()
    if key_lower == "api_key":
        return True
    for needle in _SECRET_SUBSTRINGS:
        if needle in key_lower:
            return True
    return False


def mask_sensitive_response_fields() -> None:
    """
    Defensive hardening: mask secret-like and location fields in web UI/API
    responses.

    Wraps the component-config handler so non-empty default/current_value
    fields that look secret or location-related are replaced with
    ***configured***. Fail closed on parse/mask errors.
    """
    # Late import: CONFIG_DIR must already be on sys.path (see main()).
    import components
    import utils
    import web

    secret_keys = set()
    for component_info in components.COMPONENT_LIST.values():
        args = component_info.get("args", {})
        if not isinstance(args, dict):
            continue
        for arg_info in args.values():
            if isinstance(arg_info, dict) and arg_info.get("secret"):
                config = arg_info.get("config")
                if config:
                    secret_keys.add(config)

    original = web.WebInterface.html_component_config

    @functools.wraps(original)
    async def html_component_config(self, request):
        resp = await original(self, request)
        try:
            if getattr(resp, "content_type", None) != "application/json":
                return resp
            body = resp.body
            if isinstance(body, bytes):
                data = json.loads(body.decode("utf-8"))
            else:
                data = json.loads(body)
            for entry in data.get("args", []):
                config_key = entry.get("config_key")
                if not _should_mask_config_key(config_key, secret_keys, utils):
                    continue
                for field in ("default", "current_value"):
                    value = entry.get(field)
                    if value is not None and value != "":
                        entry[field] = SECRET_MASK
            return web.web.json_response(data, status=resp.status)
        except Exception:
            return web.web.json_response(
                {"success": False, "message": "masked"}, status=500
            )

    web.WebInterface.html_component_config = html_component_config


def restrict_web_to_ingress() -> None:
    """
    Defensive hardening: restrict UI to ingress, disable raw apps.yaml
    editor/export endpoints (apps.yaml is regenerated on every start).

    Replace web.web (aiohttp.web) with a ModuleType shim whose Application
    factory prepends middleware without editing vendor code.
    """
    import aiohttp.web as aiohttp_web
    import web

    allowed = set(ALLOWED_REMOTES)
    extra = os.environ.get("PREDBAT_WEB_ALLOWED_REMOTES", "")
    for part in extra.split(","):
        remote = part.strip()
        if remote:
            allowed.add(remote)

    @aiohttp_web.middleware
    async def ingress_only(request, handler):
        if is_blocked_request(getattr(request, "method", "GET"), request.path):
            return aiohttp_web.Response(
                text="Disabled in kamien5 fork", status=403
            )
        if request.remote not in allowed:
            return aiohttp_web.Response(text="Forbidden", status=403)
        return await handler(request)

    shim = types.ModuleType("aiohttp.web")
    shim.__dict__.update(aiohttp_web.__dict__)
    real_application = aiohttp_web.Application

    def Application(*args, **kwargs):
        middlewares = list(kwargs.get("middlewares") or ())
        middlewares.insert(0, ingress_only)
        kwargs["middlewares"] = middlewares
        return real_application(*args, **kwargs)

    shim.Application = Application
    web.web = shim
    # Every module that starts its own aiohttp listener gets the same policy.
    for name in EXTRA_LISTENER_MODULES:
        try:
            mod = importlib.import_module(name)
        except ImportError:
            continue
        if hasattr(mod, "web"):
            mod.web = shim
    print(
        "Predbat web UI restricted to ingress (172.30.32.2) in kamien5 fork"
    )


def refuse_unsupported_options(apps_yaml_path: str) -> None:
    """
    Exit 1 if apps.yaml enables an option this fork does not support.

    Line-based check (stdlib only); any value other than an explicit false
    is treated as enabled, so unknown spellings fail closed.
    """
    try:
        with open(apps_yaml_path, "r", encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    except FileNotFoundError:
        return
    for option in FORBIDDEN_ENABLED_OPTIONS:
        pattern = re.compile(r"^\s*['\"]?" + re.escape(option) + r"['\"]?\s*:(.*)$")
        for line in lines:
            match = pattern.match(line)
            if not match:
                continue
            value = match.group(1).split("#", 1)[0].strip().strip("'\"").lower()
            if value not in _FALSE_VALUES:
                print(
                    "Error: apps.yaml option {} is not supported in the kamien5 fork".format(
                        option
                    )
                )
                sys.exit(1)


def main() -> None:
    if not os.path.isdir(CONFIG_DIR):
        print("Error: CONFIG_DIR does not exist: {}".format(CONFIG_DIR))
        sys.exit(1)

    os.chdir(CONFIG_DIR)
    # Prefer CONFIG_DIR modules over anything else on the path.
    sys.path.insert(0, CONFIG_DIR)

    refuse_unsupported_options(os.path.join(CONFIG_DIR, "apps.yaml"))
    block_self_update()
    extend_secret_names()
    mask_sensitive_response_fields()
    restrict_web_to_ingress()

    hass_path = os.path.join(CONFIG_DIR, "hass.py")
    if not os.path.isfile(hass_path):
        print("Error: hass.py not found in {}".format(CONFIG_DIR))
        sys.exit(1)

    # Mimic `python hass.py` without putting secrets on argv.
    sys.argv = [hass_path]
    runpy.run_path(hass_path, run_name="__main__")


if __name__ == "__main__":
    main()
