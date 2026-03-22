#!/usr/bin/env python3
"""
Groundswell Approval Executor — posts approved content automatically.

Checks telegram_approvals for items with decision='approve', attempts
to post them (API first, Playwright fallback), and marks them complete.

Zero Claude cost — pure Python.

Usage:
    python3 tools/approval_executor.py run
    python3 tools/approval_executor.py status
"""

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone

from _common import DB_PATH, emit, fail, now_iso, get_db


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def extract_post_id(approval_id):
    """Extract tweet/post ID from approval_id like 'reply:handle:POST_ID'."""
    parts = approval_id.split(":")
    if len(parts) >= 3:
        return parts[-1]
    return None


def extract_handle(text):
    """Extract @handle from approval text."""
    match = re.search(r"@(\w+)", text or "")
    return match.group(1) if match else None


def extract_draft_from_text(text):
    """Try to extract the draft reply from the approval text.

    Agents sometimes embed the draft in the text field after markers like:
    'Draft:', 'Reply:', 'Proposed reply:', etc.
    """
    if not text:
        return None

    # Look for common draft markers
    markers = [
        r"(?:Draft|Proposed reply|Reply text|Brad's reply|QT text|Quote text):\s*[\"']?(.*?)(?:[\"']?\s*$)",
        r"Reply shares Brad's.*?:\s*[\"](.*?)[\"]",
    ]
    for pattern in markers:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            draft = match.group(1).strip()
            if len(draft) > 10:
                return draft

    return None


def attempt_post(approval_id, text, handle, post_id):
    """Try to post via API, fall back to Playwright."""
    if not text:
        return {"success": False, "error": "no_draft_text", "method": None}

    tweet_url = f"https://x.com/{handle}/status/{post_id}" if handle and post_id else None

    # Determine if this is a reply, QT, or original post
    is_reply = "reply" in approval_id.lower() or "inbound" in approval_id.lower() or "community" in approval_id.lower()
    is_qt = "qt:" in approval_id.lower() or "quote" in approval_id.lower()

    if is_reply and post_id:
        # Try API reply first
        try:
            result = subprocess.run(
                ["python3", "tools/post.py", "x", "--text", text, "--reply-to", post_id],
                capture_output=True, text=True, timeout=30,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            api_result = json.loads(result.stdout) if result.stdout else {}

            if api_result.get("ok"):
                return {"success": True, "method": "api", "post_id": api_result.get("post_id")}

            # Check for 403 — fall back to Playwright
            if api_result.get("error") == "forbidden" or api_result.get("error") == 403:
                if tweet_url:
                    pw_result = subprocess.run(
                        ["python3", "tools/x_browser.py", "reply", "--url", tweet_url, "--text", text],
                        capture_output=True, text=True, timeout=60,
                        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    )
                    pw_data = json.loads(pw_result.stdout) if pw_result.stdout else {}
                    if pw_data.get("success"):
                        return {"success": True, "method": "playwright"}
                    return {"success": False, "error": f"playwright_failed: {pw_data.get('error')}", "method": "playwright"}

                return {"success": False, "error": "api_403_no_tweet_url", "method": "api"}

            return {"success": False, "error": f"api_error: {api_result}", "method": "api"}
        except Exception as e:
            return {"success": False, "error": str(e), "method": "api"}

    elif is_qt and post_id and tweet_url:
        # Quote tweet via Playwright (API QTs often fail too)
        try:
            pw_result = subprocess.run(
                ["python3", "tools/x_browser.py", "quote", "--url", tweet_url, "--text", text],
                capture_output=True, text=True, timeout=60,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            pw_data = json.loads(pw_result.stdout) if pw_result.stdout else {}
            if pw_data.get("success"):
                return {"success": True, "method": "playwright"}
            return {"success": False, "error": f"playwright_qt_failed: {pw_data.get('error')}", "method": "playwright"}
        except Exception as e:
            return {"success": False, "error": str(e), "method": "playwright"}

    else:
        # Original post
        try:
            result = subprocess.run(
                ["python3", "tools/post.py", "x", "--text", text],
                capture_output=True, text=True, timeout=30,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            api_result = json.loads(result.stdout) if result.stdout else {}
            if api_result.get("ok"):
                return {"success": True, "method": "api", "post_id": api_result.get("post_id")}
            return {"success": False, "error": f"api_error: {api_result}", "method": "api"}
        except Exception as e:
            return {"success": False, "error": str(e), "method": "api"}


def _poll_telegram_callbacks(conn):
    """Poll Telegram for callback button taps and record decisions."""
    import urllib.request
    import urllib.error

    env_keys = {}
    try:
        from _x_auth import load_env as _load_env
        env_keys = _load_env(keys=["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"])
    except Exception:
        pass

    token = env_keys.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return 0

    # Get last processed update ID
    row = conn.execute(
        "SELECT value FROM telegram_state WHERE key = 'last_update_id'"
    ).fetchone()
    last_id = int(row["value"]) if row else 0

    payload = json.dumps({"timeout": 0, "offset": last_id + 1 if last_id else None}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/getUpdates",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return 0

    updates = data.get("result", [])
    decisions_recorded = 0
    max_id = last_id

    for update in updates:
        uid = update["update_id"]
        if uid > max_id:
            max_id = uid

        cb = update.get("callback_query")
        if not cb:
            continue

        cb_data = cb.get("data", "")
        if ":" not in cb_data:
            continue

        action, approval_id = cb_data.split(":", 1)
        if action not in ("approve", "reject"):
            continue

        ts = now_iso()

        # Update the approval record
        cur = conn.execute(
            "UPDATE telegram_approvals SET decision = ?, responded_at = ? "
            "WHERE approval_id = ? AND decision IS NULL",
            (action, ts, approval_id),
        )

        if cur.rowcount > 0:
            decisions_recorded += 1

        # Answer the callback to dismiss the spinner
        try:
            answer_payload = json.dumps({
                "callback_query_id": cb["id"],
                "text": f"Got it: {action}",
            }).encode()
            answer_req = urllib.request.Request(
                f"https://api.telegram.org/bot{token}/answerCallbackQuery",
                data=answer_payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(answer_req, timeout=5)
        except Exception:
            pass

    # Save last update ID
    if max_id > last_id:
        conn.execute(
            "INSERT INTO telegram_state (key, value) VALUES ('last_update_id', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (str(max_id),),
        )

    conn.commit()
    return decisions_recorded


def cmd_run(args):
    """Poll Telegram for decisions, then execute approved items."""
    conn = get_conn()
    ts = now_iso()

    # Step 0: Poll Telegram for any button taps we haven't processed
    decisions = _poll_telegram_callbacks(conn)

    # Find approved but not yet executed items
    rows = conn.execute(
        "SELECT * FROM telegram_approvals WHERE decision = 'approve' "
        "AND (responded_at IS NOT NULL) "
        "ORDER BY responded_at ASC"
    ).fetchall()

    # Filter to items that haven't been executed yet (check events table)
    unexecuted = []
    for r in rows:
        already_done = conn.execute(
            "SELECT COUNT(*) as cnt FROM events WHERE event_type = 'approval_executed' "
            "AND details LIKE ?",
            (f'%{r["approval_id"]}%',)
        ).fetchone()["cnt"]
        if already_done == 0:
            unexecuted.append(r)

    if not unexecuted:
        conn.close()
        emit({"ok": True, "message": "No approved items to execute", "executed": 0})

    executed = 0
    failed = 0

    for r in unexecuted:
        aid = r["approval_id"]
        text = r["text"] or ""

        # Extract the draft text
        draft = extract_draft_from_text(text)
        handle = extract_handle(text)
        post_id = extract_post_id(aid)

        if not draft:
            # Log that we couldn't find draft text
            conn.execute(
                "INSERT INTO events (timestamp, agent, event_type, details) VALUES (?, ?, ?, ?)",
                (ts, "approval_executor", "execution_skipped", json.dumps({
                    "approval_id": aid, "reason": "no_draft_text_found",
                })),
            )
            conn.commit()
            continue

        # Attempt to post
        result = attempt_post(aid, draft, handle, post_id)

        # Log result
        conn.execute(
            "INSERT INTO events (timestamp, agent, event_type, details) VALUES (?, ?, ?, ?)",
            (ts, "approval_executor", "approval_executed", json.dumps({
                "approval_id": aid,
                "success": result["success"],
                "method": result.get("method"),
                "error": result.get("error"),
                "handle": handle,
            })),
        )
        conn.commit()

        if result["success"]:
            executed += 1
        else:
            failed += 1
            # Record failure for the feedback loop
            subprocess.run(
                ["python3", "tools/policy.py", "record-failure",
                 "--category", "PLATFORM_COOLDOWN", "--platform", "x",
                 "--agent", "approval_executor",
                 "--detail", f"Failed to execute approved item {aid}: {result.get('error')}"],
                capture_output=True, timeout=10,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )

    conn.close()
    emit({"ok": True, "executed": executed, "failed": failed, "total_pending": len(unexecuted)})


def cmd_status(args):
    """Show pending approved items."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT approval_id, responded_at, text FROM telegram_approvals "
        "WHERE decision = 'approve' ORDER BY responded_at DESC LIMIT 10"
    ).fetchall()

    items = []
    for r in rows:
        already_done = conn.execute(
            "SELECT COUNT(*) as cnt FROM events WHERE event_type = 'approval_executed' "
            "AND details LIKE ?",
            (f'%{r["approval_id"]}%',)
        ).fetchone()["cnt"]
        items.append({
            "approval_id": r["approval_id"],
            "responded_at": r["responded_at"],
            "executed": already_done > 0,
            "text_preview": (r["text"] or "")[:80],
        })

    conn.close()
    emit({"ok": True, "items": items, "count": len(items)})


def build_parser():
    parser = argparse.ArgumentParser(description="Groundswell Approval Executor")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("run", help="Execute approved items")
    sub.add_parser("status", help="Show pending approved items")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if not args.command:
        parser.print_help(sys.stderr)
        sys.exit(1)
    if args.command == "run":
        cmd_run(args)
    elif args.command == "status":
        cmd_status(args)


if __name__ == "__main__":
    main()
