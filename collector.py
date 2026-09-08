#!/usr/bin/env python3
"""Usage Dock collector — Codex, OpenCode Go, Command GOAT, Cursor, SuperGrok.

Reads local credentials already on this Mac. Never prints tokens.
OpenCode/GOAT reuse subscription-widget functions (no history append).
"""
from __future__ import annotations

import concurrent.futures
import datetime as dt
import importlib.util
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
SUB_COLLECTOR = os.path.expanduser("~/Documents/subscription-widget/collector.py")
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
XAI_TOKEN_URL = "https://auth.x.ai/oauth2/token"
XAI_CLIENT_ID = "b1a00492-073a-47ea-816f-4c329264a828"
CODEX_BINARIES = [
    os.path.expanduser("~/.local/bin/codex"),
    "/opt/homebrew/bin/codex",
    "/usr/local/bin/codex",
]
CODEX_WEEKLY_MINUTES = 10_080
CODEX_FIVE_HOUR_MINUTES = 300
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
    }
    base.update(kwargs)
    return base


def load_sub_module():
    spec = importlib.util.spec_from_file_location("subscription_collector", SUB_COLLECTOR)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"não achei {SUB_COLLECTOR}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _opencode_go_token(auth_path: str | None = None) -> str | None:
    """Mesma ordem do Codenotch: env, depois o auth.json do próprio OpenCode."""
    value = os.environ.get("OPENCODE_GO_API_KEY", "").strip()
    if value:
        return value
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


def _prepare_opencode_env() -> None:
    token = _opencode_go_token()
    if token:
        os.environ.setdefault("OPENCODE_GO_API_KEY", token)


def fill_command_row(cc: dict) -> dict:
    """Monta o slot goat a partir do payload /alpha. Sem rede — testável."""
    cc_row = row("goat", "Command")
    if not cc.get("ok"):
        cc_row["error"] = cc.get("error") or "Command Code indisponível"
        return cc_row
    summary = cc.get("summary") if isinstance(cc.get("summary"), dict) else {}
    credits = cc.get("credits") if isinstance(cc.get("credits"), dict) else {}
    windows = cc.get("windowLimits") if isinstance(cc.get("windowLimits"), dict) else {}
    sub = cc.get("subscription") if isinstance(cc.get("subscription"), dict) else {}
    used = float(summary.get("totalCost") or 0)
    remaining = float(credits.get("monthlyCredits") or 0)
    cap = used + remaining if (used or remaining) else 70.0
    monthly_pct = (used / cap * 100) if cap else 0.0
    details = [
        {
            "label": "Mensal",
            "usedPercent": monthly_pct,
            "resetsAt": iso(sub.get("currentPeriodEnd")),
            "caption": f"${used:.2f} de ${cap:.0f} · resta ${remaining:.2f}",
        }
    ]
    for key, label in (("fiveHour", "Sessão 5h"), ("weekly", "Semanal")):
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
    note_parts = []
    if plan:
        note_parts.append(str(plan))
    cc_row.update(
        ok=True,
        usedPercent=monthly_pct,
        details=details,
        plan=plan_chip(plan),
        note=" · ".join(note_parts) if note_parts else None,
    )
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
        }
    try:
        whoami = _commandcode_api("/alpha/whoami", key)
        org = whoami.get("org") if isinstance(whoami.get("org"), dict) else {}
        org_id = org.get("id")
        query = f"?orgId={urllib.parse.quote(str(org_id))}" if org_id else ""
        credits_raw = _commandcode_api(f"/alpha/billing/credits{query}", key)
        subs_raw = _commandcode_api(f"/alpha/billing/subscriptions{query}", key)
        sub = subs_raw.get("data", subs_raw)
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
            "belowThreshold": bool(credits.get("belowThreshold")),
            "breakdownByModel": [],
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def collect_opencode_goat() -> tuple[dict, dict]:
    oc_row = row("opencode", "OpenCode")
    oc = {"ok": False, "error": "OpenCode indisponível"}
    cc = {"ok": False, "error": "Command Code indisponível"}
    try:
        mod = load_sub_module()
        if hasattr(mod, "load_env"):
            mod.load_env()
        _prepare_opencode_env()
        try:
            oc = mod.opencode_go()
        except Exception as e:
            oc = {"ok": False, "error": str(e)}
        try:
            cc = collect_commandcode()
        except Exception as e:
            cc = {"ok": False, "error": str(e)}
    except Exception as e:
        err = str(e)
        return (
            row("opencode", "OpenCode", error=err),
            row("goat", "Command", error=err),
        )
    if oc.get("ok"):
        details = []
        pcts = []
        for key, label in (("rolling", "Rolling"), ("weekly", "Semanal"), ("monthly", "Mensal")):
            p = oc.get(key) or {}
            pct = p.get("percent")
            if pct is None:
                continue
            pcts.append(float(pct))
            details.append(
                {
                    "label": label,
                    "usedPercent": float(pct),
                    "resetsAt": iso(p.get("resetsAt")),
                }
            )
        oc_row.update(ok=True, usedPercent=max(pcts) if pcts else 0.0, details=details, plan="Go")
        note_parts = []
        if oc.get("modelCount"):
            note_parts.append(f"{oc['modelCount']} modelos")
        if pcts:
            note_parts.append(f"anel = pior janela ({max(pcts):.0f}%)")
        if note_parts:
            oc_row["note"] = " · ".join(note_parts)
    else:
        oc_row["error"] = oc.get("error") or "OpenCode indisponível"

    cc_row = fill_command_row(cc)

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


def _codex_details_from_windows(windows: list[dict], lifetime=None) -> tuple[list[dict], float]:
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
        caption = f"{win['remaining']:.0f}% restante"
        details.append(
            {
                "label": win["label"],
                "usedPercent": win["usedPercent"],
                "resetsAt": win["resetsAt"],
                "caption": caption,
            }
        )
    if lifetime is not None:
        try:
            tok = int(lifetime)
            extra = None
            if tok >= 1_000_000_000:
                extra = f"{tok / 1e9:.1f}B tokens"
            elif tok >= 1_000_000:
                extra = f"{tok / 1e6:.0f}M tokens"
            if extra and details:
                details[0]["caption"] = f"{details[0]['caption']} · {extra}"
        except (TypeError, ValueError):
            pass
    ring = weekly["usedPercent"] if weekly else (max(w["usedPercent"] for w in windows) if windows else 0.0)
    return details, ring


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
    )
    try:
        deadline = time.time() + 12
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
        _codex_send(proc, {"id": 3, "method": "account/usage/read"})
        _codex_send(proc, {"id": 4, "method": "account/read", "params": {"refreshToken": False}})
        batch = _codex_read_ids(proc, {2}, {3, 4}, deadline)
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
        usage_msg = batch.get(3) or {}
        lifetime = None
        usage_result = usage_msg.get("result") if isinstance(usage_msg.get("result"), dict) else {}
        summary = (usage_result or {}).get("summary") or {}
        lifetime = summary.get("lifetimeTokens")
        account_msg = batch.get(4) or {}
        account = ((account_msg.get("result") or {}) if isinstance(account_msg.get("result"), dict) else {}).get("account") or {}
        plan = str(account.get("planType") or "").strip()
        details, ring = _codex_details_from_windows(windows, lifetime)
        note_parts = ["via Codex CLI"]
        if plan:
            note_parts.append(plan)
        out = row("codex", "Codex")
        out.update(
            ok=True,
            usedPercent=ring,
            details=details,
            plan=plan_chip(plan),
            note=" · ".join(note_parts),
        )
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
        return out
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
        return out
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
            "caption": f"{remaining:.0f}% restante",
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


def collect_codex() -> dict:
    live = collect_codex_live()
    if live and live.get("ok"):
        return live
    return collect_codex_history()


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
        return out
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
        return out
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
    details = [
        {
            "label": "Modelos Cursor",
            "usedPercent": auto_pct if auto_pct is not None else ring,
            "resetsAt": reset,
            "caption": "franquia Auto / Grok / Composer",
        }
    ]
    if api_pct is not None:
        details.append(
            {
                "label": "Terceiros",
                "usedPercent": api_pct,
                "resetsAt": reset,
                "caption": api_msg or "modelos de terceiros (API)",
            }
        )
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
        return out
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
        return out
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
        return out
    cfg = body.get("config") or body
    pct = cfg.get("creditUsagePercent")
    if pct is None:
        products = cfg.get("productUsage") or []
        if products:
            pct = products[0].get("usagePercent")
    pct = float(pct or 0)
    period = cfg.get("currentPeriod") or {}
    details = [
        {
            "label": "Semanal SuperGrok",
            "usedPercent": pct,
            "resetsAt": iso(period.get("end") or cfg.get("billingPeriodEnd")),
        }
    ]
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


def _safe_codex() -> dict:
    try:
        return collect_codex()
    except Exception as e:
        return row("codex", "Codex", error=str(e))


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


def main() -> None:
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        f_codex = pool.submit(_safe_codex)
        f_oc_goat = pool.submit(_safe_opencode_goat)
        f_cursor = pool.submit(_safe_cursor)
        f_grok = pool.submit(_safe_grok)
        codex = f_codex.result()
        oc, goat = f_oc_goat.result()
        cursor = f_cursor.result()
        grok = f_grok.result()
    providers = [codex, oc, goat, cursor, grok]
    print(json.dumps({"ts": time.time(), "providers": providers}, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
