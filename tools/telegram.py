#!/usr/bin/env python3
"""
Groundswell Telegram Tool — Send messages, briefings, alerts, and approval requests.

Replaces Slack entirely. Uses Telegram Bot API with inline keyboards for approvals.

Credentials loaded from: env vars > ~/.zsh_env > hardcoded defaults.

Usage:
    python3 tools/telegram.py send --text "message here"
    python3 tools/telegram.py send --text "message" --parse-mode html
    python3 tools/telegram.py briefing --data '{"followers":44,"posts_today":5}'
    python3 tools/telegram.py approval --id X --text "Publisher wants to post: ..." --options '["approve","reject","edit"]'
    python3 tools/telegram.py check-approval --id X
    python3 tools/telegram.py alert --level warning --text "Rate limit approaching"
    python3 tools/telegram.py alert --level critical --text "Brand safety RED"
"""

import argparse
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(REPO_ROOT, "data", "groundswell.db")

DEFAULT_TOKEN = ""  # Set TELEGRAM_BOT_TOKEN in ~/.zsh_env
DEFAULT_CHAT_ID = ""  # Set TELEGRAM_CHAT_ID in ~/.zsh_env


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def emit(data):
    json.dump(data, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    sys.exit(0)


def fail(msg):
    json.dump({"ok": False, "error": "error", "message": msg}, sys.stdout, indent=2)
    sys.stdout.write("\n")
    sys.exit(1)


def load_env():
    """Load credentials: env vars > ~/.zsh_env > hardcoded defaults."""
    from _x_auth import load_env as _load_env
    return _load_env(keys=["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"])


def get_credentials():
    """Return (token, chat_id) with fallback chain."""
    env = load_env()
    token = env.get("TELEGRAM_BOT_TOKEN") or DEFAULT_TOKEN
    chat_id = env.get("TELEGRAM_CHAT_ID") or DEFAULT_CHAT_ID
    return token, chat_id


def telegram_api(token, method, payload):
    """Call Telegram Bot API. Returns parsed JSON response."""
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        fail(f"Telegram API error {e.code}: {body}")
    except urllib.error.URLError as e:
        fail(f"Network error: {e.reason}")


# ---------------------------------------------------------------------------
# SQLite for approval state
# ---------------------------------------------------------------------------

APPROVAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS telegram_approvals (
    approval_id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    options TEXT NOT NULL,
    message_id INTEGER,
    decision TEXT,
    responded_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS telegram_state (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    conn.executescript(APPROVAL_SCHEMA)
    return conn


def get_last_update_id(conn):
    row = conn.execute(
        "SELECT value FROM telegram_state WHERE key = 'last_update_id'"
    ).fetchone()
    return int(row["value"]) if row else 0


def set_last_update_id(conn, update_id):
    conn.execute(
        "INSERT INTO telegram_state (key, value) VALUES ('last_update_id', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (str(update_id),),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Button label formatting
# ---------------------------------------------------------------------------

OPTION_ICONS = {
    "approve": "\u2705",
    "reject": "\u274c",
    "edit": "\u270f\ufe0f",
    "skip": "\u23ed\ufe0f",
    "delay": "\u23f0",
}


def button_label(option):
    icon = OPTION_ICONS.get(option.lower(), "\u25b6\ufe0f")
    return f"{icon} {option.capitalize()}"


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------

def cmd_send(args):
    token, chat_id = get_credentials()
    payload = {
        "chat_id": chat_id,
        "text": args.text,
    }
    if args.parse_mode:
        payload["parse_mode"] = args.parse_mode.upper() if args.parse_mode.lower() == "html" else "Markdown"
    result = telegram_api(token, "sendMessage", payload)
    if result.get("ok"):
        emit({
            "ok": True,
            "message_id": result["result"]["message_id"],
        })
    else:
        fail(f"Telegram returned ok=false: {result.get('description', 'unknown')}")


def cmd_briefing(args):
    token, chat_id = get_credentials()
    try:
        data = json.loads(args.data)
    except json.JSONDecodeError as e:
        fail(f"--data must be valid JSON: {e}")

    # Build formatted briefing message
    lines = ["\U0001f4ca *Groundswell Daily Briefing*", ""]

    field_labels = {
        "followers": "Followers",
        "posts_today": "Posts today",
        "engagement_rate": "Engagement rate",
        "pending_approvals": "Pending approvals",
        "top_performing": "Top performing",
        "follower_delta": "Follower delta",
        "replies_sent": "Replies sent",
        "new_follows": "New follows",
    }

    for key, val in data.items():
        label = field_labels.get(key, key.replace("_", " ").title())
        if key == "engagement_rate" and isinstance(val, (int, float)):
            val = f"{val}%"
        if key == "top_performing" and isinstance(val, str):
            val = f'"{val}"'
        lines.append(f"{label}: {val}")

    text = "\n".join(lines)
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }
    result = telegram_api(token, "sendMessage", payload)
    if result.get("ok"):
        emit({
            "ok": True,
            "message_id": result["result"]["message_id"],
        })
    else:
        fail(f"Telegram returned ok=false: {result.get('description', 'unknown')}")


def cmd_approval(args):
    token, chat_id = get_credentials()
    approval_id = args.id

    try:
        options = json.loads(args.options)
    except json.JSONDecodeError as e:
        fail(f"--options must be valid JSON array: {e}")

    if not isinstance(options, list) or len(options) == 0:
        fail("--options must be a non-empty JSON array of strings")

    # Build inline keyboard — all buttons in one row
    buttons = [
        {"text": button_label(opt), "callback_data": f"{opt.lower()}:{approval_id}"}
        for opt in options
    ]
    reply_markup = {"inline_keyboard": [buttons]}

    # If --post-id provided, add tweet link to the approval card
    card_text = args.text
    if args.post_id:
        # Extract target handle from text (look for @handle pattern)
        handle = ""
        import re
        handle_match = re.search(r"@(\w+)", card_text)
        if handle_match:
            handle = handle_match.group(1)
        tweet_url = f"https://x.com/{handle}/status/{args.post_id}" if handle else f"https://x.com/i/status/{args.post_id}"
        card_text = f"{card_text}\n\nTweet: {tweet_url}"

    import html as html_mod
    safe_card = html_mod.escape(card_text)
    payload = {
        "chat_id": chat_id,
        "text": f"\U0001f514 <b>Approval Required</b> (#{html_mod.escape(approval_id)})\n\n{safe_card}",
        "parse_mode": "HTML",
        "reply_markup": reply_markup,
    }
    result = telegram_api(token, "sendMessage", payload)
    if not result.get("ok"):
        fail(f"Telegram returned ok=false: {result.get('description', 'unknown')}")

    message_id = result["result"]["message_id"]

    # Send draft text as a separate plain-text message for easy copy-paste
    if args.draft:
        draft_payload = {
            "chat_id": chat_id,
            "text": args.draft,
            "reply_to_message_id": message_id,
        }
        telegram_api(token, "sendMessage", draft_payload)

    # Store in DB
    conn = get_db()
    ts = now_iso()
    conn.execute(
        "INSERT INTO telegram_approvals (approval_id, text, options, message_id, created_at) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(approval_id) DO UPDATE SET text=excluded.text, options=excluded.options, "
        "message_id=excluded.message_id, created_at=excluded.created_at, decision=NULL, responded_at=NULL",
        (approval_id, args.text, json.dumps(options), message_id, ts),
    )
    conn.commit()
    conn.close()

    emit({
        "ok": True,
        "approval_id": approval_id,
        "message_id": message_id,
    })


def cmd_check_approval(args):
    token, chat_id = get_credentials()
    approval_id = args.id

    conn = get_db()

    # Check if already resolved in DB
    row = conn.execute(
        "SELECT * FROM telegram_approvals WHERE approval_id = ?", (approval_id,)
    ).fetchone()

    if row and row["decision"]:
        conn.close()
        emit({
            "ok": True,
            "approval_id": approval_id,
            "decision": row["decision"],
            "responded_at": row["responded_at"],
        })

    # Poll getUpdates for callback queries
    last_update_id = get_last_update_id(conn)
    offset = last_update_id + 1 if last_update_id else None

    payload = {"timeout": 0}
    if offset:
        payload["offset"] = offset

    result = telegram_api(token, "getUpdates", payload)
    if not result.get("ok"):
        conn.close()
        fail(f"getUpdates failed: {result.get('description', 'unknown')}")

    updates = result.get("result", [])
    decision = None
    responded_at = None
    max_update_id = last_update_id

    for update in updates:
        uid = update["update_id"]
        if uid > max_update_id:
            max_update_id = uid

        cb = update.get("callback_query")
        if not cb:
            continue

        cb_data = cb.get("data", "")
        # callback_data format: "action:approval_id"
        if ":" in cb_data:
            action, cb_approval_id = cb_data.split(":", 1)
            if cb_approval_id == str(approval_id):
                decision = action
                # Extract timestamp from callback if available
                responded_at = now_iso()

                # Answer the callback to dismiss loading indicator
                telegram_api(token, "answerCallbackQuery", {
                    "callback_query_id": cb["id"],
                    "text": f"Got it: {action}",
                })

    # Update last processed update ID
    if max_update_id > last_update_id:
        set_last_update_id(conn, max_update_id)

    if decision:
        ts = now_iso()
        conn.execute(
            "UPDATE telegram_approvals SET decision = ?, responded_at = ? WHERE approval_id = ?",
            (decision, responded_at, approval_id),
        )
        conn.commit()
        conn.close()
        emit({
            "ok": True,
            "approval_id": approval_id,
            "decision": decision,
            "responded_at": responded_at,
        })
    else:
        conn.close()
        emit({
            "ok": True,
            "approval_id": approval_id,
            "decision": None,
            "pending": True,
        })


def cmd_alert(args):
    token, chat_id = get_credentials()
    level = args.level.lower()

    if level == "critical":
        text = f"\U0001f534 *CRITICAL:* {args.text}"
    elif level == "warning":
        text = f"\u26a0\ufe0f {args.text}"
    elif level == "info":
        text = f"\u2139\ufe0f {args.text}"
    else:
        text = f"{args.text}"

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }
    result = telegram_api(token, "sendMessage", payload)
    if result.get("ok"):
        emit({
            "ok": True,
            "message_id": result["result"]["message_id"],
            "level": level,
        })
    else:
        fail(f"Telegram returned ok=false: {result.get('description', 'unknown')}")


# ---------------------------------------------------------------------------
# CLI parser
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        description="Groundswell Telegram Tool — notifications and approvals",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    # send
    p = sub.add_parser("send", help="Send a message")
    p.add_argument("--text", required=True, help="Message text")
    p.add_argument("--parse-mode", default=None, help="Parse mode: Markdown or HTML")

    # briefing
    p = sub.add_parser("briefing", help="Send a formatted daily briefing")
    p.add_argument("--data", required=True, help="JSON object with briefing data")

    # approval
    p = sub.add_parser("approval", help="Send an approval request with inline keyboard")
    p.add_argument("--id", required=True, help="Unique approval request ID")
    p.add_argument("--text", required=True, help="Approval request description")
    p.add_argument("--options", required=True, help='JSON array of options (e.g. \'["approve","reject"]\')')
    p.add_argument("--draft", default=None, help="Draft text to send as separate copy-pasteable message")
    p.add_argument("--post-id", default=None, help="Tweet/post ID to generate a direct link")

    # check-approval
    p = sub.add_parser("check-approval", help="Check if an approval was answered")
    p.add_argument("--id", required=True, help="Approval request ID to check")

    # alert
    p = sub.add_parser("alert", help="Send an alert with severity level")
    p.add_argument("--level", required=True, choices=["info", "warning", "critical"], help="Alert severity")
    p.add_argument("--text", required=True, help="Alert message text")

    return parser


COMMANDS = {
    "send": cmd_send,
    "briefing": cmd_briefing,
    "approval": cmd_approval,
    "check-approval": cmd_check_approval,
    "alert": cmd_alert,
}


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help(sys.stderr)
        sys.exit(1)

    handler = COMMANDS.get(args.command)
    if not handler:
        fail(f"Unknown command: {args.command}")

    try:
        handler(args)
    except SystemExit:
        raise
    except Exception as e:
        fail(str(e))


if __name__ == "__main__":
    main()
