# How to add a provider

This guide adds an eighth ring to the dock. The steps touch `collector.py`, one test file, two Swift files, and one SVG. The examples use an invented provider named Acme with the id `acme`.

Read [ARCHITECTURE.md](ARCHITECTURE.md) first if you do not know the JSON contract.

## Before you write code

Find two facts about the provider.

- Where the provider's own tool keeps the login on the Mac. Name the file and the field.
- Which request returns the usage, and what the response looks like.

Never copy a real token into the code, a test, an issue, or a commit.

## Add the reader to the collector

1. Add the constants near the other provider constants at the top of `collector.py`.

   ```python
   ACME_AUTH = os.path.expanduser("~/.acme/auth.json")
   ACME_USAGE_URL = "https://api.acme.example/v1/usage"
   ```

2. Write `collect_acme`. It reads the login, calls the API, and returns raw data. Set `skipWatch` when the user has no login, so the ring leaves the dock.

   ```python
   def collect_acme() -> dict:
       """Reads the login and calls the usage endpoint. Returns raw data, not a row."""
       try:
           with open(ACME_AUTH, encoding="utf-8") as fh:
               token = str(json.load(fh).get("token") or "").strip()
       except Exception:
           token = ""
       if not token:
           return {"ok": False, "error": "sem login Acme", "skipWatch": True}
       status, body = http(
           "GET",
           ACME_USAGE_URL,
           {"Authorization": f"Bearer {token}", "Accept": "application/json"},
       )
       if status in (401, 403):
           return {"ok": False, "error": "login Acme recusado", "skipWatch": True}
       if status != 200 or not isinstance(body, dict):
           return {"ok": False, "error": f"Acme usage HTTP {status}"}
       return {"ok": True, "usage": body}
   ```

3. Write `fill_acme_row`. It turns the raw data into a row and uses no network. If the response lacks the value, return an error. Do not fall back to zero, because a ring at 0% looks like an unused quota.

   ```python
   def fill_acme_row(raw: dict) -> dict:
       """Builds the row from the raw data. No network, so a test can call it."""
       out = row("acme", "Acme")
       if not raw.get("ok"):
           out["error"] = raw.get("error") or "Acme indisponível"
           return apply_unwatch({**out, "skipWatch": bool(raw.get("skipWatch"))})
       usage = raw.get("usage") if isinstance(raw.get("usage"), dict) else {}
       weekly = usage.get("weekly")
       if not isinstance(weekly, dict) or weekly.get("percent") is None:
           out["error"] = "Acme sem janelas de uso"
           return out
       used = max(0.0, min(100.0, float(weekly["percent"])))
       out.update(
           ok=True,
           usedPercent=used,
           details=[
               {
                   "label": "Semanal",
                   "usedPercent": used,
                   "resetsAt": iso(weekly.get("resetsAt")),
                   "windowSeconds": 604800,
               }
           ],
           plan=plan_chip(usage.get("plan")),
       )
       return out
   ```

4. Write `_safe_acme`. It turns any exception into a row with an error.

   ```python
   def _safe_acme() -> dict:
       try:
           return fill_acme_row(collect_acme())
       except Exception as e:
           return row("acme", "Acme", error=str(e))
   ```

5. Register the provider in `main`. Add the id to `order`, raise `max_workers` from 7 to 8, and add the job.

   ```python
   order = ("codex", "opencode", "goat", "cursor", "grok", "devin", "claude", "acme")
   ```

   ```python
   if "acme" not in skip:
       jobs["acme"] = (
           pool.submit(_safe_acme),
           PROVIDER_FUTURE_TIMEOUT,
           row("acme", "Acme", error="Acme demorou demais", stale=True),
       )
   ```

The helpers that the example uses are already in `collector.py`.

| Helper | Purpose |
|---|---|
| `http` | Sends a request and returns the status and the decoded JSON. It returns an HTTP error as a status. It raises on a network failure, which `_safe_acme` catches |
| `row` | Builds a row with every key of the JSON contract |
| `iso` | Converts an ISO string or a Unix time to ISO 8601 in the local time zone |
| `plan_chip` | Converts a plan id to a short label. Add new labels to `PLAN_LABELS` |
| `apply_unwatch` | Sets `skipWatch` when the row asks for it, or when the error text matches `UNWATCH_HINTS` |

Follow these rules in the row.

- Give each entry of `details` a different `label`.
- Add `windowSeconds` and `resetsAt` to a window when you know them. The card needs both to show the pace.
- Write the labels and the error messages in Brazilian Portuguese, like the other providers. Do not use em dashes.
- Do not write to the provider's login file. If the token expired, return an error that tells the user to open the provider's tool.

## Test the reader

Add a test class to `tests/test_collector.py`. Call `fill_acme_row` with sample payloads. Use invented values, never a real response with account data.

```python
class AcmeRowTests(unittest.TestCase):
    def test_weekly_window(self):
        out = c.fill_acme_row(
            {"ok": True, "usage": {"plan": "pro", "weekly": {"percent": 37.5, "resetsAt": "2026-11-20T12:00:00Z"}}}
        )
        self.assertTrue(out["ok"])
        self.assertEqual(out["usedPercent"], 37.5)
        self.assertEqual(out["details"][0]["label"], "Semanal")
        self.assertEqual(out["plan"], "Pro")

    def test_missing_login_leaves_the_dock(self):
        out = c.fill_acme_row({"ok": False, "error": "sem login Acme", "skipWatch": True})
        self.assertFalse(out["ok"])
        self.assertTrue(out["skipWatch"])

    def test_missing_window_is_an_error_not_zero(self):
        out = c.fill_acme_row({"ok": True, "usage": {}})
        self.assertFalse(out["ok"])
        self.assertIsNone(out["usedPercent"])
```

Run the tests, then run the collector with every other provider skipped.

```sh
python3 -m unittest discover -s tests
USAGE_DOCK_SKIP=codex,opencode,goat,cursor,grok,devin,claude python3 collector.py
```

The collector prints one row with the id `acme`. Check that the row contains no token.

## Add the ring to the app

1. Add the row to `ProviderUsage.placeholders` in `UsageDock/Sources/UsageDock/Models.swift`. The position in this list is the position of the ring in the dock.

   ```swift
   ProviderUsage(id: "acme", name: "Acme", ok: false, usedPercent: nil, details: [], note: nil, plan: nil, error: nil, stale: false, sessions: nil)
   ```

2. Add the case to `BrandID` in `UsageDock/Sources/UsageDock/BrandMarks.swift`.

   ```swift
   case codex, opencode, goat, cursor, grok, devin, claude, acme
   ```

3. Handle the case in the two `switch` statements of `BrandMark`, in `body` and in `opticalScale`. Until you do, the build fails with `switch must be exhaustive`.

   ```swift
   case .acme:
       BundledSVGMark(name: "acme", tone: tone)
   ```

4. Add the logo as `UsageDock/Sources/UsageDock/Resources/acme.svg`. Use a one-color SVG. The app draws it as a template image, white on the dock and black under the pointer. `scripts/build.sh` copies every SVG in that folder into the app bundle.

No other Swift file needs a change. The dock grows with the number of rows, and the card draws whatever the row contains.

## Check the result

1. Build the app.

   ```sh
   cd UsageDock && swift build -c release
   ```

2. Install and open the app as [CONTRIBUTING.md](../CONTRIBUTING.md) describes, and check the ring and its card by hand.

## Update the documents

- The provider tables and the privacy tables in `README.md` and `README.pt-BR.md`.
- The provider table in `docs/ARCHITECTURE.md`, and the list of ids in the row table.
- The list of ids in `AGENTS.md` and in `llms.txt`.
- The provider list in `.github/ISSUE_TEMPLATE/bug_report.yml`.
- The logo table in `THIRD_PARTY_NOTICES.md`. Record where the logo file came from.
- `CHANGELOG.md`.
