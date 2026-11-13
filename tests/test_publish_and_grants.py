#!/usr/bin/env python3
"""Static checks for publish.yml, GHCR tag-guard fail-closed behaviour, and W40/W41 hashes."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PUBLISH_YML = os.path.join(REPO_ROOT, ".github", "workflows", "publish.yml")
DEPLOY_MD = os.path.join(REPO_ROOT, "DEPLOY-UPGRADE.md")
GUARD_SH = os.path.join(REPO_ROOT, "tools", "ghcr_tag_guard.sh")

W40_MSG = {
    "endpoint": "/store/reload",
    "method": "post",
    "timeout": 120,
    "type": "supervisor/api",
}
W41_MSG = {
    "data": {"backup": False},
    "endpoint": "/addons/fc83ef65_predbat/update",
    "method": "post",
    "timeout": 1800,
    "type": "supervisor/api",
}
INVALID_W41_MSG = {
    "data": {"version": "1.7.1-kamien5.5"},
    "endpoint": "/addons/fc83ef65_predbat/update",
    "method": "post",
    "timeout": 1800,
    "type": "supervisor/api",
}

W40_SHA = "32e0b905acda79ce0561a3c30334eacf3466aa02b605ab0cd93f4e509b256df4"
W41_SHA = "c93f100b55152cf300a2dc4473fecea2a2cad32e38da6c37d3f7be84f79b7074"
INVALID_W41_SHA = "20d0c320501867a3c844be5e3cbd567fa1b9f743e84840e50d4b103726978412"


def canon_sha256(obj: object) -> str:
    payload = json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _classify(exit_code: int, output: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", GUARD_SH, "classify", str(exit_code)],
        input=output,
        text=True,
        capture_output=True,
        check=False,
    )


class CanonicalGrantTestCase(unittest.TestCase):
    def test_w40_hash(self) -> None:
        self.assertEqual(canon_sha256(W40_MSG), W40_SHA)

    def test_w41_hash_backup_false_schema(self) -> None:
        self.assertEqual(canon_sha256(W41_MSG), W41_SHA)
        self.assertNotEqual(W41_SHA, INVALID_W41_SHA)

    def test_old_version_payload_is_the_invalid_hash(self) -> None:
        self.assertEqual(canon_sha256(INVALID_W41_MSG), INVALID_W41_SHA)

    def test_deploy_doc_carries_live_hashes_and_marks_invalid(self) -> None:
        with open(DEPLOY_MD, "r", encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn(W40_SHA, text)
        self.assertIn(W41_SHA, text)
        self.assertIn(INVALID_W41_SHA, text)
        self.assertIn('"backup":false', text.replace(" ", ""))
        self.assertIn("version_latest == \"1.7.1-kamien5.5\"", text)
        self.assertIn("STOP", text)
        self.assertNotIn(
            '{"data":{"version":"1.7.1-kamien5.5"},"endpoint":"/addons/fc83ef65_predbat/update"',
            text,
        )


class PublishWorkflowTestCase(unittest.TestCase):
    def setUp(self) -> None:
        with open(PUBLISH_YML, "r", encoding="utf-8") as handle:
            self.pub = handle.read()

    def test_workflow_dispatch_requires_expected_sha(self) -> None:
        self.assertIn("workflow_dispatch:", self.pub)
        self.assertRegex(
            self.pub,
            r"expected_sha:\n(?:[ \t]+.+\n)*[ \t]+required:\s*true",
        )
        self.assertIn("github.sha ${GITHUB_SHA} != expected_sha ${EXPECTED_SHA}", self.pub)
        self.assertIn("^[0-9a-f]{40}$", self.pub)

    def test_minimal_permissions(self) -> None:
        self.assertNotIn("id-token:", self.pub)
        self.assertNotIn("attestations:", self.pub)
        block = re.search(r"(?m)^permissions:\n((?:[ \t]+.+\n)+)", self.pub)
        self.assertIsNotNone(block)
        assert block is not None
        perms = {
            line.strip()
            for line in block.group(1).splitlines()
            if line.strip()
        }
        self.assertEqual(perms, {"contents: read", "packages: write"})

    def test_login_before_tag_probe(self) -> None:
        login = self.pub.find("docker/login-action@")
        probe = self.pub.find("Refuse to overwrite an existing version tag")
        self.assertGreater(login, 0)
        self.assertGreater(probe, login)
        self.assertIn("bash tools/ghcr_tag_guard.sh inspect", self.pub)

    def test_immutable_tag_message_still_present_in_guard(self) -> None:
        with open(GUARD_SH, "r", encoding="utf-8") as handle:
            guard = handle.read()
        self.assertIn("already exists; version tags are immutable", guard)
        self.assertIn("refusing to publish", guard)


class GhcrTagGuardTestCase(unittest.TestCase):
    def test_existing_manifest_is_rejected(self) -> None:
        result = _classify(0, '{"schemaVersion": 2}')
        self.assertEqual(result.returncode, 1)
        self.assertIn("already exists", result.stderr)

    def test_missing_manifest_is_allowed(self) -> None:
        result = _classify(1, "no such manifest: ghcr.io/kamien5/predbat-addon/amd64:1.7.1-kamien5.5")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        result = _classify(1, "manifest unknown: manifest unknown")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        result = _classify(1, "Error response from daemon: manifest for x not found: manifest unknown")
        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_auth_and_network_are_fail_closed(self) -> None:
        cases = (
            "unauthorized: authentication required",
            "denied: requested access to the resource is denied",
            "HTTP 403 Forbidden",
            "TOOMANYREQUESTS: rate limit exceeded",
            "HTTP 500 Internal Server Error",
            "dial tcp: connection refused",
            "tls handshake timeout",
            "command not found",
        )
        for output in cases:
            with self.subTest(output=output):
                result = _classify(1, output)
                self.assertEqual(result.returncode, 1, msg=output)
                self.assertIn("refusing to publish", result.stderr)

    def test_auth_wins_over_missing_manifest_text(self) -> None:
        result = _classify(1, "unauthorized: authentication required\nmanifest unknown")
        self.assertEqual(result.returncode, 1)
        self.assertIn("auth/network/server", result.stderr)


if __name__ == "__main__":
    unittest.main()
