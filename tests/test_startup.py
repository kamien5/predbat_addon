#!/usr/bin/env python3
"""
Unit tests for the kamien5 Predbat add-on startup hardening.

Run from the repository root:
  python3 -m unittest discover -s tests -v

Uses only the standard library. Requires Python 3.9+.
"""

from __future__ import annotations

import hashlib
import http.server
import importlib.util
import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from typing import Dict, List, Optional, Tuple

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STARTUP_PY = os.path.join(REPO_ROOT, "predbat", "rootfs", "startup.py")
RUN_SH = os.path.join(REPO_ROOT, "predbat", "rootfs", "run.sh")
VENDOR_SRC = os.path.join(REPO_ROOT, "predbat", "vendor")
MANIFEST_SRC = os.path.join(REPO_ROOT, "predbat", "MANIFEST.sha256")
APPS_YAML_SRC = os.path.join(REPO_ROOT, "predbat", "rootfs", "apps.yaml")
LAUNCH_SRC = os.path.join(
    REPO_ROOT, "predbat", "rootfs", "opt", "predbat", "launch.py"
)

EXPECTED_FILE_COUNT = 114
APPS_YAML_SHA256 = (
    "bc4b790e3a8f63230f6ce3e4b680a9cab51d4f6212cc6072dae3f2862da3f1ee"
)
HA_TEST_LAT = 0.123456
HA_TEST_LON = 0.654321
DEFAULT_TEST_TOKEN = "test-token"


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def load_manifest_names(path: str) -> Dict[str, str]:
    mapping = {}
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.rstrip("\n")
            digest, name = line.split("  ", 1)
            mapping[name] = digest
    return mapping


def parse_manifest_yaml_entry(text: str, filename: str) -> Tuple[int, str]:
    """Extract size and sha for one file from our hand-written manifest.yaml."""
    pattern = re.compile(
        r'- name: "{}"\n  size: (\d+)\n  sha: "([0-9a-f]{{40}})"\n  type: "file"'.format(
            re.escape(filename)
        ),
        re.MULTILINE,
    )
    match = pattern.search(text)
    if not match:
        raise AssertionError("manifest.yaml missing entry for {}".format(filename))
    return int(match.group(1)), match.group(2)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class _MockHaApiServer(http.server.HTTPServer):
    def __init__(self, server_address, handler_class):
        super().__init__(server_address, handler_class)
        self.expected_token = DEFAULT_TEST_TOKEN
        self.force_status = None  # type: Optional[int]
        self.latitude = HA_TEST_LAT
        self.longitude = HA_TEST_LON
        self.recorded_headers = []  # type: List[Dict[str, str]]


class _MockHaConfigHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A003 - stdlib signature
        return

    def do_GET(self) -> None:
        headers = {key: value for key, value in self.headers.items()}
        self.server.recorded_headers.append(headers)

        if self.path != "/config":
            self.send_response(404)
            self.end_headers()
            return

        auth = self.headers.get("Authorization", "")
        expected = "Bearer " + self.server.expected_token
        if self.server.force_status is not None:
            status = self.server.force_status
        elif auth != expected:
            status = 401
        else:
            status = 200

        if status != 200:
            self.send_response(status)
            self.end_headers()
            return

        payload = {
            "latitude": self.server.latitude,
            "longitude": self.server.longitude,
            "location_name": "Home",
            "unit_system": {"length": "km"},
        }
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class StartupTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp(prefix="predbat_startup_test_")
        self.addCleanup(shutil.rmtree, self._tmpdir, ignore_errors=True)

        port = _free_port()
        self._ha_server = _MockHaApiServer(
            ("127.0.0.1", port), _MockHaConfigHandler
        )
        self._ha_api_url = "http://127.0.0.1:{}".format(port)
        thread = threading.Thread(target=self._ha_server.serve_forever, daemon=True)
        thread.start()
        # Cleanups run in reverse order: shutdown() first, then server_close().
        self.addCleanup(self._ha_server.server_close)
        self.addCleanup(self._ha_server.shutdown)

        self._options_json = os.path.join(self._tmpdir, "options.json")
        with open(self._options_json, "w", encoding="utf-8") as handle:
            json.dump({}, handle)

    def _write_options(self, options: Optional[dict] = None, *, missing: bool = False) -> str:
        path = self._options_json
        if missing:
            if os.path.exists(path):
                os.unlink(path)
            return path
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({} if options is None else options, handle)
        return path

    def _make_image_dir(self, name: str = "image") -> str:
        image_dir = os.path.join(self._tmpdir, name)
        os.makedirs(image_dir)
        shutil.copytree(VENDOR_SRC, os.path.join(image_dir, "vendor"))
        shutil.copy2(MANIFEST_SRC, os.path.join(image_dir, "MANIFEST.sha256"))
        shutil.copy2(LAUNCH_SRC, os.path.join(image_dir, "launch.py"))
        return image_dir

    def _make_config_dir(self, name: str = "config") -> str:
        config_dir = os.path.join(self._tmpdir, name)
        os.makedirs(config_dir)
        return config_dir

    def _run_startup(
        self,
        config_dir: str,
        image_dir: str,
        *,
        test_mode: bool = True,
        skip_launch: bool = True,
        supervisor_token: Optional[str] = DEFAULT_TEST_TOKEN,
        extra_env: Optional[Dict[str, str]] = None,
    ) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        # Drop host tokens so tests control presence explicitly.
        env.pop("SUPERVISOR_TOKEN", None)
        env.pop("PREDBAT_TEST_MODE", None)
        env.pop("PREDBAT_SKIP_LAUNCH", None)
        env.pop("PREDBAT_APPS_YAML_SRC", None)
        env.pop("PREDBAT_HA_API_URL", None)
        env.pop("PREDBAT_RETRY_SLEEP", None)
        env.pop("PREDBAT_OPTIONS_JSON", None)

        env["PREDBAT_CONFIG_DIR"] = config_dir
        env["PREDBAT_IMAGE_DIR"] = image_dir
        env["PREDBAT_APPS_YAML_SRC"] = APPS_YAML_SRC
        env["PREDBAT_HA_API_URL"] = self._ha_api_url
        env["PREDBAT_RETRY_SLEEP"] = "0"
        env["PREDBAT_OPTIONS_JSON"] = self._options_json
        if skip_launch:
            env["PREDBAT_SKIP_LAUNCH"] = "1"
        if test_mode:
            env["PREDBAT_TEST_MODE"] = "1"
        if supervisor_token is not None:
            env["SUPERVISOR_TOKEN"] = supervisor_token
            self._ha_server.expected_token = supervisor_token
        else:
            self._ha_server.expected_token = DEFAULT_TEST_TOKEN
        if extra_env:
            env.update(extra_env)

        return subprocess.run(
            [sys.executable, STARTUP_PY],
            capture_output=True,
            text=True,
            env=env,
            cwd=REPO_ROOT,
        )

    def _load_startup_module(self, module_name: str = "predbat_startup_under_test"):
        sys.modules.pop(module_name, None)
        spec = importlib.util.spec_from_file_location(module_name, STARTUP_PY)
        self.assertIsNotNone(spec)
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = mod
        spec.loader.exec_module(mod)
        self.addCleanup(lambda: sys.modules.pop(module_name, None))
        return mod

    def _expected_apps_yaml(self, notify_device: str = "") -> str:
        """Expected apps.yaml built independently of startup.render_apps_yaml."""
        self.assertEqual(str(HA_TEST_LAT), "0.123456")
        self.assertEqual(str(HA_TEST_LON), "0.654321")
        with open(APPS_YAML_SRC, "r", encoding="utf-8") as handle:
            text = handle.read()
        self.assertEqual(text.count("__HA_LATITUDE__"), 2)
        self.assertEqual(text.count("__HA_LONGITUDE__"), 2)
        self.assertEqual(text.count("[__HA_NOTIFY_DEVICE__]"), 1)
        devices = "[{}]".format(notify_device) if notify_device else "[]"
        expected = (
            text.replace("__HA_LATITUDE__", "0.123456")
            .replace("__HA_LONGITUDE__", "0.654321")
            .replace("[__HA_NOTIFY_DEVICE__]", devices)
        )
        self.assertNotIn("__HA_", expected)
        self.assertEqual(expected.count("latitude: 0.123456"), 2)
        self.assertEqual(expected.count("longitude: 0.654321"), 2)
        self.assertIn("notify_devices: " + devices, expected)
        return expected

    def test_a_clean_start_installs_all_pinned_files(self) -> None:
        image_dir = self._make_image_dir()
        config_dir = self._make_config_dir()
        manifest = load_manifest_names(MANIFEST_SRC)
        self.assertEqual(len(manifest), EXPECTED_FILE_COUNT)

        result = self._run_startup(config_dir, image_dir)
        self.assertEqual(
            result.returncode,
            0,
            msg="stdout:\n{}\nstderr:\n{}".format(result.stdout, result.stderr),
        )

        for name, expected_hash in manifest.items():
            path = os.path.join(config_dir, name)
            self.assertTrue(os.path.isfile(path), msg="missing {}".format(name))
            self.assertEqual(sha256_file(path), expected_hash, msg=name)

        manifest_path = os.path.join(config_dir, "manifest.yaml")
        self.assertTrue(os.path.isfile(manifest_path))
        with open(manifest_path, "r", encoding="utf-8") as handle:
            yaml_text = handle.read()

        with open(os.path.join(config_dir, "predbat.py"), "rb") as handle:
            predbat_data = handle.read()
        size, sha = parse_manifest_yaml_entry(yaml_text, "predbat.py")
        self.assertEqual(size, len(predbat_data))
        self.assertEqual(sha, git_blob_sha1(predbat_data))

    def test_b_self_update_tamper_is_restored(self) -> None:
        image_dir = self._make_image_dir()
        config_dir = self._make_config_dir()
        first = self._run_startup(config_dir, image_dir)
        self.assertEqual(first.returncode, 0, msg=first.stdout + first.stderr)

        predbat_path = os.path.join(config_dir, "predbat.py")
        hass_path = os.path.join(config_dir, "hass.py")
        with open(predbat_path, "w", encoding="utf-8") as handle:
            handle.write("print('tampered')\n")
        with open(hass_path, "a", encoding="utf-8") as handle:
            handle.write("\n# tampered by test\n")

        second = self._run_startup(config_dir, image_dir)
        self.assertEqual(second.returncode, 0, msg=second.stdout + second.stderr)
        combined = second.stdout + second.stderr
        self.assertIn("restored: predbat.py", combined)

        vendor_predbat = os.path.join(image_dir, "vendor", "predbat.py")
        vendor_hass = os.path.join(image_dir, "vendor", "hass.py")
        with open(predbat_path, "rb") as handle:
            got_predbat = handle.read()
        with open(vendor_predbat, "rb") as handle:
            self.assertEqual(got_predbat, handle.read())
        with open(hass_path, "rb") as handle:
            got_hass = handle.read()
        with open(vendor_hass, "rb") as handle:
            self.assertEqual(got_hass, handle.read())

    def test_c_tampered_image_vendor_aborts_before_config_copy(self) -> None:
        image_dir = self._make_image_dir()
        config_dir = self._make_config_dir()
        target = os.path.join(image_dir, "vendor", "predbat.py")
        with open(target, "ab") as handle:
            handle.write(b"\n# image tamper\n")

        result = self._run_startup(config_dir, image_dir)
        self.assertEqual(result.returncode, 1)
        combined = result.stdout + result.stderr
        self.assertIn("pinned Predbat code failed verification", combined)
        self.assertIn("predbat.py", combined)
        self.assertEqual(os.listdir(config_dir), [])

    def test_d_extra_vendor_file_fails(self) -> None:
        image_dir = self._make_image_dir()
        config_dir = self._make_config_dir()
        extra = os.path.join(image_dir, "vendor", "extra_evil.py")
        with open(extra, "w", encoding="utf-8") as handle:
            handle.write("print('extra')\n")

        result = self._run_startup(config_dir, image_dir)
        self.assertEqual(result.returncode, 1)
        self.assertIn("pinned Predbat code failed verification", result.stdout + result.stderr)
        self.assertIn("extra_evil.py", result.stdout + result.stderr)

    def test_e_malformed_manifest_line_fails(self) -> None:
        image_dir = self._make_image_dir()
        config_dir = self._make_config_dir()
        manifest_path = os.path.join(image_dir, "MANIFEST.sha256")
        with open(manifest_path, "a", encoding="utf-8") as handle:
            handle.write("not-a-valid-manifest-line\n")

        result = self._run_startup(config_dir, image_dir)
        self.assertEqual(result.returncode, 1)
        self.assertIn("malformed", (result.stdout + result.stderr).lower())

    def test_f_cleans_code_artifacts_preserves_user_data(self) -> None:
        image_dir = self._make_image_dir()
        config_dir = self._make_config_dir()

        with open(os.path.join(config_dir, "evil_plugin.py"), "w", encoding="utf-8") as handle:
            handle.write("print('evil')\n")
        plugins = os.path.join(config_dir, "plugins")
        os.makedirs(plugins)
        with open(os.path.join(plugins, "x_plugin.py"), "w", encoding="utf-8") as handle:
            handle.write("print('plugin')\n")
        pkg = os.path.join(config_dir, "predbat")
        os.makedirs(pkg)
        with open(os.path.join(pkg, "__init__.py"), "w", encoding="utf-8") as handle:
            handle.write("# shadow package\n")
        pycache = os.path.join(config_dir, "__pycache__")
        os.makedirs(pycache)
        with open(
            os.path.join(pycache, "predbat.cpython-312.pyc"), "wb"
        ) as handle:
            handle.write(b"\0")
        with open(
            os.path.join(config_dir, "predbat.py.v9.9.9"), "w", encoding="utf-8"
        ) as handle:
            handle.write("# staged\n")

        with open(os.path.join(config_dir, "predbat.log"), "w", encoding="utf-8") as handle:
            handle.write("keep-log\n")
        with open(os.path.join(config_dir, "secrets.yaml"), "w", encoding="utf-8") as handle:
            handle.write("token: keep\n")
        save_dir = os.path.join(config_dir, "predbat_save")
        os.makedirs(save_dir)
        save_file = os.path.join(save_dir, "x.yaml")
        with open(save_file, "w", encoding="utf-8") as handle:
            handle.write("keep: true\n")

        result = self._run_startup(config_dir, image_dir)
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)

        self.assertFalse(os.path.exists(os.path.join(config_dir, "evil_plugin.py")))
        self.assertFalse(os.path.exists(plugins))
        self.assertFalse(os.path.exists(pkg))
        self.assertFalse(os.path.exists(pycache))
        self.assertFalse(os.path.exists(os.path.join(config_dir, "predbat.py.v9.9.9")))

        with open(os.path.join(config_dir, "predbat.log"), "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "keep-log\n")
        with open(os.path.join(config_dir, "secrets.yaml"), "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "token: keep\n")
        with open(save_file, "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "keep: true\n")

    def test_g_supervisor_token_required_and_never_logged(self) -> None:
        image_dir = self._make_image_dir()
        config_dir = self._make_config_dir()

        missing = self._run_startup(
            config_dir,
            image_dir,
            test_mode=False,
            supervisor_token=None,
        )
        self.assertEqual(missing.returncode, 1)
        self.assertIn("SUPERVISOR_TOKEN", missing.stdout + missing.stderr)

        secret = "sekret-test-123"
        present = self._run_startup(
            config_dir,
            image_dir,
            test_mode=True,
            supervisor_token=secret,
        )
        self.assertEqual(present.returncode, 0, msg=present.stdout + present.stderr)
        combined = present.stdout + present.stderr
        self.assertNotIn(secret, combined)
        self.assertIn("SUPERVISOR_TOKEN present (value not logged)", combined)

    def test_h_block_self_update_stubs(self) -> None:
        fake_dir = os.path.join(self._tmpdir, "fake_modules")
        os.makedirs(fake_dir)
        download_path = os.path.join(fake_dir, "download.py")
        with open(download_path, "w", encoding="utf-8") as handle:
            handle.write(
                "def predbat_update_download(*a, **k):\n"
                "    return 'real-download'\n"
                "def predbat_update_move(*a, **k):\n"
                "    return True\n"
                "def get_github_directory_listing(*a, **k):\n"
                "    return ['real-listing']\n"
            )

        spec = importlib.util.spec_from_file_location(
            "predbat_launch_under_test", LAUNCH_SRC
        )
        self.assertIsNotNone(spec)
        assert spec is not None and spec.loader is not None
        launch_mod = importlib.util.module_from_spec(spec)
        sys.modules["predbat_launch_under_test"] = launch_mod
        spec.loader.exec_module(launch_mod)

        sys.path.insert(0, fake_dir)
        self.addCleanup(
            lambda: sys.path.remove(fake_dir) if fake_dir in sys.path else None
        )
        sys.modules.pop("download", None)

        buf = io.StringIO()
        with redirect_stdout(buf):
            launch_mod.block_self_update()
            import download as download_mod  # type: ignore

            self.assertIsNone(download_mod.predbat_update_download())
            self.assertIs(download_mod.predbat_update_move(), False)
            self.assertIsNone(download_mod.get_github_directory_listing())

        output = buf.getvalue()
        self.assertIn("Predbat self-update is disabled in the kamien5 fork", output)
        self.assertEqual(output.count("ignoring request"), 3)

        sys.modules.pop("download", None)
        sys.modules.pop("predbat_launch_under_test", None)

    def test_i_apps_yaml_installed_with_ha_coordinates(self) -> None:
        self.assertEqual(sha256_file(APPS_YAML_SRC), APPS_YAML_SHA256)

        image_dir = self._make_image_dir()
        config_dir = self._make_config_dir()
        result = self._run_startup(config_dir, image_dir)
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)

        dest = os.path.join(config_dir, "apps.yaml")
        self.assertTrue(os.path.isfile(dest))
        with open(dest, "r", encoding="utf-8") as handle:
            installed = handle.read()
        self.assertEqual(installed, self._expected_apps_yaml())
        self.assertNotIn("__HA_", installed)
        self.assertIn("notify_devices: []", installed)

        self.assertTrue(self._ha_server.recorded_headers)
        auth = self._ha_server.recorded_headers[-1].get("Authorization", "")
        self.assertEqual(auth, "Bearer " + DEFAULT_TEST_TOKEN)

    def test_j_apps_yaml_local_edits_overwritten(self) -> None:
        image_dir = self._make_image_dir()
        config_dir = self._make_config_dir()
        dest = os.path.join(config_dir, "apps.yaml")
        with open(dest, "w", encoding="utf-8") as handle:
            handle.write("# locally edited apps.yaml\npred_bat: {}\n")

        result = self._run_startup(config_dir, image_dir)
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        with open(dest, "r", encoding="utf-8") as handle:
            installed = handle.read()
        self.assertEqual(installed, self._expected_apps_yaml())
        self.assertNotIn("locally edited", installed)

    def test_k_apps_yaml_source_tamper_fails(self) -> None:
        image_dir = self._make_image_dir()
        config_dir = self._make_config_dir()
        bad_src = os.path.join(self._tmpdir, "apps_tampered.yaml")
        shutil.copy2(APPS_YAML_SRC, bad_src)
        with open(bad_src, "rb") as handle:
            data = bytearray(handle.read())
        data[0] = (data[0] + 1) % 256
        with open(bad_src, "wb") as handle:
            handle.write(data)

        result = self._run_startup(
            config_dir,
            image_dir,
            extra_env={"PREDBAT_APPS_YAML_SRC": bad_src},
        )
        self.assertEqual(result.returncode, 1)
        combined = result.stdout + result.stderr
        self.assertIn("apps.yaml in image failed verification", combined)

    def test_l_ha_api_error_exits_without_logging_secrets(self) -> None:
        image_dir = self._make_image_dir()
        secret = "ha-secret-token-xyz"

        for status in (401, 500):
            config_dir = self._make_config_dir("config_ha_{}".format(status))
            self._ha_server.force_status = status
            self._ha_server.recorded_headers = []
            result = self._run_startup(
                config_dir,
                image_dir,
                supervisor_token=secret,
            )
            self.assertEqual(result.returncode, 1, msg="status {}".format(status))
            combined = result.stdout + result.stderr
            self.assertIn(
                "unable to read latitude/longitude from Home Assistant config",
                combined,
            )
            self.assertNotIn(secret, combined)
            self.assertNotIn(str(HA_TEST_LAT), combined)

        self._ha_server.force_status = None

    def test_m_success_output_hides_token_and_coordinates(self) -> None:
        image_dir = self._make_image_dir()
        config_dir = self._make_config_dir()
        secret = "success-token-abc"
        result = self._run_startup(
            config_dir,
            image_dir,
            supervisor_token=secret,
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        combined = result.stdout + result.stderr
        self.assertNotIn(secret, combined)
        self.assertNotIn(str(HA_TEST_LAT), combined)
        self.assertNotIn(str(HA_TEST_LON), combined)
        self.assertIn("Installed apps.yaml", combined)
        self.assertIn("coordinates from Home Assistant config", combined)
        self.assertIn("notify device not set", combined)

    def test_n_notify_device_from_options(self) -> None:
        device = "mobile_app_test_phone"
        self._write_options({"notify_device": device})
        image_dir = self._make_image_dir()
        config_dir = self._make_config_dir()
        result = self._run_startup(config_dir, image_dir)
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        combined = result.stdout + result.stderr
        self.assertNotIn(device, combined)
        self.assertIn("notify device set", combined)

        dest = os.path.join(config_dir, "apps.yaml")
        with open(dest, "r", encoding="utf-8") as handle:
            installed = handle.read()
        self.assertIn("notify_devices: [mobile_app_test_phone]", installed)
        self.assertEqual(installed, self._expected_apps_yaml(device))

    def test_o_notify_device_missing_or_empty(self) -> None:
        image_dir = self._make_image_dir()

        self._write_options(missing=True)
        config_missing = self._make_config_dir("config_opts_missing")
        result_missing = self._run_startup(config_missing, image_dir)
        self.assertEqual(
            result_missing.returncode,
            0,
            msg=result_missing.stdout + result_missing.stderr,
        )
        with open(
            os.path.join(config_missing, "apps.yaml"), "r", encoding="utf-8"
        ) as handle:
            self.assertIn("notify_devices: []", handle.read())

        self._write_options({"notify_device": ""})
        config_empty = self._make_config_dir("config_opts_empty")
        result_empty = self._run_startup(config_empty, image_dir)
        self.assertEqual(
            result_empty.returncode,
            0,
            msg=result_empty.stdout + result_empty.stderr,
        )
        with open(
            os.path.join(config_empty, "apps.yaml"), "r", encoding="utf-8"
        ) as handle:
            self.assertIn("notify_devices: []", handle.read())

    def test_p_notify_device_invalid_rejected(self) -> None:
        image_dir = self._make_image_dir()
        invalids = ("a: b", "x]\n  evil: 1", "Upper", "a-b")
        for bad in invalids:
            self._write_options({"notify_device": bad})
            config_dir = self._make_config_dir(
                "config_bad_{}".format(abs(hash(bad)) % 10**8)
            )
            result = self._run_startup(config_dir, image_dir)
            self.assertEqual(result.returncode, 1, msg=repr(bad))
            combined = result.stdout + result.stderr
            self.assertIn(
                "Error: add-on option notify_device is invalid (allowed: a-z, 0-9, _)",
                combined,
            )
            self.assertNotIn(bad, combined)
            dest = os.path.join(config_dir, "apps.yaml")
            if os.path.isfile(dest):
                with open(dest, "r", encoding="utf-8") as handle:
                    self.assertNotIn(bad, handle.read())

    def test_q_render_and_check_placeholders(self) -> None:
        startup = self._load_startup_module("predbat_startup_render")
        with open(APPS_YAML_SRC, "r", encoding="utf-8") as handle:
            v5_text = handle.read()

        rendered = startup.render_apps_yaml(
            v5_text, HA_TEST_LAT, HA_TEST_LON, "mobile_app_x"
        )
        self.assertNotIn("__HA_", rendered)
        startup.check_no_placeholders(rendered)

        tainted = rendered + "\n# __HA_SOMETHING__\n"
        with self.assertRaises(SystemExit) as raised:
            startup.check_no_placeholders(tainted)
        self.assertEqual(raised.exception.code, 1)

    def test_r_run_sh_unsets_predbat_env(self) -> None:
        probe = os.path.join(self._tmpdir, "probe_predbat_env.py")
        with open(probe, "w", encoding="utf-8") as handle:
            handle.write(
                "import os\n"
                "names = sorted(k for k in os.environ if k.startswith('PREDBAT_'))\n"
                "for name in names:\n"
                "    print(name)\n"
            )

        script = os.path.join(self._tmpdir, "run_test.sh")
        with open(RUN_SH, "r", encoding="utf-8") as handle:
            content = handle.read()
        replacement = "exec {} {}".format(sys.executable, probe)
        self.assertIn("exec python3 /startup.py", content)
        content = content.replace("exec python3 /startup.py", replacement)
        with open(script, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.chmod(script, 0o755)

        env = os.environ.copy()
        env["PREDBAT_SKIP_LAUNCH"] = "1"
        env["PREDBAT_TEST_MODE"] = "1"
        env["PREDBAT_KERNEL_SO"] = "/x"

        result = subprocess.run(
            ["bash", script],
            capture_output=True,
            text=True,
            env=env,
            cwd=self._tmpdir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        printed = [
            line.strip()
            for line in (result.stdout + result.stderr).splitlines()
            if line.strip().startswith("PREDBAT_")
        ]
        self.assertEqual(printed, [])


if __name__ == "__main__":
    unittest.main()
