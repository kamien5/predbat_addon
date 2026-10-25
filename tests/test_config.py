#!/usr/bin/env python3
"""
Static checks for add-on config.yaml and build.yaml (text/regex only).

Uses only the standard library. Requires Python 3.9+.
"""

from __future__ import annotations

import os
import re
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_YAML = os.path.join(REPO_ROOT, "predbat", "config.yaml")
BUILD_YAML = os.path.join(REPO_ROOT, "predbat", "build.yaml")


class ConfigYamlTestCase(unittest.TestCase):
    def setUp(self) -> None:
        with open(CONFIG_YAML, "r", encoding="utf-8") as handle:
            self.config_text = handle.read()
        with open(BUILD_YAML, "r", encoding="utf-8") as handle:
            self.build_text = handle.read()
        self.config_lines = self.config_text.splitlines()

    def test_no_ports_keys(self) -> None:
        for line in self.config_lines:
            stripped = line.lstrip()
            self.assertFalse(
                stripped.startswith("ports:") or stripped.startswith("ports_description:"),
                msg=line,
            )

    def test_hassio_api_false(self) -> None:
        self.assertRegex(self.config_text, r"(?m)^hassio_api:\s*false\s*$")

    def test_no_hassio_role(self) -> None:
        self.assertNotRegex(self.config_text, r"(?m)^hassio_role:")

    def test_no_auth_api(self) -> None:
        self.assertNotRegex(self.config_text, r"(?m)^auth_api:")

    def test_map_only_addon_config_rw(self) -> None:
        match = re.search(r"(?m)^map:\n((?:[ \t]+-.*\n)+)", self.config_text)
        self.assertIsNotNone(match)
        assert match is not None
        map_block = match.group(1)
        entries = [
            line.strip()[2:].strip()
            for line in map_block.splitlines()
            if line.strip().startswith("-")
        ]
        self.assertEqual(entries, ["addon_config:rw"])

    def test_no_predbat_env_options(self) -> None:
        self.assertNotIn("PREDBAT_", self.config_text)
        self.assertNotIn("SKIP_LAUNCH", self.config_text)
        self.assertNotIn("TEST_MODE", self.config_text)

    def test_notify_device_option_and_schema(self) -> None:
        self.assertRegex(
            self.config_text,
            r"(?m)^options:\n(?:.*\n)*?[ \t]+notify_device:\s*\"\"\s*$",
        )
        self.assertRegex(
            self.config_text,
            r"(?m)^schema:\n(?:.*\n)*?[ \t]+notify_device:\s*str\?\s*$",
        )

    def test_build_from_pinned_sha256(self) -> None:
        entries = re.findall(
            r"(?m)^[ \t]+(?:aarch64|amd64):\s*\"([^\"]+)\"\s*$",
            self.build_text,
        )
        self.assertGreaterEqual(len(entries), 2)
        for entry in entries:
            self.assertIn("@sha256:", entry)


if __name__ == "__main__":
    unittest.main()
