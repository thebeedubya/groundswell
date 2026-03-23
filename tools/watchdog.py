#!/usr/bin/env python3
"""
Groundswell Watchdog — monitors agent health and alerts on failures.

Checks that all agents are running on schedule, posts are going out,
and no agent has gone silent. Alerts Brad via Telegram if something
is broken.

Zero Claude cost — pure Python.

Usage:
    python3 tools/watchdog.py check
"""

import argparse
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone

from _common import DB_PATH, emit, fail, now_iso, get_db


def check():
    """Run all health checks and alert on failures."""
    conn = get_db()
    conn.row_factory = sqlite3.Row
    ts = now_iso()
    now = datetime.now(timezone.utc)
    alerts = []

    # 1. Check for agents that haven't run when they should have
    overdue_threshold = timedelta(hours=2)
    rows = conn.execute(
        "SELECT task, agent, next_due, last_run, last_result FROM schedule WHERE enabled = 1"
    ).fetchall()

    for r in rows:
        if not r["next_due"]:
            continue
        try:
            due = datetime.fromisoformat(r["next_due"].replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue

        if now - due > overdue_threshold:
            alerts.append({
                "type": "agent_overdue",
                "severity": "high",
                "message": f"Agent '{r['task']}' overdue by {int((now - due).total_seconds() / 3600)}h. Last run: {r['last_run'] or 'never'}",
            })

    # 2. Check posting cadence — alert if no posts in 24h on any enabled platform
    for platform in ["x", "linkedin", "threads"]:
        count = conn.execute(
            "SELECT COUNT(*) as cnt FROM events WHERE event_type LIKE '%post_sent%' "
            "AND details LIKE ? AND timestamp > datetime('now', '-24 hours')",
            (f'%{platform}%',),
        ).fetchone()["cnt"]

        # Also check agent-specific post events
        if platform == "threads":
            count += conn.execute(
                "SELECT COUNT(*) as cnt FROM events WHERE agent = 'threads_agent' "
                "AND event_type = 'post_sent' AND timestamp > datetime('now', '-24 hours')"
            ).fetchone()["cnt"]

        if count == 0:
            # Check if it's a weekend and LinkedIn (expected)
            is_weekend = now.weekday() >= 5
            if platform == "linkedin" and is_weekend:
                continue  # Expected — no LinkedIn on weekends

            alerts.append({
                "type": "posting_gap",
                "severity": "high",
                "message": f"No {platform} posts in 24 hours. Backlog may not be routing to platform agents.",
            })

    # 3. Check for repeated errors
    error_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM events WHERE "
        "(event_type LIKE '%error%' OR event_type LIKE '%fail%') "
        "AND event_type NOT LIKE '%rate_limit%' "
        "AND timestamp > datetime('now', '-6 hours')"
    ).fetchone()["cnt"]

    if error_count >= 5:
        alerts.append({
            "type": "error_spike",
            "severity": "high",
            "message": f"{error_count} errors in last 6 hours. System may be degraded.",
        })

    # 4. Check backlog health
    try:
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "backlog.json")) as f:
            backlog = json.load(f)
        ready = len([b for b in backlog if b.get("status") == "ready"])
        if ready < 5:
            alerts.append({
                "type": "backlog_low",
                "severity": "medium",
                "message": f"Backlog has only {ready} ready items. Creator should replenish.",
            })
    except Exception:
        pass

    # 5. Check run.sh is alive
    try:
        result = subprocess.run(
            ["pgrep", "-f", "groundswell/run.sh"],
            capture_output=True, text=True, timeout=5,
        )
        if not result.stdout.strip():
            alerts.append({
                "type": "engine_down",
                "severity": "critical",
                "message": "Groundswell run.sh is NOT running. Engine is dead.",
            })
    except Exception:
        pass

    # 6. Check telegram bot is alive
    try:
        result = subprocess.run(
            ["pgrep", "-f", "telegram_bot.py"],
            capture_output=True, text=True, timeout=5,
        )
        if not result.stdout.strip():
            alerts.append({
                "type": "bot_down",
                "severity": "high",
                "message": "Telegram bot is NOT running. Approvals won't work.",
            })
    except Exception:
        pass

    # Send alerts to Telegram
    if alerts:
        alert_text = f"🚨 *Watchdog Alert* — {len(alerts)} issue(s)\n\n"
        for a in alerts:
            icon = "🔴" if a["severity"] == "critical" else "🟡" if a["severity"] == "high" else "⚪"
            alert_text += f"{icon} {a['message']}\n\n"

        try:
            subprocess.run(
                ["python3", "tools/telegram.py", "alert", "--level",
                 "critical" if any(a["severity"] == "critical" for a in alerts) else "warning",
                 "--text", alert_text],
                capture_output=True, timeout=15,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            )
        except Exception:
            pass

    # Log the check
    conn.execute(
        "INSERT INTO events (timestamp, agent, event_type, details) VALUES (?, ?, ?, ?)",
        (ts, "watchdog", "health_check", json.dumps({
            "alerts": len(alerts),
            "issues": [a["type"] for a in alerts],
        })),
    )
    conn.commit()
    conn.close()

    emit({
        "ok": len(alerts) == 0,
        "alerts": alerts,
        "timestamp": ts,
    })


def main():
    parser = argparse.ArgumentParser(description="Groundswell Watchdog")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("check", help="Run health checks")
    args = parser.parse_args()

    if args.command == "check":
        check()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
