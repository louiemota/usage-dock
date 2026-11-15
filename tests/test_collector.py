#!/usr/bin/env python3
"""Shape pins for the collector — no network, no live secrets."""
from __future__ import annotations

import concurrent.futures
import datetime as dt
import json
import os
import sys
import tempfile
import time
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

    def test_prolite_is_pro_5x(self):
        self.assertEqual(c.plan_chip("prolite"), "Pro 5x")


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

    def test_file_wins_over_the_env(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"opencode-go": "sk-file"}, fh)
            path = fh.name
        self.addCleanup(lambda: os.unlink(path))
        with mock.patch.dict(os.environ, {"OPENCODE_GO_API_KEY": "sk-env"}, clear=False):
            self.assertEqual(c._opencode_go_token(path), "sk-file")

    def test_hermes_env_is_ignored_when_file_has_no_go_key(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"openai": {"key": "sk-openai"}}, fh)
            path = fh.name
        self.addCleanup(lambda: os.unlink(path))
        with mock.patch.dict(os.environ, {"OPENCODE_GO_API_KEY": "sk-env"}, clear=False):
            self.assertIsNone(c._opencode_go_token(path))


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
        self.assertEqual(weekly["windowSeconds"], 7 * 86400)
        self.assertEqual(five["windowSeconds"], 5 * 3600)
        self.assertIn("windowSeconds", row["details"][0])
        self.assertGreater(row["details"][0]["windowSeconds"], 27 * 86400)

    def test_error_payload_stays_visible(self):
        row = c.fill_command_row({"ok": False, "error": "sem API key"})
        self.assertFalse(row["ok"])
        self.assertEqual(row["error"], "sem API key")
        self.assertEqual(row["details"], [])


class OpenCodeRowTests(unittest.TestCase):
    def test_worst_window_is_the_ring(self):
        row = c.fill_opencode_row(
            {
                "ok": True,
                "rolling": {"percent": 12, "resetsAt": "2026-09-16T20:00:00Z"},
                "weekly": {"percent": 44, "resetsAt": "2026-09-20T00:00:00Z"},
                "monthly": {"percent": 9, "resetsAt": "2026-10-01T00:00:00Z"},
            }
        )
        self.assertTrue(row["ok"])
        self.assertEqual(row["plan"], "Go")
        self.assertEqual(row["usedPercent"], 44)
        self.assertEqual([d["label"] for d in row["details"]], ["Sessão 5h", "Semanal", "Mensal"])
        self.assertEqual(row["details"][0]["windowSeconds"], 5 * 3600)
        self.assertEqual(row["details"][1]["windowSeconds"], 7 * 86400)
        self.assertIn("pior janela (44%)", row["note"])

    def test_refused_key_stays_visible(self):
        row = c.fill_opencode_row({"ok": False, "error": "chave Go recusada — faça login de novo no OpenCode"})
        self.assertFalse(row["ok"])
        self.assertIn("chave Go recusada", row["error"])
        self.assertEqual(row["details"], [])
        self.assertTrue(row["skipWatch"])

    def test_collect_maps_403_to_login_copy(self):
        with mock.patch.object(c, "_opencode_go_token", return_value="sk-dead"):
            with mock.patch.object(c, "http", return_value=(403, {"error": "Forbidden"})):
                payload = c.collect_opencode()
        self.assertFalse(payload["ok"])
        self.assertIn("chave Go recusada", payload["error"])
        self.assertTrue(payload["skipWatch"])


class UnwatchTests(unittest.TestCase):
    def test_missing_login_is_unwatched(self):
        self.assertTrue(c.should_unwatch("sem chave Go — faça login no OpenCode"))
        self.assertTrue(c.should_unwatch("Cursor deslogado"))
        self.assertTrue(c.should_unwatch("sem API key — ~/.commandcode/auth.json"))

    def test_timeout_stays_in_the_queue(self):
        self.assertFalse(c.should_unwatch("Codex demorou demais"))
        self.assertFalse(c.should_unwatch("Cursor usage HTTP 500"))
        self.assertFalse(c.should_unwatch(None))

    def test_command_missing_key_marks_the_row(self):
        row = c.fill_command_row({"ok": False, "error": "sem API key — ~/.commandcode/auth.json", "skipWatch": True})
        self.assertTrue(row["skipWatch"])

    def test_skip_env_omits_the_provider(self):
        with mock.patch.dict(os.environ, {"USAGE_DOCK_SKIP": "opencode,goat"}, clear=False):
            self.assertEqual(c.skipped_ids(), {"opencode", "goat"})


def _fake_jwt(exp: float) -> str:
    payload = json.dumps({"exp": exp}, separators=(",", ":")).encode()
    body = __import__("base64").urlsafe_b64encode(payload).rstrip(b"=").decode()
    return f"eyJhbGciOiJub25lIn0.{body}.sig"


PROFILE_FIXTURE = {
    "profile": {"display_name": "Test"},
    "stats": {
        "lifetime_tokens": 1200,
        "peak_daily_tokens": 300,
        "longest_running_turn_sec": 4020,
        "current_streak_days": 2,
        "longest_streak_days": 11,
        "daily_usage_buckets": [
            {"start_date": "2026-08-12", "tokens": 100},
            {"start_date": "2026-09-03", "tokens": 200},
            {"start_date": "2026-09-08", "tokens": 300},
        ],
    },
}


class CodexWindowTests(unittest.TestCase):
    def test_details_carry_window_seconds_without_lifetime_caption(self):
        windows = [
            {
                "label": "Semanal",
                "minutes": 10_080,
                "usedPercent": 21.0,
                "remaining": 79.0,
                "resetsAt": "2026-09-13T12:00:00-03:00",
            },
            {
                "label": "Sessão 5h",
                "minutes": 300,
                "usedPercent": 8.0,
                "remaining": 92.0,
                "resetsAt": "2026-09-09T17:00:00-03:00",
            },
        ]
        details, ring = c._codex_details_from_windows(windows)
        self.assertEqual(ring, 21.0)
        self.assertEqual([d["label"] for d in details], ["Semanal", "Sessão 5h"])
        self.assertEqual(details[0]["windowSeconds"], 604_800)
        self.assertEqual(details[1]["windowSeconds"], 18_000)
        self.assertNotIn("caption", details[0])


class CodexProfileTests(unittest.TestCase):
    def test_decodes_stats_and_fills_thirty_day_series(self):
        today = dt.date(2026, 9, 9)
        payload = c._codex_profile_payload(PROFILE_FIXTURE, today=today)
        self.assertIsNotNone(payload)
        self.assertEqual(len(payload["daily"]), 30)
        self.assertEqual(payload["lifetimeTokens"], 1200)
        self.assertEqual(payload["peakDailyTokens"], 300)
        self.assertEqual(payload["longestChatSeconds"], 4020)
        self.assertEqual(payload["currentStreakDays"], 2)
        self.assertEqual(payload["longestStreakDays"], 11)
        self.assertEqual(payload["thirtyDayTokens"], 600)
        self.assertIsNone(payload["todayTokens"])
        self.assertEqual(payload["daily"][0], 0)
        self.assertEqual(payload["daily"][1], 100)
        self.assertEqual(payload["daily"][-2], 300)
        self.assertEqual(payload["daily"][-1], 0)

    def test_present_zero_today_is_real_zero(self):
        raw = {
            "stats": {
                "daily_usage_buckets": [{"start_date": "2026-09-09", "tokens": 0}],
            }
        }
        payload = c._codex_profile_payload(raw, today=dt.date(2026, 9, 9))
        self.assertEqual(payload["todayTokens"], 0)
        self.assertEqual(payload["thirtyDayTokens"], 0)

    def test_missing_stats_is_none(self):
        self.assertIsNone(c._codex_profile_payload({"profile": {}}))

    def test_fetch_uses_auth_and_omits_on_http_error(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(
                {
                    "tokens": {
                        "access_token": _fake_jwt(1_800_000_000 + 3600),
                        "account_id": "acct_test",
                    }
                },
                fh,
            )
            path = fh.name
        cache_ok = path + ".cache-ok"
        cache_bad = path + ".cache-bad"
        self.addCleanup(lambda: os.unlink(path))
        self.addCleanup(lambda: os.path.exists(cache_ok) and os.unlink(cache_ok))
        self.addCleanup(lambda: os.path.exists(cache_bad) and os.unlink(cache_bad))

        def ok_http(method, url, headers, body=None, timeout=10):
            self.assertEqual(method, "GET")
            self.assertIn("chatgpt.com/backend-api/wham/profiles/me", url)
            self.assertEqual(headers["ChatGPT-Account-Id"], "acct_test")
            self.assertTrue(headers["Authorization"].startswith("Bearer "))
            return 200, PROFILE_FIXTURE

        payload = c._codex_fetch_profile(
            auth_path=path,
            http_fn=ok_http,
            today=dt.date(2026, 9, 9),
            cache_path=cache_ok,
        )
        self.assertEqual(payload["lifetimeTokens"], 1200)
        self.assertEqual(len(payload["daily"]), 30)

        def bad_http(*_args, **_kwargs):
            return 401, {"error": "nope"}

        self.assertIsNone(
            c._codex_fetch_profile(
                auth_path=path,
                http_fn=bad_http,
                today=dt.date(2026, 9, 9),
                cache_path=cache_bad,
                cache_ttl=0,
            )
        )

    def test_profile_cache_skips_a_second_http_call(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(
                {
                    "tokens": {
                        "access_token": _fake_jwt(1_800_000_000 + 3600),
                        "account_id": "acct_test",
                    }
                },
                fh,
            )
            path = fh.name
        cache_path = path + ".cache"
        self.addCleanup(lambda: os.unlink(path))
        self.addCleanup(lambda: os.path.exists(cache_path) and os.unlink(cache_path))
        called = {"n": 0}

        def http_fn(*_args, **_kwargs):
            called["n"] += 1
            return 200, PROFILE_FIXTURE

        first = c._codex_fetch_profile(
            auth_path=path,
            http_fn=http_fn,
            today=dt.date(2026, 9, 9),
            now=1_800_000_000,
            cache_path=cache_path,
        )
        second = c._codex_fetch_profile(
            auth_path=path,
            http_fn=http_fn,
            today=dt.date(2026, 9, 9),
            now=1_800_000_000 + 30,
            cache_path=cache_path,
        )
        self.assertEqual(first["lifetimeTokens"], 1200)
        self.assertEqual(second["lifetimeTokens"], 1200)
        self.assertEqual(called["n"], 1)

    def test_profile_429_keeps_cache_and_backs_off(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(
                {
                    "tokens": {
                        "access_token": _fake_jwt(1_800_000_000 + 3600),
                        "account_id": "acct_test",
                    }
                },
                fh,
            )
            path = fh.name
        cache_path = path + ".cache"
        self.addCleanup(lambda: os.unlink(path))
        self.addCleanup(lambda: os.path.exists(cache_path) and os.unlink(cache_path))
        called = {"n": 0}

        def http_fn(*_args, **_kwargs):
            called["n"] += 1
            if called["n"] == 1:
                return 200, PROFILE_FIXTURE
            return 429, {"error": "rate"}

        c._codex_fetch_profile(
            auth_path=path,
            http_fn=http_fn,
            today=dt.date(2026, 9, 9),
            now=1_800_000_000,
            cache_path=cache_path,
            cache_ttl=0,
        )
        held = c._codex_fetch_profile(
            auth_path=path,
            http_fn=http_fn,
            today=dt.date(2026, 9, 9),
            now=1_800_000_000 + 1,
            cache_path=cache_path,
            cache_ttl=0,
        )
        skipped = c._codex_fetch_profile(
            auth_path=path,
            http_fn=http_fn,
            today=dt.date(2026, 9, 9),
            now=1_800_000_000 + 10,
            cache_path=cache_path,
            cache_ttl=0,
        )
        self.assertEqual(held["lifetimeTokens"], 1200)
        self.assertEqual(skipped["lifetimeTokens"], 1200)
        self.assertEqual(called["n"], 2)

    def test_expired_jwt_skips_profile(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(
                {
                    "tokens": {
                        "access_token": _fake_jwt(1_700_000_000),
                        "account_id": "acct_test",
                    }
                },
                fh,
            )
            path = fh.name
        cache_path = path + ".cache"
        self.addCleanup(lambda: os.unlink(path))
        self.addCleanup(lambda: os.path.exists(cache_path) and os.unlink(cache_path))
        called = {"n": 0}

        def http_fn(*_args, **_kwargs):
            called["n"] += 1
            return 200, PROFILE_FIXTURE

        self.assertIsNone(
            c._codex_fetch_profile(
                auth_path=path,
                http_fn=http_fn,
                today=dt.date(2026, 9, 9),
                now=1_800_000_000,
                cache_path=cache_path,
            )
        )
        self.assertEqual(called["n"], 0)


class CodexUsageHttpTests(unittest.TestCase):
    def test_windows_from_wham_usage(self):
        body = {
            "plan_type": "prolite",
            "rate_limit": {
                "primary_window": {
                    "used_percent": 87,
                    "limit_window_seconds": 604800,
                    "reset_at": 1790180757,
                },
                "secondary_window": {
                    "used_percent": 12,
                    "limit_window_seconds": 18000,
                    "reset_at": 1790090000,
                },
            },
        }
        windows = c._codex_windows_from_usage(body)
        self.assertEqual([w["label"] for w in windows], ["Semanal", "Sessão 5h"])
        self.assertEqual(windows[0]["usedPercent"], 87)
        self.assertEqual(windows[0]["minutes"], 10_080)
        details, ring = c._codex_details_from_windows(windows)
        self.assertEqual(ring, 87)
        self.assertEqual(details[0]["windowSeconds"], 604_800)

    def test_slow_source_stays_in_the_queue(self):
        self.assertFalse(c.should_unwatch("codex sem resposta"))


class DevinRowTests(unittest.TestCase):
    def test_quota_windows_and_cycle(self):
        row = c.fill_devin_row(
            {
                "ok": True,
                "pro": True,
                "planName": "Pro",
                "planStatus": {
                    "planStart": "2026-09-22T11:15:15Z",
                    "planEnd": "2026-10-22T11:15:15Z",
                    "dailyQuotaRemainingPercent": 80,
                    "weeklyQuotaRemainingPercent": 60,
                    "dailyQuotaResetAtUnix": 1790150400,
                    "weeklyQuotaResetAtUnix": 1790496000,
                    "overageBalanceMicros": "9558440",
                },
            }
        )
        self.assertTrue(row["ok"])
        self.assertEqual(row["plan"], "Pro")
        self.assertEqual(row["usedPercent"], 40)
        labels = [d["label"] for d in row["details"]]
        self.assertEqual(labels, ["Diária", "Semanal", "Ciclo"])
        self.assertEqual(row["details"][0]["usedPercent"], 20)
        self.assertEqual(row["details"][0]["windowSeconds"], 86400)
        self.assertEqual(row["details"][1]["windowSeconds"], 604800)
        self.assertIn("$9.56", row["details"][2]["caption"])

    def test_not_pro_marks_cancelled(self):
        row = c.fill_devin_row({"ok": True, "pro": False, "planName": "Free", "planStatus": {}})
        self.assertTrue(row["cancelled"])
        dead = c.apply_dead(row)
        self.assertTrue(dead["skipWatch"])
        self.assertEqual(dead["error"], "assinatura cancelada")

    def test_missing_key_unwatches(self):
        row = c.fill_devin_row({"ok": False, "error": "sem API key Devin — rode `devin auth login`", "skipWatch": True})
        self.assertTrue(row["skipWatch"])


class ClaudeRowTests(unittest.TestCase):
    def test_five_hour_and_weekly_windows(self):
        row = c.fill_claude_row(
            {
                "ok": True,
                "subscription": "max",
                "tier": "default_claude_max_5x",
                "usage": {
                    "five_hour": {"utilization": 12.0, "resets_at": "2026-09-24T04:30:00.380661+00:00"},
                    "seven_day": {"utilization": 41.0, "resets_at": "2026-09-26T07:00:00+00:00"},
                    "seven_day_opus": None,
                },
            }
        )
        self.assertTrue(row["ok"])
        self.assertEqual(row["plan"], "Max 5x")
        self.assertEqual(row["usedPercent"], 41)
        self.assertEqual([d["label"] for d in row["details"]], ["5 horas", "Semanal"])
        self.assertEqual(row["details"][0]["windowSeconds"], 18000)
        self.assertIsNotNone(row["details"][0]["resetsAt"])

    def test_pro_plan_chip(self):
        self.assertEqual(c.claude_plan("pro", "default_claude_ai"), "Pro")
        self.assertEqual(c.claude_plan("max", "default_claude_max_20x"), "Max 20x")

    def test_weekly_at_limit_leaves_the_dock(self):
        row = c.fill_claude_row(
            {"ok": True, "subscription": "max", "usage": {"seven_day": {"utilization": 100.0}}}
        )
        dead = c.apply_dead(row)
        self.assertTrue(dead["skipWatch"])
        self.assertIn("esgotada", dead["error"])

    def test_missing_login_unwatches(self):
        with mock.patch.object(c, "_claude_oauth", return_value=None):
            row = c.fill_claude_row(c.collect_claude())
        self.assertTrue(row["skipWatch"])

    def test_expired_token_stays_in_the_queue(self):
        oauth = {"accessToken": "x", "expiresAt": (time.time() - 60) * 1000}
        with mock.patch.object(c, "_claude_oauth", return_value=oauth), mock.patch.object(c, "http") as http:
            row = c.fill_claude_row(c.collect_claude())
        http.assert_not_called()
        self.assertFalse(row["skipWatch"])
        self.assertTrue(row["stale"])


class DeadSubscriptionTests(unittest.TestCase):
    def test_exhausted_ring_leaves_the_dock(self):
        dead = c.apply_dead(c.row("goat", "Command", ok=True, usedPercent=100))
        self.assertFalse(dead["ok"])
        self.assertTrue(dead["skipWatch"])
        self.assertIn("esgotada", dead["error"])

    def test_free_plan_is_treated_as_cancelled(self):
        dead = c.apply_dead(c.row("cursor", "Cursor", ok=True, usedPercent=10, plan="Free"))
        self.assertTrue(dead["skipWatch"])

    def test_alive_provider_is_untouched(self):
        alive = c.apply_dead(c.row("grok", "Grok", ok=True, usedPercent=39, plan="SuperGrok"))
        self.assertTrue(alive["ok"])
        self.assertFalse(alive["skipWatch"])

    def test_error_rows_pass_through(self):
        failed = c.apply_dead(c.row("codex", "Codex", ok=False, error="timeout"))
        self.assertFalse(failed["ok"])
        self.assertFalse(failed["skipWatch"])


class WindowDurationTests(unittest.TestCase):
    def test_seconds_between_iso_stamps(self):
        seconds = c._seconds_between(
            "2026-09-05T08:21:18Z",
            "2026-09-12T08:21:18Z",
        )
        self.assertEqual(seconds, 7 * 86400)

    def test_month_before_reset_is_one_calendar_month(self):
        seconds = c._month_seconds_before("2026-10-03T13:09:45.611Z")
        self.assertIsNotNone(seconds)
        start = dt.datetime(2026, 9, 3, 13, 9, 45, 611000, tzinfo=dt.timezone.utc)
        end = dt.datetime(2026, 10, 3, 13, 9, 45, 611000, tzinfo=dt.timezone.utc)
        self.assertAlmostEqual(seconds, (end - start).total_seconds(), places=0)


class CollectorTimeoutTests(unittest.TestCase):
    def test_timeout_returns_fallback_without_blocking(self):
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.addCleanup(lambda: pool.shutdown(wait=False, cancel_futures=True))
        fut = pool.submit(time.sleep, 3)
        fallback = c.row("codex", "Codex", error="Codex demorou demais", stale=True)
        t0 = time.time()
        out = c._await_future(fut, 0.05, fallback)
        self.assertLess(time.time() - t0, 1.0)
        self.assertEqual(out["error"], "Codex demorou demais")
        self.assertTrue(out["stale"])

    def test_finished_future_keeps_value(self):
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.addCleanup(lambda: pool.shutdown(wait=False, cancel_futures=True))
        fut = pool.submit(lambda: c.row("codex", "Codex", ok=True, usedPercent=43))
        out = c._await_future(fut, 2, c.row("codex", "Codex", error="timeout", stale=True))
        self.assertTrue(out["ok"])
        self.assertEqual(out["usedPercent"], 43)


if __name__ == "__main__":
    unittest.main()
