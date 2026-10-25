#!/usr/bin/env python3
"""
Unit tests for launch.py web UI defensive hardening.

Defensive hardening: mask secret-like and location fields in web UI/API
responses, restrict UI to ingress, disable raw apps.yaml editor/export
endpoints (apps.yaml is regenerated on every start).

Uses only the standard library. aiohttp-dependent tests skip if aiohttp is
missing. Requires Python 3.9+.
"""

from __future__ import annotations

import asyncio
import importlib.util
import io
import json
import os
import re
import shutil
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout

try:
    import aiohttp  # noqa: F401

    _AIOHTTP_AVAILABLE = True
except ImportError:
    _AIOHTTP_AVAILABLE = False

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LAUNCH_SRC = os.path.join(
    REPO_ROOT, "predbat", "rootfs", "opt", "predbat", "launch.py"
)


class WebHardeningTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp(prefix="predbat_web_hardening_")
        self.addCleanup(shutil.rmtree, self._tmpdir, ignore_errors=True)
        self._clean_modules()

    def tearDown(self) -> None:
        self._clean_modules()

    def _clean_modules(self) -> None:
        for name in ("utils", "components", "web"):
            sys.modules.pop(name, None)
        for name in list(sys.modules):
            if name.startswith("predbat_launch_"):
                sys.modules.pop(name, None)

    def _load_launch(self, module_name: str):
        for name in list(sys.modules):
            if name.startswith("predbat_launch_"):
                sys.modules.pop(name, None)
        spec = importlib.util.spec_from_file_location(module_name, LAUNCH_SRC)
        self.assertIsNotNone(spec)
        assert spec is not None and spec.loader is not None
        launch_mod = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = launch_mod
        spec.loader.exec_module(launch_mod)
        return launch_mod

    def _install_fake_utils(self, *, with_extra_names: bool = True) -> None:
        fake_dir = os.path.join(self._tmpdir, "fake_utils")
        os.makedirs(fake_dir, exist_ok=True)
        body = (
            "SECRET_KEY_EXTRA_NAMES = ()\n"
            "\n"
            "def is_secret_key(key, registry=True):\n"
            "    key_lower = str(key).lower()\n"
            "    if key_lower in SECRET_KEY_EXTRA_NAMES:\n"
            "        return True\n"
            "    return '_key' in key_lower\n"
        )
        if not with_extra_names:
            body = (
                "def is_secret_key(key, registry=True):\n"
                "    return '_key' in str(key).lower()\n"
            )
        with open(os.path.join(fake_dir, "utils.py"), "w", encoding="utf-8") as handle:
            handle.write(body)
        if fake_dir not in sys.path:
            sys.path.insert(0, fake_dir)
            self.addCleanup(
                lambda: sys.path.remove(fake_dir) if fake_dir in sys.path else None
            )
        sys.modules.pop("utils", None)

    def _install_fake_components_and_web(self) -> None:
        fake_dir = os.path.join(self._tmpdir, "fake_web_modules")
        os.makedirs(fake_dir, exist_ok=True)

        with open(os.path.join(fake_dir, "components.py"), "w", encoding="utf-8") as handle:
            handle.write(
                "COMPONENT_LIST = {\n"
                "    'ha': {\n"
                "        'args': {\n"
                "            'ha_key': {\n"
                "                'secret': True,\n"
                "                'config': 'ha_key',\n"
                "                'default': 'tok-AAA',\n"
                "            },\n"
                "            'solcast_api_key': {\n"
                "                'config': 'solcast_api_key',\n"
                "                'default': 'tok-BBB',\n"
                "            },\n"
                "            'some_token': {\n"
                "                'config': 'some_token',\n"
                "                'default': 'tok-CCC',\n"
                "            },\n"
                "            'user_password': {\n"
                "                'config': 'user_password',\n"
                "                'default': 'tok-DDD',\n"
                "            },\n"
                "            'api_key': {\n"
                "                'config': 'api_key',\n"
                "                'default': 'tok-EEE',\n"
                "            },\n"
                "            'latitude': {\n"
                "                'config': 'latitude',\n"
                "                'default': 0.111111,\n"
                "            },\n"
                "            'longitude': {\n"
                "                'config': 'longitude',\n"
                "                'default': 0.222222,\n"
                "            },\n"
                "            'ha_url': {\n"
                "                'config': 'ha_url',\n"
                "                'default': 'http://supervisor/core',\n"
                "            },\n"
                "        },\n"
                "    },\n"
                "}\n"
            )

        with open(os.path.join(fake_dir, "web.py"), "w", encoding="utf-8") as handle:
            handle.write(
                "import json\n"
                "from types import SimpleNamespace\n"
                "\n"
                "class _Resp:\n"
                "    def __init__(self, body, status=200, content_type='application/json'):\n"
                "        self.body = body\n"
                "        self.status = status\n"
                "        self.content_type = content_type\n"
                "\n"
                "def json_response(data, status=200):\n"
                "    return _Resp(json.dumps(data).encode('utf-8'), status=status)\n"
                "\n"
                "web = SimpleNamespace(json_response=json_response)\n"
                "\n"
                "class WebInterface:\n"
                "    async def html_component_config(self, request):\n"
                "        return json_response({\n"
                "            'success': True,\n"
                "            'args': [\n"
                "                {'config_key': 'ha_key', 'default': 'tok-AAA',"
                " 'current_value': 'tok-AAA'},\n"
                "                {'config_key': 'solcast_api_key', 'default': 'tok-BBB',"
                " 'current_value': 'tok-BBB'},\n"
                "                {'config_key': 'some_token', 'default': 'tok-CCC',"
                " 'current_value': 'tok-CCC'},\n"
                "                {'config_key': 'user_password', 'default': 'tok-DDD',"
                " 'current_value': 'tok-DDD'},\n"
                "                {'config_key': 'api_key', 'default': 'tok-EEE',"
                " 'current_value': 'tok-EEE'},\n"
                "                {'config_key': 'latitude', 'default': 0.111111,"
                " 'current_value': 0.111111},\n"
                "                {'config_key': 'longitude', 'default': 0.222222,"
                " 'current_value': 0.222222},\n"
                "                {'config_key': 'temperature_latitude', 'default': 0.333333,"
                " 'current_value': 0.333333},\n"
                "                {'config_key': 'ha_url',"
                " 'default': 'http://supervisor/core', 'current_value': None},\n"
                "            ],\n"
                "        })\n"
            )

        if fake_dir not in sys.path:
            sys.path.insert(0, fake_dir)
            self.addCleanup(
                lambda: sys.path.remove(fake_dir) if fake_dir in sys.path else None
            )
        for name in ("components", "web", "utils"):
            sys.modules.pop(name, None)

    def test_mask_secret_like_and_location_fields(self) -> None:
        self._install_fake_utils(with_extra_names=True)
        self._install_fake_components_and_web()
        launch_mod = self._load_launch("predbat_launch_mask")

        launch_mod.extend_secret_names()
        launch_mod.mask_sensitive_response_fields()

        import utils as utils_mod  # type: ignore
        import web as web_mod  # type: ignore

        self.assertIn("latitude", utils_mod.SECRET_KEY_EXTRA_NAMES)
        self.assertIn("longitude", utils_mod.SECRET_KEY_EXTRA_NAMES)

        async def _call():
            return await web_mod.WebInterface.html_component_config(
                web_mod.WebInterface(), None
            )

        resp = asyncio.run(_call())
        body = resp.body.decode("utf-8") if isinstance(resp.body, bytes) else resp.body
        for needle in (
            "0.333333",
            "tok-AAA",
            "tok-BBB",
            "tok-CCC",
            "tok-DDD",
            "tok-EEE",
            "0.111111",
            "0.222222",
        ):
            self.assertNotIn(needle, body)
        self.assertIn("***configured***", body)
        data = json.loads(body)
        ha_url = next(
            entry for entry in data["args"] if entry["config_key"] == "ha_url"
        )
        self.assertEqual(ha_url["default"], "http://supervisor/core")

    def test_extend_secret_names_fails_closed_when_missing(self) -> None:
        self._install_fake_utils(with_extra_names=False)
        launch_mod = self._load_launch("predbat_launch_extend_missing")
        with self.assertRaises(SystemExit) as raised:
            launch_mod.extend_secret_names()
        self.assertEqual(raised.exception.code, 1)

    @unittest.skipUnless(_AIOHTTP_AVAILABLE, "aiohttp not installed")
    def test_restrict_remote_allowlist(self) -> None:
        import aiohttp.web as aiohttp_web

        launch_mod = self._load_launch("predbat_launch_restrict")
        fake_web = types.ModuleType("web")
        fake_web.web = aiohttp_web
        sys.modules["web"] = fake_web

        buf = io.StringIO()
        with redirect_stdout(buf):
            launch_mod.restrict_web_to_ingress()

        self.assertIn(
            "Predbat web UI restricted to ingress (172.30.32.2) in kamien5 fork",
            buf.getvalue(),
        )

        app = fake_web.web.Application()
        middleware = app.middlewares[0]

        async def ok_handler(_request):
            return aiohttp_web.Response(text="ok")

        async def _check():
            results = {}
            for remote in ("10.0.0.5", "192.168.1.20", "172.30.32.2", "127.0.0.1"):
                results[remote] = await middleware(
                    types.SimpleNamespace(remote=remote, path="/"),
                    ok_handler,
                )
            return results

        results = asyncio.run(_check())
        self.assertEqual(results["10.0.0.5"].status, 403)
        self.assertEqual(results["192.168.1.20"].status, 403)
        self.assertEqual(results["172.30.32.2"].status, 200)
        self.assertEqual(results["127.0.0.1"].status, 200)

    @unittest.skipUnless(_AIOHTTP_AVAILABLE, "aiohttp not installed")
    def test_blocked_paths_forbidden_from_ingress(self) -> None:
        import aiohttp.web as aiohttp_web

        launch_mod = self._load_launch("predbat_launch_blocked")
        fake_web = types.ModuleType("web")
        fake_web.web = aiohttp_web
        sys.modules["web"] = fake_web

        launch_mod.restrict_web_to_ingress()
        app = fake_web.web.Application()
        middleware = app.middlewares[0]

        async def ok_handler(_request):
            return aiohttp_web.Response(text="ok")

        async def _check():
            out = []
            for path in sorted(launch_mod.BLOCKED_PATHS):
                resp = await middleware(
                    types.SimpleNamespace(remote="172.30.32.2", path=path),
                    ok_handler,
                )
                body = resp.body or b""
                if isinstance(body, bytes):
                    body = body.decode("utf-8")
                out.append((path, resp.status, body))
            return out

        for path, status, body in asyncio.run(_check()):
            self.assertEqual(status, 403, msg=path)
            self.assertIn("Disabled in kamien5 fork", body)

    @unittest.skipUnless(_AIOHTTP_AVAILABLE, "aiohttp not installed")
    def test_admin_endpoints_forbidden(self) -> None:
        import aiohttp.web as aiohttp_web

        launch_mod = self._load_launch("predbat_launch_admin")
        fake_web = types.ModuleType("web")
        fake_web.web = aiohttp_web
        sys.modules["web"] = fake_web
        with redirect_stdout(io.StringIO()):
            launch_mod.restrict_web_to_ingress()
        middleware = fake_web.web.Application().middlewares[0]

        async def ok_handler(_request):
            return aiohttp_web.Response(text="ok")

        async def status(method, path, remote="172.30.32.2"):
            resp = await middleware(
                types.SimpleNamespace(remote=remote, path=path, method=method),
                ok_handler,
            )
            return resp.status

        blocked = [
            ("POST", "/component_config_save"),
            ("POST", "/component_restart"),
            ("POST", "/apps"),
            ("POST", "/apps/"),
            ("GET", "/download"),
            ("GET", "/download/"),
            ("HEAD", "/download"),
            ("GET", "/browse"),
            ("GET", "/internals"),
            ("GET", "/api/internals"),
            ("GET", "/api/internals/download"),
        ]
        allowed = [("GET", "/apps"), ("GET", "/"), ("GET", "/component_config")]

        async def _check():
            res = {}
            for method, path in blocked + allowed:
                res[(method, path)] = await status(method, path)
                res[("loopback", method, path)] = await status(method, path, "127.0.0.1")
            return res

        res = asyncio.run(_check())
        for method, path in blocked:
            self.assertEqual(res[(method, path)], 403, msg=(method, path))
            self.assertEqual(res[("loopback", method, path)], 403, msg=(method, path))
        for method, path in allowed:
            self.assertEqual(res[(method, path)], 200, msg=(method, path))

    def test_blocked_request_helper(self) -> None:
        launch_mod = self._load_launch("predbat_launch_helper")
        self.assertTrue(launch_mod.is_blocked_request("post", "/apps"))
        self.assertFalse(launch_mod.is_blocked_request("GET", "/apps"))
        self.assertTrue(launch_mod.is_blocked_request("GET", "/api/internals/download/"))
        self.assertFalse(launch_mod.is_blocked_request("GET", "/"))

    def _write_apps_yaml(self, body: str) -> str:
        path = os.path.join(self._tmpdir, "apps.yaml")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("pred_bat:\n  module: predbat\n" + body)
        return path

    def test_unsupported_option_enabled_exits(self) -> None:
        launch_mod = self._load_launch("predbat_launch_options")
        for value in ("true", "True", "yes", "on", "1", "'true'", "\"yes\"", "maybe"):
            path = self._write_apps_yaml("  mcp_enable: {}  # c\n".format(value))
            with redirect_stdout(io.StringIO()) as buf:
                with self.assertRaises(SystemExit) as ctx:
                    launch_mod.refuse_unsupported_options(path)
            self.assertEqual(ctx.exception.code, 1, msg=value)
            self.assertIn("not supported", buf.getvalue())

    def test_unsupported_option_absent_or_false_passes(self) -> None:
        launch_mod = self._load_launch("predbat_launch_options_ok")
        bodies = ["", "  mcp_enable: false\n", "  mcp_enable: False # off\n",
                  "  mcp_enable: no\n", "  # mcp_enable: true\n"]
        for body in bodies:
            path = self._write_apps_yaml(body)
            launch_mod.refuse_unsupported_options(path)
        launch_mod.refuse_unsupported_options(os.path.join(self._tmpdir, "missing.yaml"))

    def test_shipped_apps_yaml_passes_option_check(self) -> None:
        launch_mod = self._load_launch("predbat_launch_options_shipped")
        launch_mod.refuse_unsupported_options(
            os.path.join(REPO_ROOT, "predbat", "rootfs", "apps.yaml")
        )

    @unittest.skipUnless(_AIOHTTP_AVAILABLE, "aiohttp not installed")
    def test_extra_listener_modules_get_access_policy(self) -> None:
        import aiohttp.web as aiohttp_web

        launch_mod = self._load_launch("predbat_launch_listeners")
        fake_web = types.ModuleType("web")
        fake_web.web = aiohttp_web
        sys.modules["web"] = fake_web
        extra = types.ModuleType("web_mcp")
        extra.web = aiohttp_web
        sys.modules["web_mcp"] = extra
        self.addCleanup(lambda: sys.modules.pop("web_mcp", None))

        with redirect_stdout(io.StringIO()):
            launch_mod.restrict_web_to_ingress()
        self.assertIs(extra.web, fake_web.web)
        middleware = extra.web.Application().middlewares[0]

        async def ok_handler(_request):
            return aiohttp_web.Response(text="ok")

        async def _check():
            outside = await middleware(
                types.SimpleNamespace(remote="10.0.0.5", path="/", method="GET"), ok_handler
            )
            ingress = await middleware(
                types.SimpleNamespace(remote="172.30.32.2", path="/", method="GET"), ok_handler
            )
            return outside.status, ingress.status

        self.assertEqual(asyncio.run(_check()), (403, 200))

    def _run_main_with_apps_yaml(self, body: str, module_name: str):
        """Run launch.main() against a temp CONFIG_DIR with stubbed patch steps."""
        config_dir = os.path.join(self._tmpdir, "config_" + module_name)
        os.makedirs(config_dir)
        with open(os.path.join(config_dir, "apps.yaml"), "w", encoding="utf-8") as handle:
            handle.write("pred_bat:\n  module: predbat\n" + body)
        marker = os.path.join(config_dir, "hass_started")
        with open(os.path.join(config_dir, "hass.py"), "w", encoding="utf-8") as handle:
            handle.write("open({!r}, 'w').close()\n".format(marker))

        launch_mod = self._load_launch(module_name)
        launch_mod.CONFIG_DIR = config_dir
        calls = []
        real_refuse = launch_mod.refuse_unsupported_options

        def recording_refuse(path):
            calls.append(("refuse", path))
            return real_refuse(path)

        launch_mod.refuse_unsupported_options = recording_refuse
        for name in (
            "block_self_update",
            "extend_secret_names",
            "mask_sensitive_response_fields",
            "restrict_web_to_ingress",
        ):
            setattr(launch_mod, name, (lambda n: lambda: calls.append((n, None)))(name))

        old_cwd, old_path, old_argv = os.getcwd(), list(sys.path), list(sys.argv)

        def restore():
            os.chdir(old_cwd)
            sys.path[:] = old_path
            sys.argv[:] = old_argv

        self.addCleanup(restore)
        exit_code = None
        with redirect_stdout(io.StringIO()) as buf:
            try:
                launch_mod.main()
            except SystemExit as exc:
                exit_code = exc.code
        restore()
        return exit_code, calls, os.path.exists(marker), buf.getvalue(), config_dir

    def test_main_refuses_unsupported_option_before_start(self) -> None:
        code, calls, started, out, config_dir = self._run_main_with_apps_yaml(
            "  mcp_enable: true\n", "predbat_launch_main_refuse"
        )
        self.assertEqual(code, 1)
        self.assertFalse(started)
        self.assertIn("not supported", out)
        self.assertEqual(calls, [("refuse", os.path.join(config_dir, "apps.yaml"))])

    def test_main_checks_options_first_then_starts(self) -> None:
        code, calls, started, _out, config_dir = self._run_main_with_apps_yaml(
            "  mcp_enable: false\n", "predbat_launch_main_ok"
        )
        self.assertIsNone(code)
        self.assertTrue(started)
        self.assertEqual(calls[0], ("refuse", os.path.join(config_dir, "apps.yaml")))
        self.assertEqual(
            [name for name, _ in calls[1:]],
            [
                "block_self_update",
                "extend_secret_names",
                "mask_sensitive_response_fields",
                "restrict_web_to_ingress",
            ],
        )

    def test_restricted_paths_exist_in_vendor_routes(self) -> None:
        launch_mod = self._load_launch("predbat_launch_routes")
        with open(os.path.join(REPO_ROOT, "predbat", "vendor", "web.py"), "r", encoding="utf-8") as handle:
            source = handle.read()
        routes = set()
        for method, path in re.findall(
            r"router\.add_(get|post|put|delete|patch|route)\(\s*[\"']([^\"']+)[\"']", source
        ):
            routes.add((method.upper(), path))
        paths = {path for _method, path in routes}
        self.assertIn("/", paths)
        for path in sorted(launch_mod.BLOCKED_PATHS):
            self.assertIn(path, paths, msg="restricted path is not a vendor route: " + path)
        for method, path in sorted(launch_mod.BLOCKED_METHOD_PATHS):
            self.assertIn((method, path), routes, msg="restricted route missing: {} {}".format(method, path))


if __name__ == "__main__":
    unittest.main()
