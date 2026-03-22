#!/usr/bin/env python3
"""
Groundswell Telegram Bot — Interactive command interface.

Polls for messages from Brad and responds with live system data.
Runs as a daemon alongside the orchestrator on Kush.

Usage:
    python3 tools/telegram_bot.py serve    # Start polling (foreground)
    python3 tools/telegram_bot.py test     # Send a test response
"""

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(REPO_ROOT, "data", "groundswell.db")


def load_env():
    env = {}
    zsh_env = os.path.expanduser("~/.zsh_env")
    if os.path.exists(zsh_env):
        with open(zsh_env) as f:
            for line in f:
                line = line.strip()
                if line.startswith("export ") and "=" in line:
                    key, _, val = line[7:].partition("=")
                    val = val.strip("'\"")
                    env[key] = val
    for key in ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]:
        env[key] = os.environ.get(key, env.get(key, ""))
    return env


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def send_chat_action(token, chat_id, action="typing"):
    """Send a chat action (typing indicator) to Telegram."""
    data = json.dumps({"chat_id": chat_id, "action": action}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendChatAction",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except Exception:
        pass


def send_message(token, chat_id, text):
    data = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"Send error: {e}", file=sys.stderr)
        return None


def get_updates(token, offset=None):
    url = f"https://api.telegram.org/bot{token}/getUpdates?timeout=30"
    if offset:
        url += f"&offset={offset}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=35) as resp:
            return json.loads(resp.read())
    except Exception:
        return {"ok": False, "result": []}


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def cmd_status(conn):
    """Full system status."""
    events = conn.execute("SELECT COUNT(*) as c FROM events").fetchone()["c"]

    # Recent cycle
    last_cycle = conn.execute(
        "SELECT details FROM events WHERE event_type='cycle_complete' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    cycle_info = ""
    if last_cycle and last_cycle["details"]:
        d = json.loads(last_cycle["details"])
        cycle_info = f"Last cycle: {d.get('tasks_dispatched', '?')} tasks, {d.get('tasks_succeeded', '?')} succeeded"

    # Brand safety
    bs = conn.execute("SELECT value FROM strategy_state WHERE key='brand_safety_color'").fetchone()
    color = json.loads(bs["value"]) if bs else "GREEN"

    # Pending signals
    signals = conn.execute("SELECT COUNT(*) as c FROM signals WHERE consumed_at IS NULL").fetchone()["c"]

    # Backlog
    try:
        with open(os.path.join(REPO_ROOT, "data", "backlog.json")) as f:
            backlog = json.load(f)
        pending = len([b for b in backlog if not b.get("posted_at")])
    except Exception:
        pending = "?"

    return (
        f"🟢 *Groundswell Status*\n\n"
        f"Brand Safety: {color}\n"
        f"Total Events: {events}\n"
        f"{cycle_info}\n"
        f"Pending Signals: {signals}\n"
        f"Backlog: {pending} posts queued"
    )


def cmd_followers(conn):
    """Get current follower count."""
    try:
        result = subprocess.run(
            ["python3", os.path.join(REPO_ROOT, "tools", "x_api.py"), "metrics", "--handle", "thebeedubaya"],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(result.stdout)
        m = data["data"]["data"]["public_metrics"]
        return (
            f"📊 *Followers*\n\n"
            f"Followers: {m['followers_count']}\n"
            f"Following: {m['following_count']}\n"
            f"Tweets: {m['tweet_count']}\n"
            f"Likes: {m['like_count']}"
        )
    except Exception as e:
        return f"Error getting metrics: {e}"


def cmd_today(conn):
    """What happened today."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%dT")
    rows = conn.execute(
        "SELECT agent, event_type, details FROM events WHERE timestamp >= ? ORDER BY id DESC LIMIT 10",
        (today,),
    ).fetchall()

    if not rows:
        return "📅 Nothing logged today yet."

    lines = ["📅 *Today's Activity*\n"]
    for r in rows:
        agent = r["agent"]
        etype = r["event_type"]
        lines.append(f"• {agent}: {etype}")

    return "\n".join(lines)


def cmd_backlog(conn):
    """Backlog status."""
    try:
        with open(os.path.join(REPO_ROOT, "data", "backlog.json")) as f:
            backlog = json.load(f)
        pending = [b for b in backlog if not b.get("posted_at")]
        by_platform = {}
        for b in pending:
            p = b.get("platform", "?")
            by_platform[p] = by_platform.get(p, 0) + 1

        lines = [f"📝 *Backlog: {len(pending)} pending*\n"]
        for p, c in by_platform.items():
            lines.append(f"• {p}: {c}")

        lines.append(f"\nNext up:")
        for b in sorted(pending, key=lambda x: x.get("priority", 99))[:3]:
            lines.append(f"• [{b.get('priority','?')}] {b.get('type','?')}: {b.get('text','')[:50]}...")

        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


def cmd_usage(conn):
    """API usage for the month."""
    month_start = datetime.now(timezone.utc).strftime("%Y-%m-01T00:00:00Z")
    try:
        rows = conn.execute(
            "SELECT platform, call_type, COUNT(*) as cnt FROM api_usage "
            "WHERE created_at >= ? GROUP BY platform, call_type",
            (month_start,),
        ).fetchall()
    except Exception:
        return "📊 API usage tracking not initialized yet."

    counts = {f"{r['platform']}_{r['call_type']}": r["cnt"] for r in rows}
    x_reads = counts.get("x_read", 0)
    x_writes = counts.get("x_write", 0)
    li = counts.get("linkedin_write", 0)

    return (
        f"📊 *API Usage (this month)*\n\n"
        f"X Reads: {x_reads} / 10,000\n"
        f"X Writes: {x_writes} / 1,500\n"
        f"LinkedIn: {li} / 60\n"
        f"Total: {x_reads + x_writes + li}"
    )


def cmd_kill(conn):
    """Kill switch."""
    ts = now_iso()
    conn.execute(
        "INSERT OR REPLACE INTO strategy_state (key, value, version, updated_at) "
        "VALUES ('brand_safety_color', '\"BLACK\"', "
        "(SELECT COALESCE(MAX(version),0)+1 FROM strategy_state WHERE key='brand_safety_color'), ?)",
        (ts,),
    )
    conn.commit()
    return "🔴 *KILL SWITCH ACTIVATED*\nBrand safety set to BLACK. All agents halted."


def cmd_resume(conn):
    """Resume from kill."""
    ts = now_iso()
    conn.execute(
        "INSERT OR REPLACE INTO strategy_state (key, value, version, updated_at) "
        "VALUES ('brand_safety_color', '\"GREEN\"', "
        "(SELECT COALESCE(MAX(version),0)+1 FROM strategy_state WHERE key='brand_safety_color'), ?)",
        (ts,),
    )
    conn.commit()
    return "🟢 *RESUMED*\nBrand safety set to GREEN. Agents active."


def cmd_help():
    return (
        "🤖 *Groundswell Commands*\n\n"
        "• `status` — System status\n"
        "• `followers` — Follower count\n"
        "• `today` — Today's activity\n"
        "• `backlog` — Content queue\n"
        "• `usage` — API usage this month\n"
        "• `kill` — Emergency stop\n"
        "• `resume` — Resume operations\n"
        "• `help` — This message"
    )


COMMANDS = {
    "status": cmd_status,
    "followers": cmd_followers,
    "today": cmd_today,
    "backlog": cmd_backlog,
    "usage": cmd_usage,
    "kill": cmd_kill,
    "resume": cmd_resume,
}


def gather_context(conn):
    """Gather full system context for agentic responses."""
    ctx = {}

    # Status
    events_total = conn.execute("SELECT COUNT(*) as c FROM events").fetchone()["c"]
    bs = conn.execute("SELECT value FROM strategy_state WHERE key='brand_safety_color'").fetchone()
    ctx["brand_safety"] = json.loads(bs["value"]) if bs else "GREEN"
    ctx["total_events"] = events_total

    # Today's events
    today = datetime.now(timezone.utc).strftime("%Y-%m-%dT")
    today_events = conn.execute(
        "SELECT agent, event_type, details FROM events WHERE timestamp >= ? ORDER BY id DESC LIMIT 15",
        (today,),
    ).fetchall()
    ctx["today"] = [{"agent": r["agent"], "type": r["event_type"],
                     "detail": (r["details"] or "")[:100]} for r in today_events]

    # Pending approvals
    approvals = conn.execute("SELECT idempotency_key, action_type, payload FROM pending_actions WHERE status='pending'").fetchall()
    ctx["pending_approvals"] = len(approvals)
    ctx["approval_details"] = [{"key": r["idempotency_key"][:50], "type": r["action_type"]} for r in approvals[:5]]

    # Followers (from last snapshot)
    snap = conn.execute(
        "SELECT details FROM events WHERE event_type='follower_snapshot' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if snap and snap["details"]:
        try:
            d = json.loads(snap["details"])
            ctx["followers"] = d.get("count") or d.get("followers")
        except Exception:
            pass

    # Backlog
    try:
        with open(os.path.join(REPO_ROOT, "data", "backlog.json")) as f:
            backlog = json.load(f)
        pending = [b for b in backlog if not b.get("posted_at")]
        ctx["backlog_pending"] = len(pending)
        ctx["backlog_next"] = [{"type": b.get("type"), "platform": b.get("platform")}
                               for b in sorted(pending, key=lambda x: x.get("priority", 99))[:3]]
    except Exception:
        pass

    # API usage
    month_start = datetime.now(timezone.utc).strftime("%Y-%m-01T00:00:00Z")
    try:
        rows = conn.execute(
            "SELECT platform, call_type, COUNT(*) as cnt FROM api_usage WHERE created_at >= ? GROUP BY platform, call_type",
            (month_start,),
        ).fetchall()
        ctx["api_usage"] = {f"{r['platform']}_{r['call_type']}": r["cnt"] for r in rows}
    except Exception:
        ctx["api_usage"] = {}

    # Signals
    signals = conn.execute("SELECT COUNT(*) as c FROM signals WHERE consumed_at IS NULL").fetchone()["c"]
    ctx["pending_signals"] = signals

    return ctx


def agentic_response(question, conn):
    """Use Claude to generate a natural response based on system context."""
    ctx = gather_context(conn)

    prompt = f"""You are the Groundswell system — Brad Wood's 8-agent social growth engine. Brad is asking you a question via Telegram. Answer conversationally, like a sharp ops manager giving a briefing. Be concise (Telegram messages should be short), specific with numbers, and proactive — if something needs Brad's attention, say so.

SYSTEM CONTEXT:
{json.dumps(ctx, indent=2, default=str)}

BRAD'S QUESTION: {question}

Respond in 2-5 short paragraphs. Use emoji sparingly. No markdown headers. Be direct."""

    try:
        result = subprocess.run(
            ["/opt/homebrew/bin/claude", "-p", prompt,
             "--no-session-persistence", "--model", "haiku"],
            capture_output=True, text=True, timeout=30,
            cwd=REPO_ROOT,
        )
        response = result.stdout.strip()
        if response:
            return response
    except Exception as e:
        print(f"[telegram_bot] Claude error: {e}", file=sys.stderr)

    # Fallback to structured response if Claude fails
    return cmd_status(conn)


def handle_message(text, conn):
    """Parse a message and return a response."""
    original = text.strip()
    lower = original.lower()

    # Direct commands that should NOT go through Claude (safety)
    if lower in ("kill", "/kill", "stop", "halt", "emergency"):
        return cmd_kill(conn)
    if lower in ("resume", "/resume"):
        return cmd_resume(conn)
    if lower in ("help", "/help", "/start"):
        return cmd_help()

    # Everything else goes through Claude for a natural response
    return ("__typing__", original, conn)


def _handle_diary_callback(action, key, conn):
    """Handle diary entry approve/reject. Returns response string or None if not a diary key."""
    if not key.startswith("diary-"):
        return None

    if action == "approve":
        try:
            result = subprocess.run(
                ["python3", os.path.join(REPO_ROOT, "tools", "diary.py"), "approve", "--id", key],
                capture_output=True, text=True, timeout=150,
                env={**os.environ, "PATH": "/opt/homebrew/bin:" + os.environ.get("PATH", "")},
            )
            print(f"[telegram_bot] Diary approve: {result.stdout[:200]}", file=sys.stderr)
            return f"✅ Diary approved & published: {key}"
        except Exception as e:
            print(f"[telegram_bot] Diary approve error: {e}", file=sys.stderr)
            return f"⚠️ Diary approve failed: {e}"

    elif action == "reject":
        try:
            result = subprocess.run(
                ["python3", os.path.join(REPO_ROOT, "tools", "diary.py"),
                 "reject", "--id", key, "--reason", "rejected via Telegram"],
                capture_output=True, text=True, timeout=30,
                env={**os.environ, "PATH": "/opt/homebrew/bin:" + os.environ.get("PATH", "")},
            )
            return f"❌ Diary rejected: {key}"
        except Exception as e:
            return f"⚠️ Diary reject failed: {e}"

    return None


def handle_callback(data, conn):
    """Handle approval button callbacks."""
    # Format: "approve:ACTION_KEY" or "reject:ACTION_KEY"
    parts = data.split(":", 1)
    if len(parts) < 2:
        return f"⚠️ Unrecognized callback: {data}"

    action = parts[0].lower()
    key = parts[1]

    # Check if this is a diary entry first
    diary_result = _handle_diary_callback(action, key, conn)
    if diary_result:
        return diary_result

    ts = now_iso()

    if action in ("approve", "reject"):
        # Write to BOTH tables — pending_actions (legacy) and telegram_approvals (new)

        # 1. Update telegram_approvals (primary)
        ta_cur = conn.execute(
            "UPDATE telegram_approvals SET decision=?, responded_at=? WHERE approval_id=? AND decision IS NULL",
            (action, ts, key),
        )
        if ta_cur.rowcount == 0:
            # Try partial match
            ta_cur = conn.execute(
                "UPDATE telegram_approvals SET decision=?, responded_at=? WHERE approval_id LIKE ? AND decision IS NULL",
                (action, ts, f"%{key}%"),
            )

        # 2. Update pending_actions (legacy compatibility)
        pa_cur = conn.execute(
            "UPDATE pending_actions SET status=?, completed_at=? WHERE idempotency_key=? AND status='pending'",
            ("approved" if action == "approve" else "rejected", ts, key),
        )
        if pa_cur.rowcount == 0:
            pa_cur = conn.execute(
                "UPDATE pending_actions SET status=?, completed_at=? WHERE idempotency_key LIKE ? AND status='pending'",
                ("approved" if action == "approve" else "rejected", ts, f"%{key}%"),
            )

        conn.commit()

        found = ta_cur.rowcount > 0 or pa_cur.rowcount > 0

        if action == "approve" and found:
            # Try to execute via pending_actions payload (legacy path)
            row = conn.execute(
                "SELECT * FROM pending_actions WHERE idempotency_key LIKE ?",
                (f"%{key}%",),
            ).fetchone()
            if row and row["payload"]:
                try:
                    payload = json.loads(row["payload"])
                    execute_approved_action(row["action_type"], payload, conn)
                except Exception as e:
                    print(f"[telegram_bot] Execute error: {e}", file=sys.stderr)

            return f"✅ Approved: {key[:40]}"
        elif action == "reject" and found:
            return f"❌ Rejected: {key[:40]}"
        elif found:
            return f"✅ {action.capitalize()}: {key[:40]}"
        else:
            return f"⚠️ Not found or already processed: {key[:40]}"

    return f"⚠️ Unknown action: {action}"


def _notify_manual_post(text, reply_to=None, quote_tweet_id=None):
    """Send Brad two Telegram messages for manual posting (403 fallback).

    Message 1: link to tap open in Twitter
    Message 2: just the draft text (long-press to copy, paste in reply box)
    """
    env = load_env()
    token = env.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = env.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return

    # Message 1: context + tappable link
    if reply_to:
        send_message(token, chat_id,
                     f"✏️ Reply manually:\nhttps://x.com/i/status/{reply_to}")
    elif quote_tweet_id:
        send_message(token, chat_id,
                     f"✏️ Quote manually:\nhttps://x.com/i/status/{quote_tweet_id}")

    # Message 2: just the text, nothing else — easy to long-press → Copy
    send_message(token, chat_id, text)


def _check_forbidden(result_stdout, text, reply_to=None, quote_tweet_id=None):
    """Check if post.py returned a 403 forbidden error. Returns True if handled."""
    try:
        data = json.loads(result_stdout)
        if not data.get("ok") and data.get("error") == "forbidden":
            print(f"[telegram_bot] 403 forbidden — surfacing for manual post", file=sys.stderr)
            _notify_manual_post(text, reply_to=reply_to, quote_tweet_id=quote_tweet_id)
            return True
    except (json.JSONDecodeError, ValueError):
        pass
    return False


def execute_approved_action(action_type, payload, conn):
    """Execute an approved action — post the reply, QT, etc."""
    if action_type in ("reply", "pending_reply"):
        # Post the reply to X
        text = payload.get("text") or payload.get("draft", "")
        reply_to = payload.get("reply_to") or payload.get("tweet_id", "")
        if text and reply_to:
            try:
                result = subprocess.run(
                    ["python3", os.path.join(REPO_ROOT, "tools", "post.py"),
                     "x", "--text", text, "--reply-to", str(reply_to)],
                    capture_output=True, text=True, timeout=30,
                    env={**os.environ, "PATH": "/opt/homebrew/bin:" + os.environ.get("PATH", "")},
                )
                if not _check_forbidden(result.stdout, text, reply_to=reply_to):
                    print(f"[telegram_bot] Posted reply: {result.stdout[:100]}", file=sys.stderr)
            except Exception as e:
                print(f"[telegram_bot] Post error: {e}", file=sys.stderr)

    elif action_type in ("post", "quote_tweet"):
        text = payload.get("text") or payload.get("draft", "")
        qt_id = payload.get("quote_tweet_id", "")
        if text:
            try:
                cmd = ["python3", os.path.join(REPO_ROOT, "tools", "post.py"), "x", "--text", text]
                if qt_id:
                    cmd.extend(["--quote-tweet-id", str(qt_id)])
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=30,
                    env={**os.environ, "PATH": "/opt/homebrew/bin:" + os.environ.get("PATH", "")},
                )
                if not _check_forbidden(result.stdout, text, quote_tweet_id=qt_id):
                    print(f"[telegram_bot] Posted: {result.stdout[:100]}", file=sys.stderr)
            except Exception as e:
                print(f"[telegram_bot] Post error: {e}", file=sys.stderr)


def serve():
    """Main polling loop."""
    env = load_env()
    token = env.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = env.get("TELEGRAM_CHAT_ID", "")

    if not token:
        print("TELEGRAM_BOT_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    print(f"[telegram_bot] Starting poll loop...")
    offset = None

    while True:
        try:
            updates = get_updates(token, offset)
            if not updates.get("ok"):
                time.sleep(5)
                continue

            for update in updates.get("result", []):
                offset = update["update_id"] + 1

                # Handle callback queries (approval buttons)
                cb = update.get("callback_query")
                if cb:
                    cb_data = cb.get("data", "")
                    cb_id = cb.get("id", "")
                    sender_id = str(cb.get("from", {}).get("id", ""))

                    if sender_id != chat_id:
                        continue

                    print(f"[telegram_bot] Callback: {cb_data}")

                    cb_msg_id = cb.get("message", {}).get("message_id")
                    cb_msg_text = cb.get("message", {}).get("text", "")

                    # Process the approval/rejection
                    conn = get_db()
                    try:
                        action_word = cb_data.split(":")[0].lower()
                        result = handle_callback(cb_data, conn)
                    finally:
                        conn.close()

                    # 1. Answer callback with popup toast
                    try:
                        toast = "✅ Approved!" if "approve" in action_word else "❌ Rejected"
                        answer_data = json.dumps({
                            "callback_query_id": cb_id,
                            "text": toast,
                            "show_alert": False,
                        }).encode()
                        req = urllib.request.Request(
                            f"https://api.telegram.org/bot{token}/answerCallbackQuery",
                            data=answer_data,
                            headers={"Content-Type": "application/json"},
                            method="POST",
                        )
                        urllib.request.urlopen(req)
                    except Exception:
                        pass

                    # 2. Edit original message — remove buttons, add status
                    if cb_msg_id:
                        try:
                            status_line = "\n\n✅ APPROVED" if "approve" in action_word else "\n\n❌ REJECTED"
                            edit_data = json.dumps({
                                "chat_id": chat_id,
                                "message_id": cb_msg_id,
                                "text": cb_msg_text + status_line,
                                "reply_markup": json.dumps({"inline_keyboard": []}),
                            }).encode()
                            req = urllib.request.Request(
                                f"https://api.telegram.org/bot{token}/editMessageText",
                                data=edit_data,
                                headers={"Content-Type": "application/json"},
                                method="POST",
                            )
                            urllib.request.urlopen(req)
                        except Exception:
                            pass

                    # 3. Send confirmation of what happened
                    send_message(token, chat_id, result)

                    # 4. If rejected, ask for reason
                    if "reject" in action_word:
                        rejection_key = cb_data.split(":", 1)[1] if ":" in cb_data else cb_data
                        conn2 = get_db()
                        conn2.execute(
                            "INSERT INTO telegram_state (key, value) VALUES ('awaiting_rejection_reason', ?) "
                            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                            (rejection_key,),
                        )
                        conn2.commit()
                        conn2.close()
                        send_message(token, chat_id, "💬 Why did you reject this? (Type a short reason — helps the agents learn)")

                    continue

                # Handle regular messages
                msg = update.get("message", {})
                text = msg.get("text", "")
                sender_id = str(msg.get("chat", {}).get("id", ""))

                # Only respond to Brad
                if sender_id != chat_id:
                    continue

                if not text:
                    continue

                # Check if we're awaiting a rejection reason
                conn_check = get_db()
                awaiting = conn_check.execute(
                    "SELECT value FROM telegram_state WHERE key = 'awaiting_rejection_reason'"
                ).fetchone()
                if awaiting and awaiting["value"]:
                    rejection_key = awaiting["value"]
                    # Store the reason
                    conn_check.execute(
                        "UPDATE telegram_approvals SET decision = 'reject', "
                        "responded_at = COALESCE(responded_at, ?) "
                        "WHERE approval_id = ? OR approval_id LIKE ?",
                        (now_iso(), rejection_key, f"%{rejection_key}%"),
                    )
                    # Log as a learning event
                    conn_check.execute(
                        "INSERT INTO events (timestamp, agent, event_type, details) VALUES (?, ?, ?, ?)",
                        (now_iso(), "brad", "rejection_reason", json.dumps({
                            "approval_id": rejection_key,
                            "reason": text,
                        })),
                    )
                    # Clear the awaiting state
                    conn_check.execute(
                        "DELETE FROM telegram_state WHERE key = 'awaiting_rejection_reason'"
                    )
                    conn_check.commit()
                    conn_check.close()
                    send_message(token, chat_id, f"📝 Got it — recorded: \"{text[:80]}\"")
                    print(f"[telegram_bot] Rejection reason for {rejection_key}: {text}")
                    continue
                conn_check.close()

                print(f"[telegram_bot] Received: {text}")

                conn = get_db()
                try:
                    result = handle_message(text, conn)

                    # If agentic response, show typing indicator first
                    if isinstance(result, tuple) and result[0] == "__typing__":
                        _, question, db_conn = result
                        send_chat_action(token, chat_id, "typing")
                        response = agentic_response(question, db_conn)
                    else:
                        response = result
                finally:
                    conn.close()

                send_message(token, chat_id, response)
                print(f"[telegram_bot] Responded to: {text}")

        except KeyboardInterrupt:
            print("[telegram_bot] Shutting down.")
            break
        except Exception as e:
            print(f"[telegram_bot] Error: {e}", file=sys.stderr)
            time.sleep(5)


def main():
    parser = argparse.ArgumentParser(description="Groundswell Telegram Bot")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("serve", help="Start polling loop")
    sub.add_parser("test", help="Send a test status message")

    args = parser.parse_args()
    if not args.command:
        parser.print_help(sys.stderr)
        sys.exit(1)

    if args.command == "serve":
        serve()
    elif args.command == "test":
        env = load_env()
        conn = get_db()
        response = cmd_status(conn)
        conn.close()
        send_message(env["TELEGRAM_BOT_TOKEN"], env["TELEGRAM_CHAT_ID"], response)
        print("Test message sent")


if __name__ == "__main__":
    main()
