#!/usr/bin/env python3
"""
Groundswell SQLite CRUD tool.

CLI tool that agents call via Bash. Uses subcommands with JSON output and exit code 0/1.

Usage:
    python3 tools/db.py init
    python3 tools/db.py state
    python3 tools/db.py log-event --agent X --type Y --details '{...}'
    python3 tools/db.py read-signals
    python3 tools/db.py write-signal --type HOT_TARGET --source outbound --data '{...}'
    python3 tools/db.py consume-signal --id 123
    python3 tools/db.py get-strategy
    python3 tools/db.py set-strategy --key X --value '{...}'
    python3 tools/db.py brand-safety
    python3 tools/db.py set-brand-safety --color RED --reason "..."
    python3 tools/db.py cooldowns
    python3 tools/db.py set-cooldown --platform x --minutes 60 --reason "rate limited"
    python3 tools/db.py clear-cooldown --platform x
    python3 tools/db.py tier-targets
    python3 tools/db.py add-target --handle @kim --tier 1 --platform x
    python3 tools/db.py pending-actions
    python3 tools/db.py add-action --key "reply:x:123" --agent outbound --type reply --payload '{...}'
    python3 tools/db.py update-action --key "reply:x:123" --status verified
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(REPO_ROOT, "data", "groundswell.db")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def get_connection(db_path=None):
    path = db_path or DEFAULT_DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def emit(data):
    json.dump(data, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    sys.exit(0)


def fail(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)


def rows_to_list(rows):
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    agent TEXT NOT NULL,
    event_type TEXT NOT NULL,
    details TEXT,
    failure_category TEXT,
    duration_ms INTEGER
);

CREATE TABLE IF NOT EXISTS pending_actions (
    idempotency_key TEXT PRIMARY KEY,
    agent TEXT NOT NULL,
    action_type TEXT NOT NULL,
    payload TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS platform_cooldowns (
    platform TEXT PRIMARY KEY,
    cooldown_until TEXT NOT NULL,
    reason TEXT,
    set_by TEXT
);

CREATE TABLE IF NOT EXISTS agent_heartbeats (
    agent TEXT PRIMARY KEY,
    last_heartbeat TEXT NOT NULL,
    status TEXT DEFAULT 'healthy'
);

CREATE TABLE IF NOT EXISTS strategy_state (
    key TEXT PRIMARY KEY,
    value TEXT,
    version INTEGER DEFAULT 1,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS tier_targets (
    handle TEXT PRIMARY KEY,
    tier INTEGER NOT NULL,
    platform TEXT DEFAULT 'x',
    last_interaction TEXT,
    interaction_count INTEGER DEFAULT 0,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS proof_stack (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    detail TEXT,
    evidence_path TEXT,
    tags TEXT,
    used_in TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schedule (
    task TEXT PRIMARY KEY,
    agent TEXT NOT NULL,
    interval_minutes INTEGER,
    daily_at TEXT,
    weekly_at TEXT,
    jitter_minutes INTEGER DEFAULT 0,
    timeout_seconds INTEGER DEFAULT 120,
    last_run TEXT,
    last_result TEXT,
    next_due TEXT,
    enabled BOOLEAN DEFAULT 1
);

CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    source_agent TEXT NOT NULL,
    data TEXT,
    priority INTEGER DEFAULT 5,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    consumed_at TEXT,
    consumed_by TEXT
);

CREATE TABLE IF NOT EXISTS content_genome (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id TEXT UNIQUE,
    platform TEXT NOT NULL,
    posted_at TEXT NOT NULL,
    hook_type TEXT,
    format TEXT,
    length_bucket TEXT,
    has_image BOOLEAN DEFAULT 0,
    has_video BOOLEAN DEFAULT 0,
    has_screenshot BOOLEAN DEFAULT 0,
    topic_cluster TEXT,
    emotional_register TEXT,
    identity_bucket TEXT,
    timing_hour INTEGER,
    timing_day TEXT,
    target_follower_count INTEGER,
    target_tier INTEGER,
    impressions INTEGER,
    likes INTEGER,
    replies INTEGER,
    reposts INTEGER,
    engagement_rate REAL,
    performance_multiple REAL,
    strategy_version INTEGER,
    outlier_suspected BOOLEAN DEFAULT 0,
    confounder_flags TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audience_graph (
    handle TEXT NOT NULL,
    platform TEXT NOT NULL,
    follower_count INTEGER,
    bio TEXT,
    account_cluster TEXT,
    total_interactions INTEGER DEFAULT 0,
    first_interaction TEXT,
    last_interaction TEXT,
    connector_score REAL DEFAULT 0.0,
    conversion_value REAL DEFAULT 0.0,
    PRIMARY KEY (handle, platform)
);

CREATE TABLE IF NOT EXISTS engagement_conversions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_type TEXT NOT NULL,
    platform TEXT NOT NULL,
    target_handle TEXT,
    target_tier INTEGER,
    topic TEXT,
    timing TEXT,
    touch_number INTEGER,
    followed_back BOOLEAN,
    follower_delta_24h INTEGER,
    follower_delta_72h INTEGER,
    created_at TEXT NOT NULL,
    checked_at TEXT
);

CREATE TABLE IF NOT EXISTS edit_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    draft_text TEXT NOT NULL,
    final_text TEXT NOT NULL,
    edit_classification TEXT,
    edit_magnitude REAL,
    specific_patterns TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS touchpoint_chain (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_handle TEXT NOT NULL,
    platform TEXT NOT NULL,
    touchpoint_sequence TEXT,
    outcome TEXT,
    days_to_follow REAL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pattern_effectiveness (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_key TEXT NOT NULL,
    platform TEXT NOT NULL,
    window_start TEXT NOT NULL,
    window_end TEXT NOT NULL,
    sample_count INTEGER,
    avg_performance REAL,
    trend_direction TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS learned_models (
    model_key TEXT PRIMARY KEY,
    model_version INTEGER DEFAULT 1,
    model_data TEXT,
    confidence REAL,
    sample_size INTEGER,
    updated_at TEXT NOT NULL
);
"""


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------

def cmd_init(args):
    conn = get_connection(args.db)
    conn.executescript(SCHEMA_SQL)
    conn.close()
    emit({"ok": True, "message": "All tables created"})


def cmd_state(args):
    conn = get_connection(args.db)

    # Brand safety
    row = conn.execute(
        "SELECT value FROM strategy_state WHERE key = 'brand_safety_color'"
    ).fetchone()
    brand_color = json.loads(row["value"]) if row else "GREEN"

    # Active cooldowns (not expired)
    ts = now_iso()
    cooldowns = rows_to_list(conn.execute(
        "SELECT * FROM platform_cooldowns WHERE cooldown_until > ?", (ts,)
    ).fetchall())

    # Pending signals
    pending_signals = conn.execute(
        "SELECT COUNT(*) as cnt FROM signals WHERE consumed_at IS NULL"
    ).fetchone()["cnt"]

    # Pending actions
    pending_actions = conn.execute(
        "SELECT COUNT(*) as cnt FROM pending_actions WHERE status = 'pending'"
    ).fetchone()["cnt"]

    # Recent events (last 20)
    recent_events = rows_to_list(conn.execute(
        "SELECT * FROM events ORDER BY id DESC LIMIT 20"
    ).fetchall())

    # Agent heartbeats
    heartbeats = rows_to_list(conn.execute(
        "SELECT * FROM agent_heartbeats"
    ).fetchall())

    conn.close()
    emit({
        "brand_safety_color": brand_color,
        "active_cooldowns": cooldowns,
        "pending_signal_count": pending_signals,
        "pending_action_count": pending_actions,
        "recent_events": recent_events,
        "agent_heartbeats": heartbeats,
    })


def cmd_log_event(args):
    conn = get_connection(args.db)
    ts = now_iso()
    conn.execute(
        "INSERT INTO events (timestamp, agent, event_type, details) VALUES (?, ?, ?, ?)",
        (ts, args.agent, args.type, args.details),
    )
    conn.commit()
    event_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    emit({"ok": True, "event_id": event_id, "timestamp": ts})


def cmd_read_signals(args):
    conn = get_connection(args.db)
    ts = now_iso()
    rows = conn.execute(
        "SELECT * FROM signals WHERE consumed_at IS NULL AND (expires_at IS NULL OR expires_at > ?) ORDER BY priority ASC, id ASC",
        (ts,),
    ).fetchall()
    conn.close()
    emit({"signals": rows_to_list(rows), "count": len(rows)})


def cmd_write_signal(args):
    conn = get_connection(args.db)
    ts = now_iso()
    priority = args.priority if args.priority is not None else 5
    conn.execute(
        "INSERT INTO signals (type, source_agent, data, priority, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
        (args.type, args.source, args.data, priority, ts, args.expires),
    )
    conn.commit()
    signal_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    emit({"ok": True, "signal_id": signal_id, "timestamp": ts})


def cmd_consume_signal(args):
    conn = get_connection(args.db)
    ts = now_iso()
    cur = conn.execute(
        "UPDATE signals SET consumed_at = ?, consumed_by = ? WHERE id = ? AND consumed_at IS NULL",
        (ts, args.by or "unknown", args.id),
    )
    conn.commit()
    if cur.rowcount == 0:
        conn.close()
        fail(f"Signal {args.id} not found or already consumed")
    conn.close()
    emit({"ok": True, "signal_id": args.id, "consumed_at": ts})


def cmd_get_strategy(args):
    conn = get_connection(args.db)
    rows = conn.execute("SELECT * FROM strategy_state ORDER BY key").fetchall()
    conn.close()
    result = {}
    for r in rows:
        try:
            result[r["key"]] = json.loads(r["value"])
        except (json.JSONDecodeError, TypeError):
            result[r["key"]] = r["value"]
    emit({"strategy": result})


def cmd_set_strategy(args):
    conn = get_connection(args.db)
    ts = now_iso()
    # Upsert with version increment
    existing = conn.execute(
        "SELECT version FROM strategy_state WHERE key = ?", (args.key,)
    ).fetchone()
    new_version = (existing["version"] + 1) if existing else 1
    conn.execute(
        "INSERT INTO strategy_state (key, value, version, updated_at) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, version = ?, updated_at = excluded.updated_at",
        (args.key, args.value, new_version, ts, new_version),
    )
    conn.commit()
    conn.close()
    emit({"ok": True, "key": args.key, "version": new_version, "updated_at": ts})


def cmd_brand_safety(args):
    conn = get_connection(args.db)
    row = conn.execute(
        "SELECT value, updated_at FROM strategy_state WHERE key = 'brand_safety_color'"
    ).fetchone()
    conn.close()
    if row:
        try:
            color = json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            color = row["value"]
        emit({"color": color, "updated_at": row["updated_at"]})
    else:
        emit({"color": "GREEN", "updated_at": None})


def cmd_set_brand_safety(args):
    conn = get_connection(args.db)
    ts = now_iso()
    color = args.color.upper()
    if color not in ("GREEN", "YELLOW", "RED", "BLACK"):
        conn.close()
        fail(f"Invalid brand safety color: {color}. Must be GREEN, YELLOW, RED, or BLACK.")
    value = json.dumps(color)
    existing = conn.execute(
        "SELECT version FROM strategy_state WHERE key = 'brand_safety_color'"
    ).fetchone()
    new_version = (existing["version"] + 1) if existing else 1
    conn.execute(
        "INSERT INTO strategy_state (key, value, version, updated_at) VALUES ('brand_safety_color', ?, ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, version = ?, updated_at = excluded.updated_at",
        (value, new_version, ts, new_version),
    )
    # Log event
    details = json.dumps({"color": color, "reason": args.reason})
    conn.execute(
        "INSERT INTO events (timestamp, agent, event_type, details) VALUES (?, 'system', 'brand_safety_change', ?)",
        (ts, details),
    )
    conn.commit()
    conn.close()
    emit({"ok": True, "color": color, "version": new_version, "updated_at": ts})


def cmd_cooldowns(args):
    conn = get_connection(args.db)
    ts = now_iso()
    rows = conn.execute(
        "SELECT * FROM platform_cooldowns WHERE cooldown_until > ?", (ts,)
    ).fetchall()
    conn.close()
    emit({"cooldowns": rows_to_list(rows), "count": len(rows)})


def cmd_set_cooldown(args):
    conn = get_connection(args.db)
    ts = now_iso()
    until = (datetime.now(timezone.utc) + timedelta(minutes=args.minutes)).isoformat().replace("+00:00", "Z")
    conn.execute(
        "INSERT INTO platform_cooldowns (platform, cooldown_until, reason, set_by) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(platform) DO UPDATE SET cooldown_until = excluded.cooldown_until, reason = excluded.reason, set_by = excluded.set_by",
        (args.platform, until, args.reason, args.set_by or "system"),
    )
    conn.commit()
    conn.close()
    emit({"ok": True, "platform": args.platform, "cooldown_until": until})


def cmd_clear_cooldown(args):
    conn = get_connection(args.db)
    cur = conn.execute(
        "DELETE FROM platform_cooldowns WHERE platform = ?", (args.platform,)
    )
    conn.commit()
    if cur.rowcount == 0:
        conn.close()
        fail(f"No cooldown found for platform: {args.platform}")
    conn.close()
    emit({"ok": True, "platform": args.platform, "message": "Cooldown cleared"})


def cmd_tier_targets(args):
    conn = get_connection(args.db)
    rows = conn.execute(
        "SELECT * FROM tier_targets ORDER BY tier ASC, handle ASC"
    ).fetchall()
    conn.close()
    emit({"targets": rows_to_list(rows), "count": len(rows)})


def cmd_add_target(args):
    conn = get_connection(args.db)
    ts = now_iso()
    handle = args.handle.lstrip("@")
    try:
        conn.execute(
            "INSERT INTO tier_targets (handle, tier, platform, notes) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(handle) DO UPDATE SET tier = excluded.tier, platform = excluded.platform, notes = excluded.notes",
            (handle, args.tier, args.platform or "x", args.notes),
        )
        conn.commit()
    except sqlite3.Error as e:
        conn.close()
        fail(f"Failed to add target: {e}")
    conn.close()
    emit({"ok": True, "handle": args.handle, "tier": args.tier, "platform": args.platform or "x"})


def cmd_pending_actions(args):
    conn = get_connection(args.db)
    rows = conn.execute(
        "SELECT * FROM pending_actions WHERE status = 'pending' ORDER BY created_at ASC"
    ).fetchall()
    conn.close()
    emit({"actions": rows_to_list(rows), "count": len(rows)})


def cmd_add_action(args):
    conn = get_connection(args.db)
    ts = now_iso()
    try:
        conn.execute(
            "INSERT INTO pending_actions (idempotency_key, agent, action_type, payload, status, created_at) "
            "VALUES (?, ?, ?, ?, 'pending', ?)",
            (args.key, args.agent, args.type, args.payload, ts),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        fail(f"Action with key '{args.key}' already exists (idempotency guard)")
    conn.close()
    emit({"ok": True, "key": args.key, "status": "pending", "created_at": ts})


def cmd_update_action(args):
    conn = get_connection(args.db)
    ts = now_iso()
    completed = ts if args.status in ("completed", "failed", "rejected") else None
    cur = conn.execute(
        "UPDATE pending_actions SET status = ?, completed_at = COALESCE(?, completed_at) WHERE idempotency_key = ?",
        (args.status, completed, args.key),
    )
    conn.commit()
    if cur.rowcount == 0:
        conn.close()
        fail(f"Action with key '{args.key}' not found")
    conn.close()
    emit({"ok": True, "key": args.key, "status": args.status, "updated_at": ts})


# ---------------------------------------------------------------------------
# CLI parser
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        description="Groundswell SQLite CRUD tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--db", default=None, help="Override database path")
    sub = parser.add_subparsers(dest="command")

    # init
    sub.add_parser("init", help="Create all tables")

    # state
    sub.add_parser("state", help="Full system state JSON")

    # log-event
    p = sub.add_parser("log-event", help="Log an event")
    p.add_argument("--agent", required=True)
    p.add_argument("--type", required=True)
    p.add_argument("--details", default=None)

    # read-signals
    sub.add_parser("read-signals", help="Pending unconsumed signals")

    # write-signal
    p = sub.add_parser("write-signal", help="Write a signal")
    p.add_argument("--type", required=True)
    p.add_argument("--source", required=True)
    p.add_argument("--data", default=None)
    p.add_argument("--priority", type=int, default=None)
    p.add_argument("--expires", default=None)

    # consume-signal
    p = sub.add_parser("consume-signal", help="Consume a signal")
    p.add_argument("--id", type=int, required=True)
    p.add_argument("--by", default=None)

    # get-strategy
    sub.add_parser("get-strategy", help="Current learned weights")

    # set-strategy
    p = sub.add_parser("set-strategy", help="Set a strategy key")
    p.add_argument("--key", required=True)
    p.add_argument("--value", required=True)

    # brand-safety
    sub.add_parser("brand-safety", help="Current brand safety color")

    # set-brand-safety
    p = sub.add_parser("set-brand-safety", help="Set brand safety color")
    p.add_argument("--color", required=True)
    p.add_argument("--reason", default="")

    # cooldowns
    sub.add_parser("cooldowns", help="Active platform cooldowns")

    # set-cooldown
    p = sub.add_parser("set-cooldown", help="Set a platform cooldown")
    p.add_argument("--platform", required=True)
    p.add_argument("--minutes", type=int, required=True)
    p.add_argument("--reason", default="")
    p.add_argument("--set-by", default=None)

    # clear-cooldown
    p = sub.add_parser("clear-cooldown", help="Clear a platform cooldown")
    p.add_argument("--platform", required=True)

    # tier-targets
    sub.add_parser("tier-targets", help="All tier targets")

    # add-target
    p = sub.add_parser("add-target", help="Add or update a tier target")
    p.add_argument("--handle", required=True)
    p.add_argument("--tier", type=int, required=True)
    p.add_argument("--platform", default="x")
    p.add_argument("--notes", default=None)

    # pending-actions
    sub.add_parser("pending-actions", help="Pending actions")

    # add-action
    p = sub.add_parser("add-action", help="Add a pending action")
    p.add_argument("--key", required=True)
    p.add_argument("--agent", required=True)
    p.add_argument("--type", required=True)
    p.add_argument("--payload", default=None)

    # update-action
    p = sub.add_parser("update-action", help="Update action status")
    p.add_argument("--key", required=True)
    p.add_argument("--status", required=True)

    return parser


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

COMMANDS = {
    "init": cmd_init,
    "state": cmd_state,
    "log-event": cmd_log_event,
    "read-signals": cmd_read_signals,
    "write-signal": cmd_write_signal,
    "consume-signal": cmd_consume_signal,
    "get-strategy": cmd_get_strategy,
    "set-strategy": cmd_set_strategy,
    "brand-safety": cmd_brand_safety,
    "set-brand-safety": cmd_set_brand_safety,
    "cooldowns": cmd_cooldowns,
    "set-cooldown": cmd_set_cooldown,
    "clear-cooldown": cmd_clear_cooldown,
    "tier-targets": cmd_tier_targets,
    "add-target": cmd_add_target,
    "pending-actions": cmd_pending_actions,
    "add-action": cmd_add_action,
    "update-action": cmd_update_action,
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
    except Exception as e:
        fail(f"Error: {e}")


if __name__ == "__main__":
    main()
