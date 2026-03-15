#!/usr/bin/env python3
"""Schedule state management CLI for Groundswell.

Agents are ephemeral (Claude Code subagents that exit after each cycle),
so schedule state persists in SQLite. This tool manages the schedule table.

Usage:
    python3 tools/schedule.py init              # Seed schedule from config.yaml
    python3 tools/schedule.py due               # Tasks currently due
    python3 tools/schedule.py status            # Full schedule state
    python3 tools/schedule.py complete --task X # Mark done, compute next_due
    python3 tools/schedule.py next-sleep        # Seconds until next task
    python3 tools/schedule.py enable --task X   # Enable a task
    python3 tools/schedule.py disable --task X  # Disable a task
"""

import argparse
import json
import os
import random
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

# Resolve paths relative to the repo root (parent of tools/)
REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "data" / "groundswell.db"
CONFIG_PATH = REPO_ROOT / "config.yaml"

SCHEDULE_DDL = """\
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
"""

DAY_NAMES = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


def get_db() -> sqlite3.Connection:
    """Open (or create) the database and ensure the schedule table exists."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute(SCHEDULE_DDL)
    conn.commit()
    return conn


def load_config() -> dict:
    """Load config.yaml from the repo root."""
    if not CONFIG_PATH.exists():
        print(json.dumps({"error": f"Config not found: {CONFIG_PATH}"}), file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def get_tz(config: dict) -> ZoneInfo:
    """Return the configured timezone."""
    tz_name = config.get("schedule", {}).get("timezone", "America/Chicago")
    return ZoneInfo(tz_name)


def utcnow() -> datetime:
    """Current time in UTC, timezone-aware."""
    return datetime.now(ZoneInfo("UTC"))


def iso(dt: datetime) -> str:
    """Format a datetime as ISO 8601 with timezone."""
    return dt.isoformat()


# ── next_due computation ────────────────────────────────────────────────

def compute_next_due_interval(now_utc: datetime, interval_minutes: int, jitter_minutes: int) -> datetime:
    """Next due = now + interval + random jitter."""
    jitter = random.randint(0, jitter_minutes) if jitter_minutes else 0
    return now_utc + timedelta(minutes=interval_minutes + jitter)


def compute_next_due_daily(now_utc: datetime, daily_at: list[str], tz: ZoneInfo, jitter_minutes: int) -> datetime:
    """Next due = earliest future occurrence from the daily_at list."""
    now_local = now_utc.astimezone(tz)
    candidates = []
    for time_str in sorted(daily_at):
        hour, minute = map(int, time_str.split(":"))
        candidate = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now_local:
            candidate += timedelta(days=1)
        candidates.append(candidate)

    earliest = min(candidates)
    jitter = random.randint(0, jitter_minutes) if jitter_minutes else 0
    result = earliest + timedelta(minutes=jitter)
    return result.astimezone(ZoneInfo("UTC"))


def compute_next_due_weekly(now_utc: datetime, weekly_at: str, tz: ZoneInfo, jitter_minutes: int) -> datetime:
    """Next due = next occurrence of 'dayname HH:MM'."""
    parts = weekly_at.strip().lower().split()
    day_name = parts[0]
    time_str = parts[1]
    target_weekday = DAY_NAMES[day_name]
    hour, minute = map(int, time_str.split(":"))

    now_local = now_utc.astimezone(tz)
    candidate = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)

    # Advance to the target weekday
    days_ahead = (target_weekday - candidate.weekday()) % 7
    candidate += timedelta(days=days_ahead)

    # If it's today but already past, push to next week
    if candidate <= now_local:
        candidate += timedelta(weeks=1)

    jitter = random.randint(0, jitter_minutes) if jitter_minutes else 0
    result = candidate + timedelta(minutes=jitter)
    return result.astimezone(ZoneInfo("UTC"))


def compute_next_due(task_cfg: dict, now_utc: datetime, tz: ZoneInfo) -> datetime:
    """Dispatch to the correct next_due computation based on task type."""
    jitter = task_cfg.get("jitter_minutes", 0)
    if task_cfg.get("daily_at"):
        return compute_next_due_daily(now_utc, task_cfg["daily_at"], tz, jitter)
    elif task_cfg.get("weekly_at"):
        return compute_next_due_weekly(now_utc, task_cfg["weekly_at"], tz, jitter)
    elif task_cfg.get("interval_minutes"):
        return compute_next_due_interval(now_utc, task_cfg["interval_minutes"], jitter)
    else:
        # Fallback: 5 minutes from now
        return now_utc + timedelta(minutes=5)


# ── CLI commands ────────────────────────────────────────────────────────

def cmd_init(args):
    """Seed schedule table from config.yaml."""
    config = load_config()
    tz = get_tz(config)
    tasks = config.get("schedule", {}).get("tasks", {})
    now = utcnow()
    conn = get_db()
    count = 0

    for task_name, task_cfg in tasks.items():
        next_due = compute_next_due(task_cfg, now, tz)
        daily_at = json.dumps(task_cfg["daily_at"]) if task_cfg.get("daily_at") else None
        weekly_at = task_cfg.get("weekly_at")

        conn.execute(
            """INSERT INTO schedule (task, agent, interval_minutes, daily_at, weekly_at,
                                     jitter_minutes, timeout_seconds, next_due, enabled)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(task) DO UPDATE SET
                   agent=excluded.agent,
                   interval_minutes=excluded.interval_minutes,
                   daily_at=excluded.daily_at,
                   weekly_at=excluded.weekly_at,
                   jitter_minutes=excluded.jitter_minutes,
                   timeout_seconds=excluded.timeout_seconds,
                   next_due=excluded.next_due,
                   enabled=excluded.enabled
            """,
            (
                task_name,
                task_cfg["agent"],
                task_cfg.get("interval_minutes"),
                daily_at,
                weekly_at,
                task_cfg.get("jitter_minutes", 0),
                task_cfg.get("timeout_seconds", 120),
                iso(next_due),
                1 if task_cfg.get("enabled", True) else 0,
            ),
        )
        count += 1

    conn.commit()
    conn.close()
    print(json.dumps({"ok": True, "tasks_seeded": count}))


def cmd_due(args):
    """Return tasks that are currently due."""
    conn = get_db()
    now = utcnow()

    # Check brand_safety in strategy_state if the table exists
    try:
        row = conn.execute(
            "SELECT value FROM strategy_state WHERE key = 'brand_safety'"
        ).fetchone()
        if row and row["value"] == "BLACK":
            print(json.dumps({"due": [], "warning": "brand_safety is BLACK — all tasks halted"}))
            conn.close()
            return
    except sqlite3.OperationalError:
        pass  # strategy_state table doesn't exist yet — that's fine

    rows = conn.execute(
        """SELECT task, agent, timeout_seconds, next_due
           FROM schedule
           WHERE enabled = 1 AND next_due <= ?
           ORDER BY next_due ASC""",
        (iso(now),),
    ).fetchall()

    due_list = [
        {"task": r["task"], "agent": r["agent"], "timeout_seconds": r["timeout_seconds"]}
        for r in rows
    ]

    print(json.dumps({"due": due_list, "now": iso(now)}))
    conn.close()


def cmd_complete(args):
    """Mark a task complete and compute next_due."""
    task_name = args.task
    config = load_config()
    tz = get_tz(config)
    tasks_cfg = config.get("schedule", {}).get("tasks", {})
    conn = get_db()
    now = utcnow()

    row = conn.execute("SELECT * FROM schedule WHERE task = ?", (task_name,)).fetchone()
    if not row:
        print(json.dumps({"error": f"Task not found: {task_name}"}), file=sys.stderr)
        sys.exit(1)

    # Build a task_cfg dict from the DB row (or config if available)
    if task_name in tasks_cfg:
        task_cfg = tasks_cfg[task_name]
    else:
        # Reconstruct from DB row
        task_cfg = {
            "interval_minutes": row["interval_minutes"],
            "daily_at": json.loads(row["daily_at"]) if row["daily_at"] else None,
            "weekly_at": row["weekly_at"],
            "jitter_minutes": row["jitter_minutes"] or 0,
        }

    next_due = compute_next_due(task_cfg, now, tz)

    conn.execute(
        """UPDATE schedule
           SET last_run = ?, last_result = 'success', next_due = ?
           WHERE task = ?""",
        (iso(now), iso(next_due), task_name),
    )
    conn.commit()
    conn.close()

    print(json.dumps({"ok": True, "task": task_name, "next_due": iso(next_due)}))


def cmd_next_sleep(args):
    """Print seconds until next due task (integer only)."""
    conn = get_db()
    now = utcnow()

    row = conn.execute(
        """SELECT MIN(next_due) as earliest
           FROM schedule
           WHERE enabled = 1"""
    ).fetchone()
    conn.close()

    if not row or not row["earliest"]:
        print(300)
        return

    earliest = datetime.fromisoformat(row["earliest"])
    # Ensure timezone-aware comparison
    if earliest.tzinfo is None:
        earliest = earliest.replace(tzinfo=ZoneInfo("UTC"))

    delta = (earliest - now).total_seconds()
    seconds = int(max(10, delta))
    print(seconds)


def cmd_status(args):
    """Print full schedule state as JSON."""
    conn = get_db()
    now = utcnow()
    rows = conn.execute("SELECT * FROM schedule ORDER BY next_due ASC").fetchall()
    conn.close()

    tasks = []
    for r in rows:
        tasks.append({
            "task": r["task"],
            "agent": r["agent"],
            "interval_minutes": r["interval_minutes"],
            "daily_at": json.loads(r["daily_at"]) if r["daily_at"] else None,
            "weekly_at": r["weekly_at"],
            "jitter_minutes": r["jitter_minutes"],
            "timeout_seconds": r["timeout_seconds"],
            "last_run": r["last_run"],
            "last_result": r["last_result"],
            "next_due": r["next_due"],
            "enabled": bool(r["enabled"]),
        })

    print(json.dumps({"now": iso(now), "tasks": tasks}, indent=2))


def cmd_enable(args):
    """Enable a task."""
    conn = get_db()
    cur = conn.execute("UPDATE schedule SET enabled = 1 WHERE task = ?", (args.task,))
    conn.commit()
    if cur.rowcount == 0:
        print(json.dumps({"error": f"Task not found: {args.task}"}), file=sys.stderr)
        conn.close()
        sys.exit(1)
    conn.close()
    print(json.dumps({"ok": True, "task": args.task, "enabled": True}))


def cmd_disable(args):
    """Disable a task."""
    conn = get_db()
    cur = conn.execute("UPDATE schedule SET enabled = 0 WHERE task = ?", (args.task,))
    conn.commit()
    if cur.rowcount == 0:
        print(json.dumps({"error": f"Task not found: {args.task}"}), file=sys.stderr)
        conn.close()
        sys.exit(1)
    conn.close()
    print(json.dumps({"ok": True, "task": args.task, "enabled": False}))


# ── Main ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Groundswell schedule manager")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Seed schedule from config.yaml")
    sub.add_parser("due", help="Show tasks currently due")
    sub.add_parser("status", help="Full schedule state")
    sub.add_parser("next-sleep", help="Seconds until next task (integer)")

    p_complete = sub.add_parser("complete", help="Mark task complete")
    p_complete.add_argument("--task", required=True, help="Task name")

    p_enable = sub.add_parser("enable", help="Enable a task")
    p_enable.add_argument("--task", required=True, help="Task name")

    p_disable = sub.add_parser("disable", help="Disable a task")
    p_disable.add_argument("--task", required=True, help="Task name")

    args = parser.parse_args()

    dispatch = {
        "init": cmd_init,
        "due": cmd_due,
        "complete": cmd_complete,
        "next-sleep": cmd_next_sleep,
        "status": cmd_status,
        "enable": cmd_enable,
        "disable": cmd_disable,
    }

    try:
        dispatch[args.command](args)
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
