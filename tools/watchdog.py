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
            ["bash", "-c", "ps aux | grep 'run.sh' | grep -v grep | grep -v aianna-social | grep -c ."],
            capture_output=True, text=True, timeout=5,
        )
        count = int(result.stdout.strip() or "0")
        if count == 0:
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

    # 7. Verify actual platform posts exist (trust but verify)
    # Check last post_sent event for each platform and verify it's live
    for platform in ["x", "linkedin", "threads"]:
        last_post = conn.execute(
            "SELECT details FROM events WHERE event_type LIKE '%post_sent%' "
            "AND details LIKE ? AND timestamp > datetime('now', '-48 hours') "
            "ORDER BY id DESC LIMIT 1",
            (f'%{platform}%',),
        ).fetchone()

        if last_post and last_post["details"]:
            try:
                d = json.loads(last_post["details"])
                post_id = d.get("post_id")
                if not post_id:
                    continue

                verified = False

                # Try API verification first (X only)
                if platform == "x":
                    try:
                        result = subprocess.run(
                            ["python3", "tools/post.py", "verify", "--platform", "x", "--id", str(post_id)],
                            capture_output=True, text=True, timeout=15,
                            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        )
                        vdata = json.loads(result.stdout)
                        if vdata.get("verified") or vdata.get("ok"):
                            verified = True
                    except Exception:
                        pass

                # Playwright verification for all platforms (fallback or primary)
                if not verified:
                    try:
                        # Build the URL to check
                        if platform == "x":
                            check_url = f"https://x.com/thebeedubya/status/{post_id}"
                        elif platform == "linkedin":
                            check_url = f"https://www.linkedin.com/feed/update/{post_id}/"
                        elif platform == "threads":
                            # Threads blocks headless — verify via API instead
                            try:
                                threads_token = os.environ.get("THREADS_BRAD_ACCESS_TOKEN", "")
                                if threads_token:
                                    import urllib.request as _ur
                                    api_url = f"https://graph.threads.net/v1.0/{post_id}?fields=id&access_token={threads_token}"
                                    with _ur.urlopen(api_url, timeout=10) as resp:
                                        tdata = json.loads(resp.read().decode())
                                        if tdata.get("id"):
                                            verified = True
                                            continue
                            except Exception:
                                pass
                            continue  # Skip Playwright for Threads
                        else:
                            continue

                        result = subprocess.run(
                            ["python3", "-c", f"""
import asyncio
from playwright.async_api import async_playwright

async def verify():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto("{check_url}", timeout=15000)
            await page.wait_for_timeout(3000)
            # Check for error indicators
            content = await page.content()
            is_404 = "doesn't exist" in content or "not found" in content.lower() or "page isn't available" in content.lower()
            print("VERIFIED" if not is_404 else "NOT_FOUND")
        except:
            print("ERROR")
        finally:
            await browser.close()

asyncio.run(verify())
"""],
                            capture_output=True, text=True, timeout=25,
                            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        )
                        verdict = result.stdout.strip()
                        if verdict == "VERIFIED":
                            verified = True
                        elif verdict == "NOT_FOUND":
                            verified = False
                        # ERROR = inconclusive, don't alert
                        elif verdict == "ERROR":
                            continue

                    except Exception:
                        continue

                if not verified:
                    alerts.append({
                        "type": "ghost_post",
                        "severity": "high",
                        "message": f"{platform} post {str(post_id)[:30]} logged as sent but NOT found on platform. Ghost post.",
                    })

            except (json.JSONDecodeError, Exception):
                pass

    # 8. Monitor tracked campaign posts for engagement spikes
    tracked = conn.execute(
        "SELECT details FROM events WHERE agent = 'monitor' AND event_type = 'track_post' "
        "AND details LIKE '%monitor_until%' ORDER BY id DESC LIMIT 10"
    ).fetchall()

    for row in tracked:
        try:
            d = json.loads(row["details"])
            post_id = d.get("post_id")
            monitor_until = d.get("monitor_until", "")
            if not post_id or monitor_until < datetime.now(timezone.utc).strftime("%Y-%m-%d"):
                continue

            result = subprocess.run(
                ["python3", "tools/x_api.py", "tweet", "--id", str(post_id)],
                capture_output=True, text=True, timeout=15,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            )
            tdata = json.loads(result.stdout) if result.stdout else {}
            metrics = tdata.get("data", {}).get("data", {}).get("public_metrics", {})
            impressions = metrics.get("impression_count", 0)
            likes = metrics.get("like_count", 0)
            retweets = metrics.get("retweet_count", 0)
            replies = metrics.get("reply_count", 0)

            # Log metrics
            conn.execute(
                "INSERT INTO events (timestamp, agent, event_type, details) VALUES (?, ?, ?, ?)",
                (ts, "monitor", "post_metrics", json.dumps({
                    "post_id": post_id,
                    "label": d.get("label"),
                    "impressions": impressions,
                    "likes": likes,
                    "retweets": retweets,
                    "replies": replies,
                })),
            )

            # Alert on breakout (>500 impressions or any retweet from 64-follower account is significant)
            if retweets > 0 or likes >= 5 or impressions >= 500:
                alerts.append({
                    "type": "engagement_spike",
                    "severity": "info",
                    "message": f"Strix post {d.get('label','')}: {impressions} impressions, {likes} likes, {retweets} RTs, {replies} replies",
                })
        except Exception:
            pass

    conn.commit()

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
