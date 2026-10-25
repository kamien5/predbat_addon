#!/usr/bin/env python3
"""
Unit tests for the kamien5 Predbat add-on startup hardening.

Run from the repository root:
  python3 -m unittest discover -s tests -v

Uses only the standard library. Requires Python 3.9+.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from typing import Dict, Optional, Tuple

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STARTUP_PY = os.path.join(REPO_ROOT, "predbat", "rootfs", "startup.py")
VENDOR_SRC = os.path.join(REPO_ROOT, "predbat", "vendor")
MANIFEST_SRC = os.path.join(REPO_ROOT, "predbat", "MANIFEST.sha256")
LAUNCH_SRC = os.path.join(
    REPO_ROOT, "predbat", "rootfs", "opt", "predbat", "launch.py"
)

EXPECTED_FILE_COUNT = 114


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


class StartupTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp(prefix="predbat_startup_test_")
        self.addCleanup(shutil.rmtree, self._tmpdir, ignore_errors=True)

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
        supervisor_token: Optional[str] = "test-token",
        extra_env: Optional[Dict[str, str]] = None,
    ) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        # Drop host tokens so tests control presence explicitly.
        env.pop("SUPERVISOR_TOKEN", None)
        env.pop("PREDBAT_TEST_MODE", None)
        env.pop("PREDBAT_SKIP_LAUNCH", None)

        env["PREDBAT_CONFIG_DIR"] = config_dir
        env["PREDBAT_IMAGE_DIR"] = image_dir
        if skip_launch:
            env["PREDBAT_SKIP_LAUNCH"] = "1"
        if test_mode:
            env["PREDBAT_TEST_MODE"] = "1"
        if supervisor_token is not None:
            env["SUPERVISOR_TOKEN"] = supervisor_token
        if extra_env:
            env.update(extra_env)

        return subprocess.run(
            [sys.executable, STARTUP_PY],
            capture_output=True,
            text=True,
            env=env,
            cwd=REPO_ROOT,
        )

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

        # Load launch.py by path so we do not import the real vendored download.
        spec = importlib.util.spec_from_file_location("predbat_launch_under_test", LAUNCH_SRC)
        self.assertIsNotNone(spec)
        assert spec is not None and spec.loader is not None
        launch_mod = importlib.util.module_from_spec(spec)
        sys.modules["predbat_launch_under_test"] = launch_mod
        spec.loader.exec_module(launch_mod)

        sys.path.insert(0, fake_dir)
        self.addCleanup(lambda: sys.path.remove(fake_dir) if fake_dir in sys.path else None)
        # Ensure a fresh fake download module is imported.
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


if __name__ == "__main__":
    unittest.main()
