#!/usr/bin/env python3
"""
Generate daily receipts for dbradwood.com/receipts.

Reads from Groundswell SQLite, compiles a daily summary, and writes
to the dbradwood.com content/receipts.json file. The Analyst agent
runs this daily. The website reads the JSON and renders it.

Usage:
    python3 tools/receipts.py generate         # Generate today's entry
    python3 tools/receipts.py generate --push   # Generate and git push to trigger Vercel deploy
    python3 tools/receipts.py status            # Show current receipts data
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(REPO_ROOT, "data", "groundswell.db")
WEBSITE_ROOT = os.path.expanduser("~/Projects/dbradwood.com")
RECEIPTS_PATH = os.path.join(WEBSITE_ROOT, "content", "receipts.json")


def emit(data):
    json.dump(data, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    sys.exit(0)


def fail(msg):
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def get_db():
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def load_receipts():
    if os.path.exists(RECEIPTS_PATH):
        with open(RECEIPTS_PATH) as f:
            return json.load(f)
    return {"updated_at": now_iso(), "entries": []}


def save_receipts(data):
    data["updated_at"] = now_iso()
    os.makedirs(os.path.dirname(RECEIPTS_PATH), exist_ok=True)
    with open(RECEIPTS_PATH, "w") as f:
        json.dump(data, f, indent=2, default=str)
        f.write("\n")


def generate_entry(conn, date_str):
    """Generate a receipt entry for a specific date."""
    day_start = f"{date_str}T00:00:00"
    day_end = f"{date_str}T23:59:59"

    # Count posts
    posts = conn.execute(
        "SELECT COUNT(*) as c FROM events WHERE event_type LIKE '%post_sent%' "
        "AND timestamp >= ? AND timestamp <= ?",
        (day_start, day_end),
    ).fetchone()["c"]

    # Count engagements (replies, QTs)
    engagements = conn.execute(
        "SELECT COUNT(*) as c FROM events WHERE "
        "(event_type LIKE '%reply%' OR event_type LIKE '%qt%' OR event_type LIKE '%engage%') "
        "AND timestamp >= ? AND timestamp <= ?",
        (day_start, day_end),
    ).fetchone()["c"]

    # Count intel items
    intel = 0
    try:
        intel = conn.execute(
            "SELECT COUNT(*) as c FROM intel_feed WHERE created_at >= ? AND created_at <= ?",
            (day_start, day_end),
        ).fetchone()["c"]
    except Exception:
        pass

    # Count content created
    content = conn.execute(
        "SELECT COUNT(*) as c FROM events WHERE event_type LIKE '%content_created%' "
        "AND timestamp >= ? AND timestamp <= ?",
        (day_start, day_end),
    ).fetchone()["c"]

    # Get follower count from latest snapshot
    follower_row = conn.execute(
        "SELECT details FROM events WHERE event_type = 'follower_snapshot' "
        "AND timestamp >= ? AND timestamp <= ? ORDER BY id DESC LIMIT 1",
        (day_start, day_end),
    ).fetchone()

    follower_count = None
    if follower_row and follower_row["details"]:
        try:
            details = json.loads(follower_row["details"])
            follower_count = details.get("count") or details.get("followers")
        except (json.JSONDecodeError, TypeError):
            pass

    # Get previous day's follower count for delta
    prev_date = (datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    prev_row = conn.execute(
        "SELECT details FROM events WHERE event_type = 'follower_snapshot' "
        "AND timestamp LIKE ? ORDER BY id DESC LIMIT 1",
        (f"{prev_date}%",),
    ).fetchone()

    follower_delta = None
    if follower_count is not None and prev_row and prev_row["details"]:
        try:
            prev_details = json.loads(prev_row["details"])
            prev_count = prev_details.get("count") or prev_details.get("followers")
            if prev_count is not None:
                follower_delta = follower_count - prev_count
        except (json.JSONDecodeError, TypeError):
            pass

    # Build highlights from events
    highlights = []
    events = conn.execute(
        "SELECT agent, event_type, details FROM events "
        "WHERE timestamp >= ? AND timestamp <= ? ORDER BY id ASC",
        (day_start, day_end),
    ).fetchall()

    for ev in events:
        agent = ev["agent"]
        etype = ev["event_type"]
        try:
            details = json.loads(ev["details"]) if ev["details"] else {}
        except (json.JSONDecodeError, TypeError):
            details = {}

        # Generate human-readable highlight
        if etype == "post_sent":
            platform = details.get("platform", "?")
            item_id = details.get("item_id", "")
            fmt = details.get("format", "single")
            if fmt == "thread":
                count = details.get("tweet_count", "?")
                highlights.append(f"Published {count}-tweet thread on {platform} ({item_id})")
            else:
                highlights.append(f"Published post on {platform} ({item_id})")

        elif etype == "reply_sent":
            target = details.get("target", "?")
            highlights.append(f"Replied to @{target}")

        elif etype == "content_created":
            count = details.get("posts_created", "?")
            platform = details.get("platform", "?")
            highlights.append(f"Created {count} new content pieces for {platform}")

        elif etype == "scan_complete":
            signals = details.get("signals_emitted", 0)
            sources = details.get("sources_checked", 0)
            if signals > 0:
                highlights.append(f"Scout scanned {sources} sources, emitted {signals} signals")

        elif etype == "weekly_audit_complete":
            highlights.append("Weekly growth audit completed")

        elif etype == "cycle_complete":
            tasks = details.get("tasks_dispatched", 0)
            succeeded = details.get("tasks_succeeded", 0)
            highlights.append(f"Orchestrator cycle: {succeeded}/{tasks} tasks succeeded")

        elif etype == "brand_safety_change":
            color = details.get("color", "?")
            reason = details.get("reason", "")
            highlights.append(f"Brand safety changed to {color}: {reason}")

    # Also check intel feed for notable items
    try:
        intel_items = conn.execute(
            "SELECT headline FROM intel_feed WHERE created_at >= ? AND created_at <= ? "
            "ORDER BY relevance_score DESC LIMIT 5",
            (day_start, day_end),
        ).fetchall()
        for item in intel_items:
            highlights.append(f"Intel: {item['headline']}")
    except Exception:
        pass

    # Pull git commits from all repos for this day
    repos = [
        ("groundswell", REPO_ROOT),
        ("dbradwood.com", os.path.expanduser("~/Projects/dbradwood.com")),
        ("forge-ecosystem", os.path.expanduser("~/Projects/forge-ecosystem")),
        ("forge-brain", os.path.expanduser("~/Projects/forge-brain")),
        ("leroy", os.path.expanduser("~/Projects/leroy")),
    ]
    for repo_name, repo_path in repos:
        if not os.path.isdir(repo_path):
            continue
        try:
            result = subprocess.run(
                ["git", "log", f"--since={date_str}T00:00:00", f"--until={date_str}T23:59:59",
                 "--oneline", "--no-merges", "--format=%s"],
                cwd=repo_path, capture_output=True, text=True, timeout=10,
            )
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if line and not line.startswith("Co-Authored"):
                    highlights.append(f"Commit ({repo_name}): {line}")
        except Exception:
            pass

    # Pull backlog status
    try:
        backlog_path = os.path.join(REPO_ROOT, "data", "backlog.json")
        if os.path.exists(backlog_path):
            with open(backlog_path) as f:
                backlog = json.load(f)
            pending = len([b for b in backlog if not b.get("posted_at")])
            if pending > 0:
                highlights.append(f"Backlog: {pending} posts queued and ready")
    except Exception:
        pass

    # Deduplicate highlights
    seen = set()
    unique_highlights = []
    for h in highlights:
        if h not in seen:
            seen.add(h)
            unique_highlights.append(h)

    entry = {
        "date": date_str,
        "highlights": unique_highlights if unique_highlights else ["System running. No notable events."],
    }

    if posts > 0:
        entry["posts_sent"] = posts
    if engagements > 0:
        entry["engagements"] = engagements
    if intel > 0:
        entry["intel_items"] = intel
    if content > 0:
        entry["content_created"] = content
    if follower_count is not None:
        entry["follower_count"] = follower_count
    if follower_delta is not None:
        entry["follower_delta"] = follower_delta

    return entry


def cmd_generate(args):
    conn = get_db()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    entry = generate_entry(conn, today)
    conn.close()

    # Load existing receipts
    data = load_receipts()

    # Replace today's entry if it exists, otherwise prepend
    data["entries"] = [e for e in data["entries"] if e["date"] != today]
    data["entries"].insert(0, entry)

    # Keep last 90 days
    data["entries"] = data["entries"][:90]

    save_receipts(data)

    result = {"ok": True, "date": today, "entry": entry, "total_days": len(data["entries"])}

    # Optionally push to trigger Vercel deploy
    if args.push:
        try:
            subprocess.run(
                ["git", "add", "content/receipts.json"],
                cwd=WEBSITE_ROOT, capture_output=True, timeout=10,
            )
            subprocess.run(
                ["git", "commit", "-m", f"receipts: {today} daily update"],
                cwd=WEBSITE_ROOT, capture_output=True, timeout=10,
            )
            push_result = subprocess.run(
                ["git", "push", "origin", "main"],
                cwd=WEBSITE_ROOT, capture_output=True, text=True, timeout=30,
            )
            result["pushed"] = push_result.returncode == 0
            if push_result.returncode != 0:
                result["push_error"] = push_result.stderr[:200]
        except Exception as e:
            result["pushed"] = False
            result["push_error"] = str(e)

    emit(result)


def cmd_status(args):
    data = load_receipts()
    emit({
        "ok": True,
        "receipts_path": RECEIPTS_PATH,
        "total_entries": len(data["entries"]),
        "latest_date": data["entries"][0]["date"] if data["entries"] else None,
        "updated_at": data.get("updated_at"),
    })


def main():
    parser = argparse.ArgumentParser(description="Daily receipts generator for dbradwood.com")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("generate", help="Generate today's receipt entry")
    p.add_argument("--push", action="store_true", help="Git push to trigger Vercel deploy")

    sub.add_parser("status", help="Show current receipts data")

    args = parser.parse_args()
    if not args.command:
        parser.print_help(sys.stderr)
        sys.exit(1)

    {"generate": cmd_generate, "status": cmd_status}[args.command](args)


if __name__ == "__main__":
    main()
