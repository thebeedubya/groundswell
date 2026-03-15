"""
Channel-agnostic internal broadcast tool for Groundswell.

Posts "scoreboard" messages to Slack and/or Google Chat webhooks
showing what Brad's team is building, shipping, and automating.

Usage:
    python3 tools/broadcast.py send --text "RevRecV3 deployed"
    python3 tools/broadcast.py send --text "message" --channel slack
    python3 tools/broadcast.py send --text "message" --channel gchat
    python3 tools/broadcast.py send --text "message" --channel all
    python3 tools/broadcast.py ship --repo groundswell --commit abc123 --message "Built 7-agent social engine"
    python3 tools/broadcast.py win --title "Compliance monitoring" --detail "Built by Sarah" --team "CS"
    python3 tools/broadcast.py digest --hours 24
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

# --- Sibling imports -------------------------------------------------------

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _x_auth import load_env
from _common import DB_PATH, get_db, emit, fail, now_iso


# ---------------------------------------------------------------------------
# Webhook delivery
# ---------------------------------------------------------------------------

WEBHOOK_KEYS = ["SLACK_WEBHOOK_URL", "GCHAT_WEBHOOK_URL"]


def _load_webhooks():
    """Return dict with webhook URLs (may be empty strings)."""
    env = load_env(keys=WEBHOOK_KEYS)
    return {
        "slack": env.get("SLACK_WEBHOOK_URL", ""),
        "gchat": env.get("GCHAT_WEBHOOK_URL", ""),
    }


def _post_json(url, payload):
    """POST a JSON payload to a webhook URL. Returns (ok, detail)."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return True, body
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        return False, f"HTTP {e.code}: {body}"
    except urllib.error.URLError as e:
        return False, str(e.reason)


def broadcast(text, channel="all"):
    """Send text to the requested channel(s).

    Returns a dict with delivery results.
    """
    webhooks = _load_webhooks()
    targets = []

    if channel in ("all", "slack"):
        targets.append("slack")
    if channel in ("all", "gchat"):
        targets.append("gchat")

    results = {}
    any_configured = False

    for target in targets:
        url = webhooks.get(target, "")
        if not url:
            results[target] = {"sent": False, "reason": "no_webhook_configured"}
            continue
        any_configured = True
        ok, detail = _post_json(url, {"text": text})
        results[target] = {"sent": ok, "detail": detail}

    if not any_configured:
        print(
            "WARNING: No webhook URLs configured. "
            "Set SLACK_WEBHOOK_URL and/or GCHAT_WEBHOOK_URL in ~/.zsh_env",
            file=sys.stderr,
        )
        # Still output the formatted message so it's not lost
        print(text, file=sys.stdout)

    return results


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_send(args):
    """Raw message send."""
    results = broadcast(args.text, channel=args.channel)
    emit({
        "ok": True,
        "action": "send",
        "channel": args.channel,
        "message": args.text,
        "delivery": results,
    })


def cmd_ship(args):
    """Format and send a deployment/commit announcement."""
    short_commit = args.commit[:8] if args.commit else "unknown"
    text = (
        f"\U0001f680 SHIPPED: {args.message}\n"
        f"Repo: {args.repo} | Commit: {short_commit}"
    )
    results = broadcast(text, channel=args.channel)
    emit({
        "ok": True,
        "action": "ship",
        "channel": args.channel,
        "message": text,
        "delivery": results,
    })


def cmd_win(args):
    """Format and send a team win."""
    text = (
        f"\U0001f3c6 WIN: {args.title}\n"
        f"{args.detail}\n"
        f"Team: {args.team}"
    )
    results = broadcast(text, channel=args.channel)
    emit({
        "ok": True,
        "action": "win",
        "channel": args.channel,
        "message": text,
        "delivery": results,
    })


def cmd_digest(args):
    """Summarize recent agent activity from the SQLite database."""
    if not os.path.exists(DB_PATH):
        fail(f"Database not found at {DB_PATH}")

    conn = get_db()
    cutoff = (
        datetime.now(timezone.utc) - timedelta(hours=args.hours)
    ).isoformat().replace("+00:00", "Z")

    # Count events by type — gracefully handle missing table/columns
    try:
        rows = conn.execute(
            "SELECT type, COUNT(*) as cnt FROM events "
            "WHERE created_at >= ? GROUP BY type",
            (cutoff,),
        ).fetchall()
    except Exception:
        # Table may not exist yet or schema differs
        rows = []

    counts = {row["type"]: row["cnt"] for row in rows}

    posts_x = counts.get("post_x", 0)
    posts_li = counts.get("post_linkedin", 0)
    posts_total = posts_x + posts_li + counts.get("post", 0)
    replies = counts.get("reply", 0)
    qts = counts.get("quote_tweet", 0) + counts.get("qt", 0)
    intel = counts.get("intel", 0) + counts.get("scout", 0)
    content = counts.get("content", 0) + counts.get("draft", 0)
    signals = counts.get("signal", 0)

    # Build platform breakdown
    platform_parts = []
    if posts_x:
        platform_parts.append(f"X: {posts_x}")
    if posts_li:
        platform_parts.append(f"LinkedIn: {posts_li}")
    platform_str = f" ({', '.join(platform_parts)})" if platform_parts else ""

    # Try to get follower count
    followers = "—"
    try:
        row = conn.execute(
            "SELECT value FROM metrics WHERE key = 'followers' "
            "ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if row:
            followers = row["value"]
    except Exception:
        pass

    text = (
        f"\U0001f4ca AGENT OPS \u2014 Last {args.hours}h\n"
        f"\u2501" * 20 + "\n"
        f"\U0001f4f0 Posts: {posts_total}{platform_str}\n"
        f"\U0001f4ac Engagement: {replies} replies, {qts} QTs\n"
        f"\U0001f50d Intel: {intel} items scanned\n"
        f"\u270d\ufe0f Content: {content} pieces created\n"
        f"\u26a1 Signals: {signals} handled\n"
        f"\u2501" * 20 + "\n"
        f"Followers: {followers} | Target: 100"
    )

    results = broadcast(text, channel=args.channel)
    emit({
        "ok": True,
        "action": "digest",
        "hours": args.hours,
        "channel": args.channel,
        "message": text,
        "delivery": results,
        "counts": {
            "posts": posts_total,
            "replies": replies,
            "qts": qts,
            "intel": intel,
            "content": content,
            "signals": signals,
        },
    })


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Groundswell internal broadcast tool"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # send
    p_send = sub.add_parser("send", help="Send a raw message")
    p_send.add_argument("--text", required=True, help="Message text")
    p_send.add_argument(
        "--channel", default="all", choices=["slack", "gchat", "all"],
        help="Target channel (default: all)",
    )
    p_send.set_defaults(func=cmd_send)

    # ship
    p_ship = sub.add_parser("ship", help="Announce a deployment")
    p_ship.add_argument("--repo", required=True, help="Repository name")
    p_ship.add_argument("--commit", required=True, help="Commit hash")
    p_ship.add_argument("--message", required=True, help="What was shipped")
    p_ship.add_argument(
        "--channel", default="all", choices=["slack", "gchat", "all"],
    )
    p_ship.set_defaults(func=cmd_ship)

    # win
    p_win = sub.add_parser("win", help="Announce a team win")
    p_win.add_argument("--title", required=True, help="Win title")
    p_win.add_argument("--detail", required=True, help="Details")
    p_win.add_argument("--team", required=True, help="Team name")
    p_win.add_argument(
        "--channel", default="all", choices=["slack", "gchat", "all"],
    )
    p_win.set_defaults(func=cmd_win)

    # digest
    p_digest = sub.add_parser("digest", help="Summarize recent activity")
    p_digest.add_argument(
        "--hours", type=int, default=24, help="Lookback window in hours (default: 24)",
    )
    p_digest.add_argument(
        "--channel", default="all", choices=["slack", "gchat", "all"],
    )
    p_digest.set_defaults(func=cmd_digest)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
