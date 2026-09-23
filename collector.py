#!/usr/bin/env python3
"""Usage Dock collector — Codex, OpenCode Go, Command GOAT, Cursor, SuperGrok.

Reads local credentials already on this Mac. Never prints tokens.
OpenCode Go lê só ~/.local/share/opencode/auth.json — nunca o .env do Hermes.
"""
from __future__ import annotations

import base64
import calendar
import concurrent.futures
import datetime as dt
import json
import os
import re
import select
import sqlite3
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
CODEX_HISTORY = os.path.expanduser(
    "~/Library/Application Support/com.github.thrr87.CodexLimits/History"
)
CURSOR_DB = os.path.expanduser(
    "~/Library/Application Support/Cursor/User/globalStorage/state.vscdb"
)
GROK_AUTH = os.path.expanduser("~/.grok/auth.json")
GROK_LOCK = os.path.expanduser("~/.grok/auth.json.lock")
COMMANDCODE_AUTH = os.path.expanduser("~/.commandcode/auth.json")
COMMANDCODE_API = "https://api.commandcode.ai"
OPENCODE_AUTH = os.path.expanduser("~/.local/share/opencode/auth.json")
OPENCODE_USAGE_URL = "https://opencode.ai/zen/go/v1/usage"
DEVIN_CREDS = os.path.expanduser("~/.local/share/devin/credentials.toml")
XAI_TOKEN_URL = "https://auth.x.ai/oauth2/token"
XAI_CLIENT_ID = "b1a00492-073a-47ea-816f-4c329264a828"
CODEX_BINARIES = [
    os.path.expanduser("~/.local/bin/codex"),
    "/opt/homebrew/bin/codex",
    "/usr/local/bin/codex",
]
CODEX_WEEKLY_MINUTES = 10_080
CODEX_FIVE_HOUR_MINUTES = 300
CODEX_AUTH = os.path.expanduser("~/.codex/auth.json")
CODEX_USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"
CODEX_PROFILE_URL = "https://chatgpt.com/backend-api/wham/profiles/me"
CODEX_PROFILE_CACHE = os.path.expanduser("~/.cache/usage-dock/codex-profile.json")
CODEX_PROFILE_TTL = 5 * 60
PROVIDER_FUTURE_TIMEOUT = 10
CODEX_FUTURE_TIMEOUT = 16
APPLE_EPOCH = dt.datetime(2001, 1, 1, tzinfo=dt.timezone.utc)
CURSOR_PLAN_LABELS = {
    "pro_plus": "Pro Plus",
    "pro": "Pro",
    "ultra": "Ultra",
    "business": "Business",
    "team": "Team",
    "free": "Free",
    "hobby": "Hobby",
}
PLAN_LABELS = {
    **CURSOR_PLAN_LABELS,
    "plus": "Plus",
    "plus_monthly": "Plus",
    "chatgpt_plus": "Plus",
    "chatgpt_pro": "Pro",
    "prolite": "Pro 5x",
    "pro_lite": "Pro 5x",
    "pro5x": "Pro 5x",
    "pro_5x": "Pro 5x",
    "pro20x": "Pro 20x",
    "pro_20x": "Pro 20x",
    "edu": "Edu",
    "enterprise": "Enterprise",
    "super": "SuperGrok",
    "supergrok": "SuperGrok",
    "go": "Go",
    "goat": "GOAT",
    "individual_goat": "GOAT",
}


def http(method: str, url: str, headers: dict, body=None, timeout: int = 10):
    data = None
    if body is not None:
        data = body if isinstance(body, (bytes, bytearray)) else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return r.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            parsed = json.loads(raw) if raw else {}
        except Exception:
            parsed = {"_raw": raw[:400].decode("utf-8", "replace")}
        return e.code, parsed


def iso(ts) -> str | None:
    if ts is None or ts == "" or ts == 0:
        return None
    try:
        if isinstance(ts, str):
            s = ts.strip()
            if not s or s in ("0", "0.0"):
                return None
            if s.isdigit() or s.replace(".", "", 1).isdigit():
                return iso(float(s))
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            d = dt.datetime.fromisoformat(s)
            if d.tzinfo is None:
                d = d.replace(tzinfo=dt.timezone.utc)
            if d.year < 2020:
                return None
            return d.astimezone().isoformat(timespec="seconds")
        v = float(ts)
        if v <= 0:
            return None
        if v > 10**12:
            v /= 1000
        if v > 10**11:
            v /= 1000
        if 600_000_000 < v < 1_200_000_000:
            d = APPLE_EPOCH + dt.timedelta(seconds=v)
        else:
            d = dt.datetime.fromtimestamp(v, tz=dt.timezone.utc)
        if d.year < 2020:
            return None
        return d.astimezone().isoformat(timespec="seconds")
    except Exception:
        return None


def _parse_iso_dt(raw) -> dt.datetime | None:
    stamp = iso(raw)
    if not stamp:
        return None
    try:
        parsed = dt.datetime.fromisoformat(stamp)
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed


def _seconds_between(start, end) -> float | None:
    start_at = _parse_iso_dt(start)
    end_at = _parse_iso_dt(end)
    if start_at is None or end_at is None:
        return None
    delta = (end_at - start_at).total_seconds()
    if delta <= 0 or delta != delta:
        return None
    return delta


def _add_months(moment: dt.datetime, months: int) -> dt.datetime:
    month0 = moment.month - 1 + months
    year = moment.year + month0 // 12
    month = month0 % 12 + 1
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


def _month_seconds_before(end) -> float | None:
    """Janela mensal do OpenCode: um mês civil UTC terminando no reset. Igual ao Codenotch."""
    end_at = _parse_iso_dt(end)
    if end_at is None:
        return None
    utc = end_at.astimezone(dt.timezone.utc)
    delta = (utc - _add_months(utc, -1)).total_seconds()
    if delta <= 0:
        return None
    return delta


def plan_chip(raw) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    key = s.lower().replace(" ", "_").replace("-", "_")
    if key in PLAN_LABELS:
        return PLAN_LABELS[key]
    if len(s) > 22 or all(c in "0123456789abcdef-" for c in key) and len(key) >= 20:
        return None
    pretty = s.replace("_", " ").replace("-", " ").strip()
    if not pretty:
        return None
    return pretty.title() if pretty.islower() or "_" in s or "-" in s else pretty


def row(id_: str, name: str, **kwargs) -> dict:
    base = {
        "id": id_,
        "name": name,
        "ok": False,
        "usedPercent": None,
        "details": [],
        "note": None,
        "plan": None,
        "error": None,
        "stale": False,
        "skipWatch": False,
    }
    base.update(kwargs)
    return base


UNWATCH_HINTS = (
    "sem chave",
    "faça login",
    "faca login",
    "deslogado",
    "sem api key",
    "api key inválida",
    "api key invalida",
    "chave go recusada",
    "token grok vazio",
    "auth.json",
    "cli/limits indisponível",
    "cli/limits indisponivel",
    "histórico codexlimits vazio",
    "historico codexlimits vazio",
)


def should_unwatch(error: str | None) -> bool:
    """Falta de login/assinatura — o HUD tira o anel da fila. Timeout e 5xx ficam."""
    if not error:
        return False
    text = str(error).lower()
    return any(hint in text for hint in UNWATCH_HINTS)


def apply_unwatch(payload: dict) -> dict:
    err = payload.get("error")
    if payload.get("skipWatch") or should_unwatch(err):
        payload["skipWatch"] = True
    return payload


def _opencode_go_token(auth_path: str | None = None) -> str | None:
    """Codenotch 1.12: só o auth.json do OpenCode. Env do Hermes era chave morta (403)."""
    try:
        with open(auth_path or OPENCODE_AUTH, encoding="utf-8") as fh:
            root = json.load(fh)
        entry = root.get("opencode-go")
        if isinstance(entry, str) and entry.strip():
            return entry.strip()
        if isinstance(entry, dict):
            for key in ("key", "apiKey", "api_key", "token", "accessToken"):
                token = str(entry.get(key) or "").strip()
                if token:
                    return token
    except Exception:
        pass
    return None


def fill_command_row(cc: dict) -> dict:
    """Monta o slot goat a partir do payload /alpha. Sem rede — testável."""
    cc_row = row("goat", "Command")
    if not cc.get("ok"):
        cc_row["error"] = cc.get("error") or "Command Code indisponível"
        return apply_unwatch(cc_row)
    summary = cc.get("summary") if isinstance(cc.get("summary"), dict) else {}
    credits = cc.get("credits") if isinstance(cc.get("credits"), dict) else {}
    windows = cc.get("windowLimits") if isinstance(cc.get("windowLimits"), dict) else {}
    sub = cc.get("subscription") if isinstance(cc.get("subscription"), dict) else {}
    used = float(summary.get("totalCost") or 0)
    remaining = float(credits.get("monthlyCredits") or 0)
    cap = used + remaining if (used or remaining) else 70.0
    monthly_pct = (used / cap * 100) if cap else 0.0
    monthly_seconds = _seconds_between(sub.get("currentPeriodStart"), sub.get("currentPeriodEnd"))
    if monthly_seconds is None:
        monthly_seconds = _month_seconds_before(sub.get("currentPeriodEnd"))
    monthly = {
        "label": "Mensal",
        "usedPercent": monthly_pct,
        "resetsAt": iso(sub.get("currentPeriodEnd")),
        "caption": f"${used:.2f} de ${cap:.0f} · resta ${remaining:.2f}",
    }
    if monthly_seconds:
        monthly["windowSeconds"] = monthly_seconds
    details = [monthly]
    for key, label, seconds in (
        ("fiveHour", "Sessão 5h", CODEX_FIVE_HOUR_MINUTES * 60),
        ("weekly", "Semanal", CODEX_WEEKLY_MINUTES * 60),
    ):
        w = windows.get(key) or {}
        w_used = float(w.get("used") or 0)
        w_cap = float(w.get("cap") or 0)
        if w_cap <= 0:
            continue
        details.append(
            {
                "label": label,
                "usedPercent": w_used / w_cap * 100,
                "resetsAt": iso(w.get("resetAt") or None),
                "caption": f"${w_used:.2f} de ${w_cap:.0f}",
                "windowSeconds": seconds,
            }
        )
    runs = summary.get("totalCount")
    tok_in = float(summary.get("totalTokensIn") or 0)
    tok_out = float(summary.get("totalTokensOut") or 0)
    if runs or tok_in or tok_out:
        details.append(
            {
                "label": "Volume",
                "usedPercent": None,
                "resetsAt": iso(sub.get("currentPeriodEnd")),
                "caption": f"{int(runs or 0)} runs · {tok_in/1e6:.1f}M in / {tok_out/1e3:.0f}K out",
            }
        )
    plan = sub.get("planId")
    cc_row.update(
        ok=True,
        usedPercent=monthly_pct,
        details=details,
        plan=plan_chip(plan),
        note=None,
    )
    if cc.get("cancelled"):
        cc_row["cancelled"] = True
    return cc_row


def _commandcode_key(auth_path: str | None = None) -> str | None:
    """Mesma ordem do app desktop: env oficial, depois ~/.commandcode/auth.json.

    COMMANDCODE_API_KEY (Hermes) fica por último — é outro nome de variável e
    pode apontar para uma chave antiga, diferente da sessão logada no app.
    """
    for env_name in ("COMMAND_CODE_API_KEY",):
        value = os.environ.get(env_name, "").strip()
        if value:
            return value
    try:
        with open(auth_path or COMMANDCODE_AUTH, encoding="utf-8") as fh:
            data = json.load(fh)
        value = str(data.get("apiKey") or "").strip()
        if value:
            return value
    except Exception:
        pass
    value = os.environ.get("COMMANDCODE_API_KEY", "").strip()
    return value or None


def _commandcode_api(path: str, key: str) -> dict:
    status, body = http(
        "GET",
        COMMANDCODE_API + path,
        {
            "Authorization": f"Bearer {key}",
            "User-Agent": "command-code-desktop",
            "Accept": "application/json",
            "x-command-code-version": "desktop",
        },
        timeout=12,
    )
    if status >= 400:
        hint = ""
        if isinstance(body, dict):
            hint = str(body.get("error") or body.get("message") or "")[:120]
        if status in (401, 403):
            raise RuntimeError("API key inválida ou expirada — rode o login no Command Code")
        raise RuntimeError(f"{path} HTTP {status}" + (f": {hint}" if hint else ""))
    return body if isinstance(body, dict) else {}


def collect_commandcode() -> dict:
    """Cota GOAT via /alpha + Bearer, o mesmo caminho do app Command Code.

    O coletor antigo lia cookie de Chrome em /internal/. A API saiu desse
    contrato; sem o cookie o dock marcava Command como indisponível.
    """
    key = _commandcode_key()
    if not key:
        return {
            "ok": False,
            "error": "sem API key — ~/.commandcode/auth.json ou COMMAND_CODE_API_KEY",
            "skipWatch": True,
        }
    try:
        whoami = _commandcode_api("/alpha/whoami", key)
        org = whoami.get("org") if isinstance(whoami.get("org"), dict) else {}
        org_id = org.get("id")
        query = f"?orgId={urllib.parse.quote(str(org_id))}" if org_id else ""
        credits_raw = _commandcode_api(f"/alpha/billing/credits{query}", key)
        subs_raw = _commandcode_api(f"/alpha/billing/subscriptions{query}", key)
        sub = subs_raw.get("data", subs_raw)
        cancelled = "data" in subs_raw and subs_raw.get("data") is None
        since = sub.get("currentPeriodStart") if isinstance(sub, dict) else None
        summary_bits = []
        if org_id:
            summary_bits.append("orgId=" + urllib.parse.quote(str(org_id)))
        if since:
            summary_bits.append("since=" + urllib.parse.quote(str(since)))
        summary_path = "/alpha/usage/summary"
        if summary_bits:
            summary_path += "?" + "&".join(summary_bits)
        summary = _commandcode_api(summary_path, key)
        credits = credits_raw.get("credits") if isinstance(credits_raw.get("credits"), dict) else {}
        windows = credits_raw.get("windowLimits") if isinstance(credits_raw.get("windowLimits"), dict) else {}
        return {
            "ok": True,
            "summary": summary,
            "credits": credits,
            "windowLimits": windows if isinstance(windows, dict) else {},
            "subscription": sub if isinstance(sub, dict) else {},
            "cancelled": cancelled,
            "belowThreshold": bool(credits.get("belowThreshold")),
            "breakdownByModel": [],
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def fill_opencode_row(oc: dict) -> dict:
    """Monta o slot OpenCode a partir do payload zen/go. Sem rede — testável."""
    oc_row = row("opencode", "OpenCode")
    if not oc.get("ok"):
        oc_row["error"] = oc.get("error") or "OpenCode indisponível"
        return apply_unwatch({**oc_row, "skipWatch": bool(oc.get("skipWatch"))})
    details = []
    pcts = []
    for key, label in (("rolling", "Sessão 5h"), ("weekly", "Semanal"), ("monthly", "Mensal")):
        p = oc.get(key) or {}
        pct = p.get("percent")
        if pct is None:
            continue
        pcts.append(float(pct))
        if key == "rolling":
            seconds = CODEX_FIVE_HOUR_MINUTES * 60
        elif key == "weekly":
            seconds = CODEX_WEEKLY_MINUTES * 60
        else:
            seconds = _month_seconds_before(p.get("resetsAt"))
        item = {
            "label": label,
            "usedPercent": float(pct),
            "resetsAt": iso(p.get("resetsAt")),
        }
        if seconds:
            item["windowSeconds"] = seconds
        details.append(item)
    oc_row.update(ok=True, usedPercent=max(pcts) if pcts else 0.0, details=details, plan="Go")
    note_parts = []
    if oc.get("modelCount"):
        note_parts.append(f"{oc['modelCount']} modelos")
    if pcts:
        note_parts.append(f"anel = pior janela ({max(pcts):.0f}%)")
    if note_parts:
        oc_row["note"] = " · ".join(note_parts)
    return oc_row


def collect_opencode() -> dict:
    """Cota Go via /zen/go/v1/usage. Não puxa o .env do Hermes — chave morta dava 403."""
    token = _opencode_go_token()
    if not token:
        return {
            "ok": False,
            "error": "sem chave Go — faça login no OpenCode (~/.local/share/opencode/auth.json)",
            "skipWatch": True,
        }
    status, body = http(
        "GET",
        OPENCODE_USAGE_URL,
        {
            "Authorization": f"Bearer {token}",
            "User-Agent": UA,
            "Accept": "application/json",
        },
        timeout=12,
    )
    if status in (401, 403):
        return {"ok": False, "error": "chave Go recusada — faça login de novo no OpenCode", "skipWatch": True}
    if status != 200 or not isinstance(body, dict):
        return {"ok": False, "error": f"OpenCode usage HTTP {status}"}
    usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
    out = {"ok": True}
    for period in ("rolling", "weekly", "monthly"):
        window = usage.get(period) if isinstance(usage.get(period), dict) else {}
        out[period] = {
            "percent": window.get("percent"),
            "resetsAt": window.get("resetsAt"),
        }
    return out


def collect_opencode_goat() -> tuple[dict, dict]:
    oc_row = fill_opencode_row(collect_opencode())
    cc_row = fill_command_row(collect_commandcode())
    return oc_row, cc_row


def _codex_binary() -> str | None:
    for path in CODEX_BINARIES:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


def _codex_send(proc: subprocess.Popen, payload: dict) -> None:
    assert proc.stdin is not None
    proc.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
    proc.stdin.flush()


def _codex_read_ids(
    proc: subprocess.Popen,
    required: set[int],
    optional: set[int],
    deadline: float,
) -> dict[int, dict]:
    assert proc.stdout is not None
    want = set(required) | set(optional)
    found: dict[int, dict] = {}
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            if required <= found.keys():
                return found
            raise TimeoutError("codex app-server timeout")
        if required <= found.keys() and optional <= found.keys():
            return found
        ready, _, _ = select.select([proc.stdout], [], [], max(0.05, remaining))
        if not ready:
            continue
        line = proc.stdout.readline()
        if not line:
            if proc.poll() is not None:
                if required <= found.keys():
                    return found
                raise RuntimeError("codex app-server encerrou")
            continue
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(msg, dict):
            continue
        rid = msg.get("id")
        if rid in want:
            found[int(rid)] = msg


def _codex_window_label(minutes: int) -> str:
    if minutes == CODEX_WEEKLY_MINUTES:
        return "Semanal"
    if minutes == CODEX_FIVE_HOUR_MINUTES:
        return "Sessão 5h"
    if minutes > 0 and minutes % 60 == 0:
        hours = minutes // 60
        if hours == 1:
            return "Sessão 1h"
        return f"Sessão {hours}h"
    return f"Janela {minutes} min"


def _codex_windows_from_snapshot(snapshot: dict) -> list[dict]:
    windows = []
    for key in ("primary", "secondary"):
        win = snapshot.get(key)
        if not isinstance(win, dict):
            continue
        minutes = win.get("windowDurationMins")
        used = win.get("usedPercent")
        if minutes is None or used is None:
            continue
        try:
            minutes_i = int(minutes)
            used_f = float(used)
        except (TypeError, ValueError):
            continue
        if minutes_i <= 0 or not (used_f == used_f):  # NaN check
            continue
        remaining = max(0.0, min(100.0, 100.0 - used_f))
        windows.append(
            {
                "label": _codex_window_label(minutes_i),
                "minutes": minutes_i,
                "usedPercent": max(0.0, min(100.0, used_f)),
                "remaining": remaining,
                "resetsAt": iso(win.get("resetsAt")),
            }
        )
    return windows


def _codex_details_from_windows(windows: list[dict]) -> tuple[list[dict], float]:
    weekly = next((w for w in windows if w["minutes"] == CODEX_WEEKLY_MINUTES), None)
    five = next((w for w in windows if w["minutes"] == CODEX_FIVE_HOUR_MINUTES), None)
    ordered = []
    if weekly:
        ordered.append(weekly)
    if five:
        ordered.append(five)
    for win in windows:
        if win is weekly or win is five:
            continue
        ordered.append(win)
    details = []
    for win in ordered:
        details.append(
            {
                "label": win["label"],
                "usedPercent": win["usedPercent"],
                "resetsAt": win["resetsAt"],
                "windowSeconds": win["minutes"] * 60,
            }
        )
    ring = weekly["usedPercent"] if weekly else (max(w["usedPercent"] for w in windows) if windows else 0.0)
    return details, ring


def _jwt_expired(token: str, now: float | None = None) -> bool:
    """Hint local do exp. O servidor valida; falha de parse não mata a cota."""
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return False
        payload = parts[1].replace("-", "+").replace("_", "/")
        payload += "=" * ((4 - len(payload) % 4) % 4)
        data = json.loads(base64.b64decode(payload))
        exp = data.get("exp")
        if exp is None:
            return False
        return float(exp) <= (now if now is not None else time.time())
    except Exception:
        return False


def _codex_auth_credential(auth_path: str | None = None, now: float | None = None) -> tuple[str, str] | None:
    """Lê ~/.codex/auth.json no mesmo shape do Codenotch. Nunca imprime o token."""
    try:
        with open(auth_path or CODEX_AUTH, encoding="utf-8") as fh:
            root = json.load(fh)
        tokens = root.get("tokens") if isinstance(root, dict) else None
        if not isinstance(tokens, dict):
            return None
        access = str(tokens.get("access_token") or "").strip()
        account = str(tokens.get("account_id") or "").strip()
        if not access or not account:
            return None
        if _jwt_expired(access, now=now):
            return None
        return access, account
    except Exception:
        return None


def _codex_day_key(day: dt.date) -> str:
    return f"{day.year:04d}-{day.month:02d}-{day.day:02d}"


def _codex_last_30_days(buckets: list[dict], today: dt.date) -> list[int]:
    by_day = {}
    for bucket in buckets:
        key = bucket.get("start_date")
        if not isinstance(key, str):
            continue
        try:
            by_day[key] = int(bucket.get("tokens") or 0)
        except (TypeError, ValueError):
            continue
    daily = []
    for offset in range(30):
        day = today - dt.timedelta(days=29 - offset)
        daily.append(int(by_day.get(_codex_day_key(day), 0)))
    return daily


def _codex_usage_today(buckets: list[dict], today: dt.date) -> int | None:
    """Bucket do dia ausente = pendente. Zero presente = zero real."""
    key = _codex_day_key(today)
    for bucket in buckets:
        if bucket.get("start_date") == key:
            try:
                return int(bucket.get("tokens") or 0)
            except (TypeError, ValueError):
                return 0
    return None


def _codex_clean_buckets(raw) -> list[dict]:
    if not isinstance(raw, list):
        return []
    out = []
    for bucket in raw:
        if not isinstance(bucket, dict):
            continue
        start = bucket.get("start_date")
        if not isinstance(start, str) or not start:
            continue
        try:
            tokens = int(bucket.get("tokens") or 0)
        except (TypeError, ValueError):
            continue
        out.append({"start_date": start, "tokens": tokens})
    return out


def _codex_profile_payload(raw: dict, today: dt.date | None = None) -> dict | None:
    """Parse de /wham/profiles/me — números crus, sem rede."""
    if not isinstance(raw, dict):
        return None
    stats = raw.get("stats")
    if not isinstance(stats, dict):
        return None
    day = today or dt.date.today()
    buckets = _codex_clean_buckets(stats.get("daily_usage_buckets"))
    daily = _codex_last_30_days(buckets, day)
    peak = stats.get("peak_daily_tokens")
    try:
        peak_i = int(peak) if peak is not None else (max((b["tokens"] for b in buckets), default=None))
    except (TypeError, ValueError):
        peak_i = max((b["tokens"] for b in buckets), default=None)
    return {
        "lifetimeTokens": _int_or_none(stats.get("lifetime_tokens")),
        "peakDailyTokens": peak_i,
        "longestChatSeconds": _float_or_none(stats.get("longest_running_turn_sec")),
        "currentStreakDays": _int_or_none(stats.get("current_streak_days")),
        "longestStreakDays": _int_or_none(stats.get("longest_streak_days")),
        "todayTokens": _codex_usage_today(buckets, day),
        "thirtyDayTokens": sum(daily),
        "daily": daily,
    }


def _int_or_none(value):
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_or_none(value):
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    return number


def _codex_load_profile_cache(path: str) -> dict | None:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _codex_save_profile_cache(path: str, payload: dict | None, fetched_at: float, backoff_until: float | None = None) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        body = {
            "fetchedAt": fetched_at,
            "payload": payload,
            "backoffUntil": backoff_until,
        }
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(body, fh, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        pass


def _codex_fetch_profile(
    auth_path: str | None = None,
    http_fn=None,
    today: dt.date | None = None,
    now: float | None = None,
    cache_path: str | None = None,
    cache_ttl: float = CODEX_PROFILE_TTL,
    timeout: float = 8,
) -> dict | None:
    """GET /wham/profiles/me. Cache 5 min; 429 recua. Falha some o bloco."""
    clock = now if now is not None else time.time()
    path = cache_path or CODEX_PROFILE_CACHE
    cached = _codex_load_profile_cache(path)
    cached_payload = None
    if cached:
        raw_payload = cached.get("payload")
        if isinstance(raw_payload, dict):
            cached_payload = raw_payload
        backoff = cached.get("backoffUntil")
        try:
            backoff_f = float(backoff) if backoff is not None else 0.0
        except (TypeError, ValueError):
            backoff_f = 0.0
        if backoff_f > clock:
            return cached_payload
        fetched = cached.get("fetchedAt")
        try:
            fetched_f = float(fetched) if fetched is not None else 0.0
        except (TypeError, ValueError):
            fetched_f = 0.0
        if cached_payload is not None and cache_ttl > 0 and (clock - fetched_f) < cache_ttl:
            return cached_payload

    cred = _codex_auth_credential(auth_path, now=clock)
    if not cred:
        return cached_payload
    access, account = cred
    fn = http_fn or http
    try:
        status, body = fn(
            "GET",
            CODEX_PROFILE_URL,
            {
                "Authorization": f"Bearer {access}",
                "ChatGPT-Account-Id": account,
                "Accept": "application/json",
                "Cache-Control": "no-cache, no-store",
            },
            timeout=timeout,
        )
    except Exception:
        return cached_payload
    if status == 429:
        _codex_save_profile_cache(path, cached_payload, fetched_at=clock, backoff_until=clock + 60)
        return cached_payload
    if status < 200 or status >= 300 or not isinstance(body, dict):
        return cached_payload
    payload = _codex_profile_payload(body, today=today)
    if payload:
        _codex_save_profile_cache(path, payload, fetched_at=clock)
    return payload


def collect_codex_live() -> dict | None:
    binary = _codex_binary()
    if not binary:
        return None
    proc = subprocess.Popen(
        [binary, "app-server", "--stdio"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
        start_new_session=True,
    )
    try:
        deadline = time.time() + 15
        _codex_send(
            proc,
            {
                "id": 1,
                "method": "initialize",
                "params": {
                    "clientInfo": {
                        "name": "usage-dock",
                        "title": "Usage Dock",
                        "version": "0.1.0",
                    },
                    "capabilities": {"experimentalApi": True},
                },
            },
        )
        init = _codex_read_ids(proc, {1}, set(), deadline)
        if "error" in init.get(1, {}) or "result" not in init.get(1, {}):
            return None
        _codex_send(proc, {"method": "initialized"})
        _codex_send(proc, {"id": 2, "method": "account/rateLimits/read"})
        _codex_send(proc, {"id": 4, "method": "account/read", "params": {"refreshToken": False}})
        batch = _codex_read_ids(proc, {2}, {4}, deadline)
        rate_msg = batch.get(2) or {}
        if "result" not in rate_msg:
            return None
        result = rate_msg["result"] or {}
        snapshot = result.get("rateLimits") or {}
        by_id = result.get("rateLimitsByLimitId")
        if isinstance(by_id, dict) and isinstance(by_id.get("codex"), dict):
            snapshot = by_id["codex"]
        windows = _codex_windows_from_snapshot(snapshot)
        if not windows:
            return None
        account_msg = batch.get(4) or {}
        account = ((account_msg.get("result") or {}) if isinstance(account_msg.get("result"), dict) else {}).get("account") or {}
        plan = str(account.get("planType") or "").strip()
        details, ring = _codex_details_from_windows(windows)
        remaining = deadline - time.time()
        profile = (
            _codex_fetch_profile(timeout=max(2.0, remaining - 1.0))
            if remaining > 3
            else None
        )
        note_parts = ["via Codex CLI"]
        chip = plan_chip(plan)
        if chip:
            note_parts.append(chip)
        elif plan:
            note_parts.append(plan)
        out = row("codex", "Codex")
        out.update(
            ok=True,
            usedPercent=ring,
            details=details,
            plan=chip,
            note=" · ".join(note_parts),
        )
        if profile:
            out["profile"] = profile
        return out
    except Exception:
        return None
    finally:
        try:
            proc.kill()
            proc.wait(timeout=2)
        except Exception:
            pass


def collect_codex_history() -> dict:
    out = row("codex", "Codex")
    if not os.path.isdir(CODEX_HISTORY):
        out["error"] = "Codex CLI/Limits indisponível"
        return apply_unwatch(out)
    newest = None
    newest_mtime = -1.0
    for root, _, files in os.walk(CODEX_HISTORY):
        for name in files:
            if not name.endswith(".json") or name.startswith("."):
                continue
            path = os.path.join(root, name)
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                continue
            if mtime > newest_mtime:
                newest_mtime = mtime
                newest = path
    if not newest:
        out["error"] = "histórico CodexLimits vazio"
        return apply_unwatch(out)
    try:
        data = json.load(open(newest))
    except Exception as e:
        out["error"] = f"histórico ilegível: {e}"
        return out
    samples = data.get("samples") or []
    if not samples:
        out["error"] = "sem amostras Codex hoje"
        return out
    last = samples[-1]
    remaining = float(last.get("remainingPercent") or 0)
    used = max(0.0, min(100.0, 100.0 - remaining))
    observed = last.get("observedAt")
    stale = False
    if observed is not None:
        try:
            observed_dt = APPLE_EPOCH + dt.timedelta(seconds=float(observed))
            stale = (dt.datetime.now(dt.timezone.utc) - observed_dt) > dt.timedelta(minutes=25)
        except Exception:
            stale = False
    details = [
        {
            "label": "Semanal",
            "usedPercent": used,
            "resetsAt": iso(last.get("resetsAt")),
            "windowSeconds": CODEX_WEEKLY_MINUTES * 60,
        }
    ]
    out.update(
        ok=True,
        usedPercent=used,
        stale=stale,
        details=details,
        note="via Codex Limits"
        + (" · dado parado" if stale else "")
        + " · sem sessão 5h ao vivo",
    )
    return out


def _codex_windows_from_usage(body: dict) -> list[dict]:
    """Janelas do /wham/usage — mesmo dado do account/rateLimits/read."""
    rate = body.get("rate_limit") if isinstance(body.get("rate_limit"), dict) else {}
    windows = []
    for key in ("primary_window", "secondary_window"):
        win = rate.get(key)
        if not isinstance(win, dict):
            continue
        seconds = win.get("limit_window_seconds")
        used = win.get("used_percent")
        if seconds is None or used is None:
            continue
        try:
            minutes_i = int(round(float(seconds) / 60))
            used_f = float(used)
        except (TypeError, ValueError):
            continue
        if minutes_i <= 0 or not (used_f == used_f):  # NaN check
            continue
        windows.append(
            {
                "label": _codex_window_label(minutes_i),
                "minutes": minutes_i,
                "usedPercent": max(0.0, min(100.0, used_f)),
                "remaining": max(0.0, min(100.0, 100.0 - used_f)),
                "resetsAt": iso(win.get("reset_at")),
            }
        )
    return windows


def collect_codex_http() -> dict | None:
    """GET /wham/usage com o token do ~/.codex/auth.json — ~1s contra ~12s do app-server."""
    cred = _codex_auth_credential()
    if not cred:
        return None
    access, account = cred
    try:
        status, body = http(
            "GET",
            CODEX_USAGE_URL,
            {
                "Authorization": f"Bearer {access}",
                "ChatGPT-Account-Id": account,
                "Accept": "application/json",
                "Cache-Control": "no-cache, no-store",
            },
            timeout=6,
        )
    except Exception:
        return None
    if status < 200 or status >= 300 or not isinstance(body, dict):
        return None
    windows = _codex_windows_from_usage(body)
    if not windows:
        return None
    plan = str(body.get("plan_type") or "").strip()
    details, ring = _codex_details_from_windows(windows)
    note_parts = ["via ChatGPT API"]
    chip = plan_chip(plan)
    if chip:
        note_parts.append(chip)
    elif plan:
        note_parts.append(plan)
    out = row("codex", "Codex")
    out.update(
        ok=True,
        usedPercent=ring,
        details=details,
        plan=chip,
        note=" · ".join(note_parts),
    )
    profile = _codex_fetch_profile()
    if profile:
        out["profile"] = profile
    return out


def collect_codex() -> dict:
    fast = collect_codex_http()
    if fast and fast.get("ok"):
        return fast
    if os.path.isfile(CODEX_AUTH):
        live = collect_codex_live()
        if live and live.get("ok"):
            return live
    history = collect_codex_history()
    if history.get("ok"):
        return history
    if not os.path.isfile(CODEX_AUTH):
        out = row("codex", "Codex", error="Codex deslogado — rode `codex login`")
        return apply_unwatch(out)
    if not _codex_binary() and _codex_auth_credential() is None:
        return history  # sem CLI e token morto — nada pra vigiar
    # Fonte existe mas não respondeu — anel stale, não park.
    return row("codex", "Codex", error="codex sem resposta", stale=True)


def cursor_auth() -> tuple[str, str]:
    con = sqlite3.connect(f"file:{CURSOR_DB}?mode=ro", uri=True)
    try:
        token_row = con.execute(
            "SELECT value FROM ItemTable WHERE key='cursorAuth/accessToken'"
        ).fetchone()
        plan_row = con.execute(
            "SELECT value FROM ItemTable WHERE key='cursorAuth/stripeMembershipType'"
        ).fetchone()
        token = (token_row[0] if token_row else "") or ""
        plan = (plan_row[0] if plan_row else "") or ""
        return token, plan
    finally:
        con.close()


def _percent_from_message(message: str | None) -> float | None:
    if not message:
        return None
    match = re.search(r"used\s+(\d+(?:\.\d+)?)\s*%", message, re.I)
    if not match:
        match = re.search(r"(\d+(?:\.\d+)?)\s*%", message)
    if not match:
        return None
    return max(0.0, min(100.0, float(match.group(1))))


def collect_cursor() -> dict:
    out = row("cursor", "Cursor")
    try:
        token, membership = cursor_auth()
    except Exception as e:
        out["error"] = f"state.vscdb: {e}"
        return out
    if not token:
        out["error"] = "Cursor deslogado"
        return apply_unwatch(out)
    plan_label = CURSOR_PLAN_LABELS.get(membership.strip().lower(), membership.strip() or None)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Connect-Protocol-Version": "1",
        "User-Agent": UA,
        "Origin": "https://cursor.com",
    }
    status, body = http(
        "POST",
        "https://api2.cursor.sh/aiserver.v1.DashboardService/GetCurrentPeriodUsage",
        headers,
        {},
    )
    if status != 200 or not isinstance(body, dict):
        out["error"] = f"Cursor usage HTTP {status}"
        if status in (401, 403):
            out["skipWatch"] = True
        return apply_unwatch(out)
    plan = body.get("planUsage") or {}
    auto_msg = body.get("autoModelSelectedDisplayMessage")
    auto_pct = _percent_from_message(auto_msg)
    if auto_pct is None and plan.get("autoPercentUsed") is not None:
        auto_pct = float(plan["autoPercentUsed"])
    api_msg = body.get("namedModelSelectedDisplayMessage")
    api_pct = _percent_from_message(api_msg)
    if api_pct is None and plan.get("apiPercentUsed") is not None:
        api_pct = float(plan["apiPercentUsed"])
    # Ring = Cursor Models pool (Auto / Grok / Composer), same franchise the
    # editor settings show. API percent is third-party. displayMessage/includedSpend
    # is a dashboard dollar total, not the "terceiros" bar.
    ring = auto_pct if auto_pct is not None else (api_pct if api_pct is not None else 0.0)
    reset = iso(body.get("billingCycleEnd"))
    cycle_seconds = _seconds_between(body.get("billingCycleStart"), body.get("billingCycleEnd"))
    models = {
        "label": "Modelos Cursor",
        "usedPercent": auto_pct if auto_pct is not None else ring,
        "resetsAt": reset,
        "caption": "franquia Auto / Grok / Composer",
    }
    if cycle_seconds:
        models["windowSeconds"] = cycle_seconds
    details = [models]
    if api_pct is not None:
        third = {
            "label": "Terceiros",
            "usedPercent": api_pct,
            "resetsAt": reset,
            "caption": api_msg or "modelos de terceiros (API)",
        }
        if cycle_seconds:
            third["windowSeconds"] = cycle_seconds
        details.append(third)
    grokbot = collect_cursor_grokbot(headers, body)
    if grokbot:
        details.append(grokbot)
    out.update(
        ok=True,
        usedPercent=ring,
        details=details,
        plan=plan_label,
        note=plan_label,
    )
    return out


def collect_cursor_grokbot(headers: dict, period: dict) -> dict | None:
    start = period.get("billingCycleStart")
    end = period.get("billingCycleEnd")
    payload = {}
    if start:
        payload["startDate"] = str(start)
    if end:
        payload["endDate"] = str(end)
    status, body = http(
        "POST",
        "https://api2.cursor.sh/aiserver.v1.DashboardService/GetAggregatedUsageEvents",
        headers,
        payload,
    )
    if status != 200 or not isinstance(body, dict):
        return None
    items = (
        body.get("aggregations")
        or body.get("aggregatedUsage")
        or body.get("usageEvents")
        or body.get("items")
        or []
    )
    if isinstance(body.get("aggregationsByModel"), dict):
        items = [{"model": k, **(v if isinstance(v, dict) else {})} for k, v in body["aggregationsByModel"].items()]
    grok_cost = 0.0
    total_cost = 0.0
    grok_hits = 0

    def walk(node):
        nonlocal grok_cost, total_cost, grok_hits
        if isinstance(node, dict):
            model = str(node.get("model") or node.get("modelName") or node.get("name") or "")
            cost = node.get("costCents") or node.get("cost") or node.get("totalCents") or node.get("spend")
            try:
                cost_f = float(cost) if cost is not None else 0.0
            except (TypeError, ValueError):
                cost_f = 0.0
            if cost_f:
                total_cost += cost_f
                if "grok" in model.lower():
                    grok_cost += cost_f
                    grok_hits += 1
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(items if items else body)
    if grok_hits == 0 and grok_cost == 0:
        return {
            "label": "Grokbot",
            "usedPercent": None,
            "resetsAt": iso(period.get("billingCycleEnd")),
            "caption": "mesma cota Cursor",
        }
    pct = (grok_cost / total_cost * 100) if total_cost else 0.0
    return {
        "label": "Grokbot",
        "usedPercent": pct,
        "resetsAt": iso(period.get("billingCycleEnd")),
        "caption": f"{pct:.0f}% do gasto Cursor neste ciclo",
    }


def grok_slot() -> tuple[str, dict]:
    data = json.load(open(GROK_AUTH))
    key = next(iter(data))
    return key, data


def grok_access_token(slot: dict) -> tuple[str, dict, bool]:
    """Return (token, slot, refreshed). Refresh only when expiry is inside 8 min."""
    expires_at = slot.get("expires_at")
    need = True
    if expires_at:
        try:
            exp = dt.datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            need = exp - dt.datetime.now(dt.timezone.utc) < dt.timedelta(minutes=8)
        except Exception:
            need = True
    token = slot.get("key") or ""
    if not need and token:
        return token, slot, False
    refresh = slot.get("refresh_token") or ""
    if not refresh:
        return token, slot, False
    body = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "client_id": slot.get("oidc_client_id") or XAI_CLIENT_ID,
            "refresh_token": refresh,
        }
    ).encode()
    status, payload = http(
        "POST",
        XAI_TOKEN_URL,
        {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": UA,
        },
        body,
    )
    if status != 200 or not isinstance(payload, dict) or not payload.get("access_token"):
        return token, slot, False
    slot = dict(slot)
    slot["key"] = payload["access_token"]
    if payload.get("refresh_token"):
        slot["refresh_token"] = payload["refresh_token"]
    expires_in = payload.get("expires_in") or 3600
    slot["expires_at"] = (
        dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=int(expires_in))
    ).isoformat().replace("+00:00", "Z")
    return slot["key"], slot, True


def persist_grok_slot(file_key: str, slot: dict) -> None:
    os.makedirs(os.path.dirname(GROK_AUTH), exist_ok=True)
    lock_fd = os.open(GROK_LOCK, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        import fcntl

        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        current = {}
        if os.path.exists(GROK_AUTH):
            current = json.load(open(GROK_AUTH))
        current[file_key] = slot
        tmp = GROK_AUTH + ".tmp"
        with open(tmp, "w") as f:
            json.dump(current, f, indent=2)
            f.write("\n")
        os.replace(tmp, GROK_AUTH)
    finally:
        import fcntl

        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


def collect_grok() -> dict:
    out = row("grok", "Grok")
    if not os.path.exists(GROK_AUTH):
        out["error"] = "sem ~/.grok/auth.json — faça login no Grok CLI"
        return apply_unwatch(out)
    try:
        file_key, data = grok_slot()
        slot = data[file_key]
        token, slot, refreshed = grok_access_token(slot)
        if refreshed:
            persist_grok_slot(file_key, slot)
    except Exception as e:
        out["error"] = f"auth Grok: {e}"
        return out
    if not token:
        out["error"] = "token Grok vazio"
        return apply_unwatch(out)
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": UA,
        "Accept": "application/json",
        "x-grok-client-surface": "grok-build",
        "x-grok-client-version": "1.0.0",
    }
    status, body = http(
        "GET",
        "https://cli-chat-proxy.grok.com/v1/billing?format=credits",
        headers,
    )
    if status != 200 or not isinstance(body, dict):
        out["error"] = f"Grok billing HTTP {status}"
        if status in (401, 403):
            out["skipWatch"] = True
        return apply_unwatch(out)
    cfg = body.get("config") or body
    pct = cfg.get("creditUsagePercent")
    if pct is None:
        products = cfg.get("productUsage") or []
        if products:
            pct = products[0].get("usagePercent")
    pct = float(pct or 0)
    period = cfg.get("currentPeriod") or {}
    grok_end = period.get("end") or cfg.get("billingPeriodEnd")
    grok_start = period.get("start") or cfg.get("billingPeriodStart")
    grok_seconds = _seconds_between(grok_start, grok_end)
    weekly = {
        "label": "Semanal",
        "usedPercent": pct,
        "resetsAt": iso(grok_end),
    }
    if grok_seconds:
        weekly["windowSeconds"] = grok_seconds
    details = [weekly]
    on_demand_cap = (cfg.get("onDemandCap") or {}).get("val") or 0
    on_demand_used = (cfg.get("onDemandUsed") or {}).get("val") or 0
    try:
        on_demand_cap_f = float(on_demand_cap)
        on_demand_used_f = float(on_demand_used)
    except (TypeError, ValueError):
        on_demand_cap_f = 0
        on_demand_used_f = 0
    if on_demand_cap_f > 0:
        details.append(
            {
                "label": "Créditos extra",
                "usedPercent": on_demand_used_f / on_demand_cap_f * 100,
                "resetsAt": None,
            }
        )
    out.update(
        ok=True,
        usedPercent=pct,
        details=details,
        plan="SuperGrok",
        note="pool da assinatura Grok",
    )
    return out


def _await_future(fut, timeout: float, fallback):
    """Não deixa um provider travado segurar o JSON inteiro — o HUD congelava."""
    try:
        return fut.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        return fallback
    except Exception as exc:
        if isinstance(fallback, dict) and fallback.get("id"):
            out = dict(fallback)
            out["error"] = str(exc)
            return out
        raise


def _safe_codex() -> dict:
    try:
        return collect_codex()
    except Exception as e:
        return row("codex", "Codex", error=str(e))


def _safe_opencode() -> dict:
    try:
        return fill_opencode_row(collect_opencode())
    except Exception as e:
        return row("opencode", "OpenCode", error=str(e))


def _safe_command() -> dict:
    try:
        return fill_command_row(collect_commandcode())
    except Exception as e:
        return row("goat", "Command", error=str(e))


def _safe_opencode_goat() -> tuple[dict, dict]:
    try:
        return collect_opencode_goat()
    except Exception as e:
        err = str(e)
        return (
            row("opencode", "OpenCode", error=err),
            row("goat", "Command", error=err),
        )


def _safe_cursor() -> dict:
    try:
        return collect_cursor()
    except Exception as e:
        return row("cursor", "Cursor", error=str(e))


def _safe_grok() -> dict:
    try:
        return collect_grok()
    except Exception as e:
        return row("grok", "Grok", error=str(e))


def _devin_credentials() -> tuple[str | None, str | None]:
    """credentials.toml do devin-cli — parse manual pra não depender de tomllib."""
    try:
        with open(DEVIN_CREDS, encoding="utf-8") as fh:
            text = fh.read()
    except Exception:
        return None, None

    def field(name: str) -> str:
        m = re.search(rf'^\s*{name}\s*=\s*"([^"]*)"', text, re.M)
        return m.group(1).strip() if m else ""

    key = field("windsurf_api_key")
    base = field("api_server_url") or "https://server.codeium.com"
    return key or None, base.rstrip("/")


def fill_devin_row(dv: dict) -> dict:
    """Monta o slot Devin a partir do GetUserStatus. Sem rede — testável."""
    dv_row = row("devin", "Devin")
    if not dv.get("ok"):
        dv_row["error"] = dv.get("error") or "Devin indisponível"
        return apply_unwatch({**dv_row, "skipWatch": bool(dv.get("skipWatch"))})
    ps = dv.get("planStatus") if isinstance(dv.get("planStatus"), dict) else {}
    details = []
    pcts = []
    for label, remain_key, reset_key, seconds in (
        ("Diária", "dailyQuotaRemainingPercent", "dailyQuotaResetAtUnix", 86400),
        ("Semanal", "weeklyQuotaRemainingPercent", "weeklyQuotaResetAtUnix", 604800),
    ):
        remain = ps.get(remain_key)
        if remain is None:
            continue
        try:
            used = max(0.0, min(100.0, 100.0 - float(remain)))
        except (TypeError, ValueError):
            continue
        pcts.append(used)
        details.append(
            {
                "label": label,
                "usedPercent": used,
                "resetsAt": iso(ps.get(reset_key)),
                "windowSeconds": seconds,
            }
        )
    cycle_seconds = _seconds_between(ps.get("planStart"), ps.get("planEnd"))
    cycle = {
        "label": "Ciclo",
        "usedPercent": None,
        "resetsAt": iso(ps.get("planEnd")),
    }
    if cycle_seconds:
        cycle["windowSeconds"] = cycle_seconds
    try:
        overage = float(ps.get("overageBalanceMicros") or 0) / 1e6
    except (TypeError, ValueError):
        overage = 0.0
    if overage:
        cycle["caption"] = f"overage ${overage:.2f} no ciclo"
    details.append(cycle)
    plan = dv.get("planName")
    dv_row.update(
        ok=True,
        usedPercent=max(pcts) if pcts else 0.0,
        details=details,
        plan=plan_chip(plan),
        note="via Devin account",
    )
    if dv.get("pro") is False:
        dv_row["cancelled"] = True
    return dv_row


def collect_devin() -> dict:
    """Quota ACU via GetUserStatus no api_server — mesmo envelope ConnectRPC do Cursor."""
    key, base = _devin_credentials()
    if not key:
        return {
            "ok": False,
            "error": "sem API key Devin — rode `devin auth login`",
            "skipWatch": True,
        }
    status, body = http(
        "POST",
        base + "/exa.seat_management_pb.SeatManagementService/GetUserStatus",
        {
            "Content-Type": "application/json",
            "Connect-Protocol-Version": "1",
            "User-Agent": UA,
            "Accept": "application/json",
        },
        {
            "metadata": {
                "apiKey": key,
                "ideName": "devin-cli",
                "ideVersion": "3000.11.1",
                "extensionName": "devin",
                "extensionVersion": "3000.11.1",
                "locale": "en_US",
            }
        },
        timeout=10,
    )
    if status in (401, 403):
        return {"ok": False, "error": "API key Devin recusada — rode `devin auth login`", "skipWatch": True}
    if status != 200 or not isinstance(body, dict):
        return {"ok": False, "error": f"Devin status HTTP {status}"}
    user = body.get("userStatus") if isinstance(body.get("userStatus"), dict) else {}
    ps = user.get("planStatus") if isinstance(user.get("planStatus"), dict) else {}
    info = ps.get("planInfo") if isinstance(ps.get("planInfo"), dict) else {}
    return {
        "ok": True,
        "pro": user.get("pro"),
        "planStatus": ps,
        "planName": info.get("planName"),
    }


def _safe_devin() -> dict:
    try:
        return fill_devin_row(collect_devin())
    except Exception as e:
        return row("devin", "Devin", error=str(e))


def skipped_ids() -> set[str]:
    return {part.strip() for part in os.environ.get("USAGE_DOCK_SKIP", "").split(",") if part.strip()}


def apply_dead(payload: dict) -> dict:
    """Cota 100% ou assinatura cancelada sai do dock como 'sem assinatura'."""
    if not payload.get("ok"):
        return payload
    pid, name = payload["id"], payload["name"]
    if payload.get("cancelled") or str(payload.get("plan") or "") in ("Free", "Hobby"):
        return row(pid, name, error="assinatura cancelada", skipWatch=True)
    try:
        exhausted = float(payload.get("usedPercent") or 0) >= 99.9
    except (TypeError, ValueError):
        exhausted = False
    if exhausted:
        return row(pid, name, error="cota esgotada — assinatura no limite", skipWatch=True)
    return payload


def main() -> None:
    skip = skipped_ids()
    order = ("codex", "opencode", "goat", "cursor", "grok", "devin")
    jobs: dict[str, tuple] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        if "codex" not in skip:
            jobs["codex"] = (
                pool.submit(_safe_codex),
                CODEX_FUTURE_TIMEOUT,
                row("codex", "Codex", error="Codex demorou demais", stale=True),
            )
        if "opencode" not in skip:
            jobs["opencode"] = (
                pool.submit(_safe_opencode),
                PROVIDER_FUTURE_TIMEOUT,
                row("opencode", "OpenCode", error="OpenCode demorou demais", stale=True),
            )
        if "goat" not in skip:
            jobs["goat"] = (
                pool.submit(_safe_command),
                PROVIDER_FUTURE_TIMEOUT,
                row("goat", "Command", error="Command demorou demais", stale=True),
            )
        if "cursor" not in skip:
            jobs["cursor"] = (
                pool.submit(_safe_cursor),
                PROVIDER_FUTURE_TIMEOUT,
                row("cursor", "Cursor", error="Cursor demorou demais", stale=True),
            )
        if "grok" not in skip:
            jobs["grok"] = (
                pool.submit(_safe_grok),
                PROVIDER_FUTURE_TIMEOUT,
                row("grok", "Grok", error="Grok demorou demais", stale=True),
            )
        if "devin" not in skip:
            jobs["devin"] = (
                pool.submit(_safe_devin),
                PROVIDER_FUTURE_TIMEOUT,
                row("devin", "Devin", error="Devin demorou demais", stale=True),
            )
        providers = []
        for pid in order:
            if pid in skip:
                continue
            fut, timeout, fallback = jobs[pid]
            providers.append(apply_dead(apply_unwatch(_await_future(fut, timeout, fallback))))
    print(json.dumps({"ts": time.time(), "providers": providers}, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
