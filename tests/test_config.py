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
DOCKERFILE = os.path.join(REPO_ROOT, "predbat", "Dockerfile")


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
            r"(?m)^schema:\n(?:.*\n)*?[ \t]+notify_device:\s*\"match\(\^\[a-z0-9_\]\*\$\)\?\"\s*$",
        )

    def test_notify_device_schema_regex_matches_startup_validation(self) -> None:
        match = re.search(
            r"(?m)^[ \t]+notify_device:\s*\"match\((.+)\)\?\"\s*$",
            self.config_text,
        )
        self.assertIsNotNone(match)
        pattern = re.compile(match.group(1))
        for ok in ("", "mobile_app_x", "abc_123"):
            self.assertIsNotNone(pattern.fullmatch(ok), msg=ok)
        for bad in ("Mobile", "a-b", "a b", "a]\nb: c", "x,y", "a.b", "[x]"):
            self.assertIsNone(pattern.fullmatch(bad), msg=bad)

    def test_build_from_pinned_sha256(self) -> None:
        entries = re.findall(
            r"(?m)^[ \t]+aarch64:\s*\"([^\"]+)\"\s*$",
            self.build_text,
        )
        self.assertEqual(len(entries), 1)
        for entry in entries:
            self.assertIn("@sha256:", entry)

    def test_dockerfile_from_hardcoded_and_matches_build_yaml(self) -> None:
        with open(DOCKERFILE, "r", encoding="utf-8") as handle:
            dockerfile_text = handle.read()
        self.assertNotIn("BUILD_FROM", dockerfile_text)
        from_matches = re.findall(r"(?m)^FROM\s+(\S+)\s*$", dockerfile_text)
        self.assertEqual(len(from_matches), 1)
        image = from_matches[0]
        self.assertIn("@sha256:", image)
        build_from = re.search(
            r"(?m)^[ \t]+aarch64:\s*\"([^\"]+)\"\s*$",
            self.build_text,
        )
        self.assertIsNotNone(build_from)
        assert build_from is not None
        self.assertEqual(image, build_from.group(1))

    def test_config_arch_aarch64_only(self) -> None:
        match = re.search(r"(?m)^arch:\n((?:[ \t]+-.*\n)+)", self.config_text)
        self.assertIsNotNone(match)
        assert match is not None
        arch_block = match.group(1)
        entries = [
            line.strip()[2:].strip()
            for line in arch_block.splitlines()
            if line.strip().startswith("-")
        ]
        self.assertEqual(entries, ["aarch64"])


if __name__ == "__main__":
    unittest.main()
