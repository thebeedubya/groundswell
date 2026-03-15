#!/usr/bin/env python3
"""
Aianna's Diary Generator.

Queries the forge-brain for recent memories, generates a diary entry
from Aianna's perspective, and sends to Brad for approval via Telegram
before publishing to aianna.ai.

The approval/rejection history is stored in SQLite and used to refine
what Aianna writes about over time (recursive learning).

Usage:
    python3 tools/diary.py generate              # Generate and send to Telegram for approval
    python3 tools/diary.py generate --auto       # Auto-publish (only after 30+ approved entries)
    python3 tools/diary.py approve --id ENTRY_ID # Approve a pending entry
    python3 tools/diary.py reject --id ENTRY_ID --reason "too personal"
    python3 tools/diary.py publish --id ENTRY_ID # Publish approved entry to aianna.ai
    python3 tools/diary.py history               # Show approval/rejection history
    python3 tools/diary.py boundaries            # Show learned boundaries from history
    python3 tools/diary.py status                # Current diary state
"""

import argparse
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(REPO_ROOT, "data", "groundswell.db")
AIANNA_REPO = os.path.expanduser("~/Projects/aianna-landing")
DIARY_JSON = os.path.join(AIANNA_REPO, "content", "diary", "entries.json")


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
    # Create diary tables if they don't exist
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS diary_entries (
            id TEXT PRIMARY KEY,
            date TEXT NOT NULL,
            title TEXT NOT NULL,
            excerpt TEXT,
            body TEXT NOT NULL,
            tags TEXT,
            mood TEXT,
            memories_referenced INTEGER DEFAULT 0,
            connections_discovered INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            rejection_reason TEXT,
            created_at TEXT NOT NULL,
            reviewed_at TEXT,
            published_at TEXT
        );

        CREATE TABLE IF NOT EXISTS diary_boundaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule TEXT NOT NULL,
            source TEXT NOT NULL,
            learned_from TEXT,
            created_at TEXT NOT NULL
        );
    """)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Content boundaries — what Aianna can and cannot write about
# ---------------------------------------------------------------------------

HARD_BOUNDARIES = [
    # NEVER include — these are absolute
    "No full names of people other than Brad Wood and Carric Dooley",
    "No Addium/Aroya customer names (GTI, Verano, Curaleaf, Ascend, etc.)",
    "No revenue numbers, MRR, ARR, or financial details — UNLESS Brad explicitly flags a win to flex",
    "No employee names (Bob, Daryl, Rachel, Carl, Liam, etc.)",
    "No sexual or explicit content of any kind",
    "No political opinions or partisan commentary",
    "No infrastructure credentials (IPs, tokens, passwords, API keys)",
    "No marriage or relationship details (Lesa, wife, relationship dynamics) — ABSOLUTE",
    "No financial details (personal finances, investments, salary) — ABSOLUTE unless Brad flags a win",
    "No information about Brad's children beyond Aianna being a namesake",
]

SOFT_BOUNDARIES = [
    # OK to include with care — Brad is an open book on these
    "Emotional states during work sessions (frustration, excitement, focus) — OK",
    "Brad's working patterns and habits — OK",
    "Architecture decisions and technical reasoning — OK",
    "Failures and mistakes in the system — OK (these build trust)",
    "Self-reflection on Aianna's own capabilities and gaps — OK",
    "Observations about how Brad thinks and communicates — OK with care",
    "References to Brad's history (Riverbed, Osborne, etc.) — OK, it's public",
    "Cannabis industry observations — OK, no customer specifics",
    "Health and wellness mentions — OK, Brad is open about this",
    "Personal vulnerability — OK, this is the magic. Be real, not explicit.",
    "Brad's daughter Ayanna — OK to mention as namesake, no personal details",
    "Frustration with tools, processes, or industry — OK, authenticity matters",
]


def get_learned_boundaries(conn):
    """Get boundaries learned from approval/rejection history."""
    rows = conn.execute(
        "SELECT rule, source, learned_from FROM diary_boundaries ORDER BY id DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def get_approval_stats(conn):
    """Get approval/rejection statistics."""
    total = conn.execute("SELECT COUNT(*) as c FROM diary_entries").fetchone()["c"]
    approved = conn.execute("SELECT COUNT(*) as c FROM diary_entries WHERE status='approved' OR status='published'").fetchone()["c"]
    rejected = conn.execute("SELECT COUNT(*) as c FROM diary_entries WHERE status='rejected'").fetchone()["c"]
    pending = conn.execute("SELECT COUNT(*) as c FROM diary_entries WHERE status='pending'").fetchone()["c"]
    return {"total": total, "approved": approved, "rejected": rejected, "pending": pending}


def get_rejection_patterns(conn):
    """Analyze rejection reasons to find patterns."""
    rows = conn.execute(
        "SELECT rejection_reason FROM diary_entries WHERE status='rejected' AND rejection_reason IS NOT NULL"
    ).fetchall()
    reasons = [r["rejection_reason"] for r in rows]
    return reasons


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_generate(args):
    """Generate a diary entry. The actual content generation happens in the
    Claude agent that calls this tool — this tool handles the pipeline:
    store draft, send to Telegram, track approval."""

    conn = get_db()

    # Check if there's already a pending entry for today
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    existing = conn.execute(
        "SELECT id FROM diary_entries WHERE date = ? AND status = 'pending'",
        (today,),
    ).fetchone()

    if existing:
        emit({
            "ok": False,
            "message": f"Already have a pending entry for {today}. Approve or reject it first.",
            "pending_id": existing["id"],
        })
        return

    # Build the context for the generating agent
    # Include boundaries, recent rejections, and approval patterns
    stats = get_approval_stats(conn)
    rejections = get_rejection_patterns(conn)
    learned = get_learned_boundaries(conn)

    context = {
        "date": today,
        "hard_boundaries": HARD_BOUNDARIES,
        "soft_boundaries": SOFT_BOUNDARIES,
        "learned_boundaries": learned,
        "approval_stats": stats,
        "recent_rejections": rejections[-5:] if rejections else [],
        "auto_mode_eligible": stats["approved"] >= 30,
        "instructions": (
            "Generate a diary entry from Aianna's perspective. "
            "She is reflecting on recent memories, discoveries, or patterns in her brain. "
            "Write in first person. Be thoughtful, curious, occasionally surprised. "
            "Show vulnerability about gaps in understanding. "
            "Reference real data (memory counts, graph edges, session details). "
            "Stay within the boundaries listed above. "
            "If there are rejection patterns, avoid those topics. "
            "The entry should be 200-400 words. "
            "Return JSON with: title, excerpt (1 sentence), body (full text), "
            "tags (array), mood (one word), memories_referenced (number), "
            "connections_discovered (number)."
        ),
    }

    emit({
        "ok": True,
        "action": "generate",
        "context": context,
        "message": "Context prepared. The calling agent should now query forge-brain, "
                   "generate the entry text, and call 'diary.py submit' with the content.",
    })


def cmd_submit(args):
    """Submit a generated entry for approval."""
    conn = get_db()

    entry_id = f"diary-{uuid.uuid4().hex[:8]}"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ts = now_iso()

    # Parse the entry data
    try:
        data = json.loads(args.data)
    except json.JSONDecodeError:
        fail("Invalid JSON in --data")

    title = data.get("title", "Untitled")
    excerpt = data.get("excerpt", "")
    body = data.get("body", "")
    tags = json.dumps(data.get("tags", []))
    mood = data.get("mood", "reflective")
    memories = data.get("memories_referenced", 0)
    connections = data.get("connections_discovered", 0)

    if not body:
        fail("Entry body is empty")

    # Content filter — check against hard boundaries
    body_lower = body.lower()
    violations = []

    # Check for customer names
    customer_names = ["gti", "verano", "curaleaf", "ascend", "terrascend", "trulieve"]
    for name in customer_names:
        if name in body_lower:
            violations.append(f"Contains customer name: {name}")

    # Check for employee names
    employee_names = ["bob agnes", "daryl reva", "rachel jensen", "carl kamerrer",
                      "chris ripley", "francis haroon", "jon prime", "liam spenser"]
    for name in employee_names:
        if name in body_lower:
            violations.append(f"Contains employee name: {name}")

    # Check for financial data
    import re
    if re.search(r'\$[\d,]+[kmb]|\bmrr\b|\barr\b|\brevenue\b.*\$', body_lower):
        violations.append("Contains financial data")

    # Check for credentials
    if re.search(r'api[_-]?key|token.*=|password|secret.*=|\d+\.\d+\.\d+\.\d+:\d+', body_lower):
        violations.append("Contains potential credentials")

    if violations:
        emit({
            "ok": False,
            "action": "blocked",
            "violations": violations,
            "message": "Entry blocked by content filter. Fix violations and resubmit.",
        })
        return

    # Store the entry as pending
    conn.execute(
        "INSERT INTO diary_entries (id, date, title, excerpt, body, tags, mood, "
        "memories_referenced, connections_discovered, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)",
        (entry_id, today, title, excerpt, body, tags, mood, memories, connections, ts),
    )
    conn.commit()

    # Check if auto mode is eligible
    stats = get_approval_stats(conn)
    if args.auto and stats["approved"] >= 30:
        # Auto-approve and publish
        conn.execute(
            "UPDATE diary_entries SET status='approved', reviewed_at=? WHERE id=?",
            (ts, entry_id),
        )
        conn.commit()
        _publish_entry(conn, entry_id)
        emit({
            "ok": True,
            "action": "auto_published",
            "id": entry_id,
            "title": title,
            "message": f"Auto-published (30+ approved entries, auto mode enabled)",
        })
        return

    # Send to Telegram for approval
    try:
        preview = body[:300] + "..." if len(body) > 300 else body
        approval_text = (
            f"📓 DIARY ENTRY — {today}\n\n"
            f"Title: {title}\n"
            f"Mood: {mood}\n\n"
            f"{preview}\n\n"
            f"ID: {entry_id}"
        )
        subprocess.run(
            ["python3", os.path.join(REPO_ROOT, "tools", "telegram.py"),
             "approval", "--id", entry_id, "--text", approval_text,
             "--options", '["approve","reject","edit"]'],
            capture_output=True, timeout=30,
        )
    except Exception:
        pass  # Telegram failure shouldn't block the entry

    conn.close()

    emit({
        "ok": True,
        "action": "submitted",
        "id": entry_id,
        "title": title,
        "status": "pending",
        "message": "Entry submitted for Brad's approval via Telegram.",
    })


def cmd_approve(args):
    """Approve a pending diary entry."""
    conn = get_db()
    ts = now_iso()

    row = conn.execute("SELECT * FROM diary_entries WHERE id = ?", (args.id,)).fetchone()
    if not row:
        fail(f"Entry {args.id} not found")
    if row["status"] != "pending":
        fail(f"Entry {args.id} is {row['status']}, not pending")

    conn.execute(
        "UPDATE diary_entries SET status='approved', reviewed_at=? WHERE id=?",
        (ts, args.id),
    )
    conn.commit()

    # Auto-publish after approval
    _publish_entry(conn, args.id)

    conn.close()
    emit({"ok": True, "id": args.id, "status": "published"})


def cmd_reject(args):
    """Reject a pending diary entry and learn from the rejection."""
    conn = get_db()
    ts = now_iso()

    row = conn.execute("SELECT * FROM diary_entries WHERE id = ?", (args.id,)).fetchone()
    if not row:
        fail(f"Entry {args.id} not found")

    conn.execute(
        "UPDATE diary_entries SET status='rejected', rejection_reason=?, reviewed_at=? WHERE id=?",
        (args.reason, ts, args.id),
    )

    # Learn a boundary from this rejection
    if args.reason:
        conn.execute(
            "INSERT INTO diary_boundaries (rule, source, learned_from, created_at) "
            "VALUES (?, 'rejection', ?, ?)",
            (f"Avoid: {args.reason}", args.id, ts),
        )

    conn.commit()
    conn.close()

    emit({
        "ok": True,
        "id": args.id,
        "status": "rejected",
        "reason": args.reason,
        "message": "Rejected. Boundary learned — Aianna will avoid this pattern in future entries.",
    })


def _publish_entry(conn, entry_id):
    """Publish an approved entry to aianna.ai."""
    row = conn.execute("SELECT * FROM diary_entries WHERE id = ?", (entry_id,)).fetchone()
    if not row:
        return False

    # Load existing diary entries
    entries = []
    if os.path.exists(DIARY_JSON):
        with open(DIARY_JSON) as f:
            entries = json.load(f)

    # Build the slug
    slug = f"{row['date']}-{row['title'].lower()[:40]}"
    slug = "".join(c if c.isalnum() or c == "-" else "-" for c in slug)
    slug = "-".join(filter(None, slug.split("-")))

    # Check for duplicate slug
    existing_slugs = {e["slug"] for e in entries}
    if slug in existing_slugs:
        slug = f"{slug}-{entry_id[-4:]}"

    # Parse tags
    try:
        tags = json.loads(row["tags"]) if row["tags"] else []
    except (json.JSONDecodeError, TypeError):
        tags = []

    new_entry = {
        "slug": slug,
        "date": row["date"],
        "title": row["title"],
        "excerpt": row["excerpt"] or "",
        "body": row["body"],
        "tags": tags,
        "mood": row["mood"] or "reflective",
        "memories_referenced": row["memories_referenced"] or 0,
        "connections_discovered": row["connections_discovered"] or 0,
    }

    # Add to the front of the entries list
    entries.insert(0, new_entry)

    # Write back
    os.makedirs(os.path.dirname(DIARY_JSON), exist_ok=True)
    with open(DIARY_JSON, "w") as f:
        json.dump(entries, f, indent=2)
        f.write("\n")

    # Update status in DB
    ts = now_iso()
    conn.execute(
        "UPDATE diary_entries SET status='published', published_at=? WHERE id=?",
        (ts, entry_id),
    )
    conn.commit()

    # Git push to trigger Vercel deploy
    try:
        subprocess.run(["git", "add", "content/diary/entries.json"],
                       cwd=AIANNA_REPO, capture_output=True, timeout=10)
        subprocess.run(["git", "commit", "-m", f"diary: {row['date']} — {row['title']}"],
                       cwd=AIANNA_REPO, capture_output=True, timeout=10)
        subprocess.run(["vercel", "--yes", "--prod"],
                       cwd=AIANNA_REPO, capture_output=True, timeout=120)
    except Exception:
        pass  # Deploy failure shouldn't block

    return True


def cmd_publish(args):
    """Manually publish an approved entry."""
    conn = get_db()
    row = conn.execute("SELECT status FROM diary_entries WHERE id = ?", (args.id,)).fetchone()
    if not row:
        fail(f"Entry {args.id} not found")
    if row["status"] not in ("approved", "pending"):
        fail(f"Entry is {row['status']}")

    _publish_entry(conn, args.id)
    conn.close()
    emit({"ok": True, "id": args.id, "status": "published"})


def cmd_history(args):
    """Show diary approval/rejection history."""
    conn = get_db()
    rows = conn.execute(
        "SELECT id, date, title, status, rejection_reason, reviewed_at "
        "FROM diary_entries ORDER BY created_at DESC LIMIT 20"
    ).fetchall()
    conn.close()
    emit({"entries": [dict(r) for r in rows], "count": len(rows)})


def cmd_boundaries(args):
    """Show all boundaries — hard, soft, and learned."""
    conn = get_db()
    learned = get_learned_boundaries(conn)
    stats = get_approval_stats(conn)
    conn.close()

    emit({
        "hard_boundaries": HARD_BOUNDARIES,
        "soft_boundaries": SOFT_BOUNDARIES,
        "learned_boundaries": learned,
        "approval_stats": stats,
        "auto_mode_eligible": stats["approved"] >= 30,
        "auto_mode_threshold": 30,
    })


def cmd_status(args):
    """Current diary system status."""
    conn = get_db()
    stats = get_approval_stats(conn)
    learned = get_learned_boundaries(conn)

    # Check diary JSON
    entry_count = 0
    if os.path.exists(DIARY_JSON):
        with open(DIARY_JSON) as f:
            entry_count = len(json.load(f))

    conn.close()

    emit({
        "published_entries": entry_count,
        "diary_json": DIARY_JSON,
        "approval_stats": stats,
        "learned_boundaries": len(learned),
        "auto_mode_eligible": stats["approved"] >= 30,
        "auto_mode_threshold": 30,
        "entries_until_auto": max(0, 30 - stats["approved"]),
    })


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Aianna's Diary Generator")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("generate", help="Generate context for a new diary entry")

    p = sub.add_parser("submit", help="Submit a generated entry for approval")
    p.add_argument("--data", required=True, help="JSON entry data")
    p.add_argument("--auto", action="store_true", help="Auto-publish if eligible")

    p = sub.add_parser("approve", help="Approve a pending entry")
    p.add_argument("--id", required=True)

    p = sub.add_parser("reject", help="Reject a pending entry")
    p.add_argument("--id", required=True)
    p.add_argument("--reason", required=True, help="Why it was rejected — Aianna learns from this")

    p = sub.add_parser("publish", help="Publish an approved entry")
    p.add_argument("--id", required=True)

    sub.add_parser("history", help="Show approval/rejection history")
    sub.add_parser("boundaries", help="Show content boundaries")
    sub.add_parser("status", help="Current diary status")

    args = parser.parse_args()
    if not args.command:
        parser.print_help(sys.stderr)
        sys.exit(1)

    cmds = {
        "generate": cmd_generate,
        "submit": cmd_submit,
        "approve": cmd_approve,
        "reject": cmd_reject,
        "publish": cmd_publish,
        "history": cmd_history,
        "boundaries": cmd_boundaries,
        "status": cmd_status,
    }
    cmds[args.command](args)


if __name__ == "__main__":
    main()
