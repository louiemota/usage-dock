#!/usr/bin/env python3
"""Shape pins for the collector — no network, no live secrets."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import collector as c  # noqa: E402


class PlanChipTests(unittest.TestCase):
    def test_individual_goat_is_goat(self):
        self.assertEqual(c.plan_chip("individual-goat"), "GOAT")

    def test_go_is_go(self):
        self.assertEqual(c.plan_chip("go"), "Go")


class OpenCodeAuthTests(unittest.TestCase):
    def test_reads_object_key(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"opencode-go": {"type": "api", "key": "sk-go-live"}}, fh)
            path = fh.name
        self.addCleanup(lambda: os.unlink(path))
        with mock.patch.dict(os.environ, {"OPENCODE_GO_API_KEY": ""}, clear=False):
            os.environ.pop("OPENCODE_GO_API_KEY", None)
            self.assertEqual(c._opencode_go_token(path), "sk-go-live")

    def test_reads_bare_string(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"opencode-go": "sk-go-live"}, fh)
            path = fh.name
        self.addCleanup(lambda: os.unlink(path))
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENCODE_GO_API_KEY", None)
            self.assertEqual(c._opencode_go_token(path), "sk-go-live")

    def test_ignores_other_vendors(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"openai": {"key": "sk-openai"}}, fh)
            path = fh.name
        self.addCleanup(lambda: os.unlink(path))
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENCODE_GO_API_KEY", None)
            self.assertIsNone(c._opencode_go_token(path))

    def test_env_wins_over_the_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"opencode-go": "sk-file"}, fh)
            path = fh.name
        self.addCleanup(lambda: os.unlink(path))
        with mock.patch.dict(os.environ, {"OPENCODE_GO_API_KEY": "sk-env"}, clear=False):
            self.assertEqual(c._opencode_go_token(path), "sk-env")


class CommandCodeKeyTests(unittest.TestCase):
    def test_reads_auth_json(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"apiKey": "user_testkey", "userName": "tester"}, fh)
            path = fh.name
        self.addCleanup(lambda: os.unlink(path))
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("COMMAND_CODE_API_KEY", None)
            os.environ.pop("COMMANDCODE_API_KEY", None)
            self.assertEqual(c._commandcode_key(path), "user_testkey")

    def test_missing_file_is_none(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("COMMAND_CODE_API_KEY", None)
            os.environ.pop("COMMANDCODE_API_KEY", None)
            self.assertIsNone(c._commandcode_key("/tmp/does-not-exist-usage-dock.json"))

    def test_desktop_env_wins_over_the_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"apiKey": "user_file"}, fh)
            path = fh.name
        self.addCleanup(lambda: os.unlink(path))
        with mock.patch.dict(os.environ, {"COMMAND_CODE_API_KEY": "user_env"}, clear=False):
            self.assertEqual(c._commandcode_key(path), "user_env")

    def test_hermes_named_key_is_ignored_when_the_file_exists(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"apiKey": "user_file"}, fh)
            path = fh.name
        self.addCleanup(lambda: os.unlink(path))
        with mock.patch.dict(os.environ, {"COMMANDCODE_API_KEY": "user_hermes"}, clear=False):
            os.environ.pop("COMMAND_CODE_API_KEY", None)
            self.assertEqual(c._commandcode_key(path), "user_file")


class CommandRowTests(unittest.TestCase):
    def test_monthly_ring_and_windows(self):
        cc = {
            "ok": True,
            "summary": {"totalCost": 50.50, "totalCount": 10, "totalTokensIn": 0, "totalTokensOut": 0},
            "credits": {"monthlyCredits": 19.50},
            "windowLimits": {
                "fiveHour": {"used": 0, "cap": 14, "resetAt": 0},
                "weekly": {"used": 22.45, "cap": 35, "resetAt": 1787857355088},
            },
            "subscription": {
                "planId": "individual-goat",
                "currentPeriodEnd": "2026-09-13T15:21:27.000Z",
            },
        }
        row = c.fill_command_row(cc)
        self.assertTrue(row["ok"])
        self.assertEqual(row["plan"], "GOAT")
        self.assertAlmostEqual(row["usedPercent"], 50.50 / 70.0 * 100, places=4)
        labels = [d["label"] for d in row["details"]]
        self.assertEqual(labels[:3], ["Mensal", "Sessão 5h", "Semanal"])
        five = row["details"][1]
        self.assertEqual(five["usedPercent"], 0)
        self.assertIsNone(five["resetsAt"])
        weekly = row["details"][2]
        self.assertAlmostEqual(weekly["usedPercent"], 22.45 / 35 * 100, places=4)
        self.assertIsNotNone(weekly["resetsAt"])

    def test_error_payload_stays_visible(self):
        row = c.fill_command_row({"ok": False, "error": "sem API key"})
        self.assertFalse(row["ok"])
        self.assertEqual(row["error"], "sem API key")
        self.assertEqual(row["details"], [])


if __name__ == "__main__":
    unittest.main()
