#!/usr/bin/env python3
"""
Groundswell Newsroom — cinematic ops-center visualization of the 7-agent system.

Usage:
    python3 tools/newsroom.py [--port 8501]
"""

import argparse
import json
import os
import sqlite3
import sys
import urllib.parse
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(REPO_ROOT, "data", "groundswell.db")

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def rows_to_list(rows):
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Data queries
# ---------------------------------------------------------------------------

def get_brand_safety(conn):
    row = conn.execute(
        "SELECT value, updated_at FROM strategy_state WHERE key = 'brand_safety_color'"
    ).fetchone()
    if row:
        try:
            color = json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            color = row["value"]
        return {"color": color, "updated_at": row["updated_at"]}
    return {"color": "GREEN", "updated_at": None}


def get_trust_phase(conn):
    row = conn.execute(
        "SELECT value FROM strategy_state WHERE key = 'trust_phase'"
    ).fetchone()
    if row:
        try:
            return json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            return row["value"]
    return "A"


def get_recent_events(conn, limit=30):
    rows = conn.execute(
        "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return rows_to_list(rows)


def get_pending_signals(conn):
    ts = now_iso()
    rows = conn.execute(
        "SELECT * FROM signals WHERE consumed_at IS NULL "
        "AND (expires_at IS NULL OR expires_at > ?) "
        "ORDER BY priority ASC, id ASC",
        (ts,),
    ).fetchall()
    return rows_to_list(rows)


def get_agent_status(conn):
    rows = conn.execute(
        "SELECT agent, MAX(timestamp) as last_active, event_type "
        "FROM events GROUP BY agent"
    ).fetchall()
    return rows_to_list(rows)


def get_schedule(conn):
    rows = conn.execute(
        "SELECT * FROM schedule ORDER BY next_due ASC LIMIT 5"
    ).fetchall()
    return rows_to_list(rows)


def get_quick_stats(conn):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%dT")
    from datetime import timedelta
    one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")

    posts_today = conn.execute(
        "SELECT COUNT(*) as cnt FROM events WHERE event_type LIKE '%post%' AND timestamp >= ?",
        (today,),
    ).fetchone()["cnt"]

    actions_hour = conn.execute(
        "SELECT COUNT(*) as cnt FROM events WHERE timestamp >= ?",
        (one_hour_ago,),
    ).fetchone()["cnt"]

    pending_signals = conn.execute(
        "SELECT COUNT(*) as cnt FROM signals WHERE consumed_at IS NULL"
    ).fetchone()["cnt"]

    pending_actions = conn.execute(
        "SELECT COUNT(*) as cnt FROM pending_actions WHERE status = 'pending'"
    ).fetchone()["cnt"]

    return {
        "posts_today": posts_today,
        "actions_this_hour": actions_hour,
        "pending_signals": pending_signals,
        "pending_approvals": pending_actions,
    }


def _make_headline(agent, event_type, details):
    """Produce a human-readable headline from an event."""
    a = (agent or "system").lower()
    et = (event_type or "").lower()

    if a == "scout":
        if "scan" in et:
            trends = details.get("trends_found", details.get("trends", "?"))
            opps = details.get("opportunities", 0)
            return f"Scout completed scan: {trends} trends, {opps} opportunities"
        if "trend" in et:
            return f"Trend detected: {details.get('topic', details.get('trend', 'unknown'))}"
        if "opportunity" in et or "newsjack" in et:
            return f"Opportunity: {details.get('topic', details.get('title', 'new opening'))}"
        if "competitive" in et:
            return f"Competitive intel: {details.get('competitor', details.get('target', 'rival activity'))}"
        return f"Scout: {event_type}"

    if "outbound" in a:
        if "scan" in et:
            query = details.get("query", details.get("topic", ""))
            count = details.get("candidates", details.get("count", "?"))
            return f"Outbound scanned: '{query}' — {count} candidates"
        if "engage" in et or "reply" in et:
            target = details.get("target", details.get("username", "unknown"))
            return f"Engaged with @{target}"
        return f"Outbound: {event_type}"

    if "inbound" in a:
        if "reply" in et:
            target = details.get("username", details.get("target", "someone"))
            topic = details.get("topic", details.get("thread", ""))
            return f"Replied to @{target}" + (f" on {topic}" if topic else "")
        if "mention" in et:
            return f"Mention detected from @{details.get('username', 'unknown')}"
        return f"Inbound: {event_type}"

    if "publisher" in a:
        if "post" in et or "publish" in et:
            title = details.get("title", details.get("content", "content"))
            if len(title) > 50:
                title = title[:47] + "..."
            return f"Published: {title}"
        return f"Publisher: {event_type}"

    if "creator" in a:
        if "draft" in et or "create" in et:
            return f"Drafted: {details.get('title', details.get('type', 'content'))}"
        return f"Creator: {event_type}"

    if "analyst" in a:
        if "report" in et or "analysis" in et:
            return f"Analysis: {details.get('topic', details.get('metric', 'report ready'))}"
        return f"Analyst: {event_type}"

    if "orchestrat" in a:
        return f"Orchestrator: {event_type}"

    return f"{agent}: {event_type}"


def _make_detail(details):
    """Produce a brief detail line from event details."""
    if not details:
        return ""
    # Try common fields
    for key in ("summary", "description", "message", "reason", "content", "text"):
        if key in details:
            val = str(details[key])
            return val[:120] + "..." if len(val) > 120 else val
    # Fallback: compact json
    compact = json.dumps(details)
    return compact[:100] + "..." if len(compact) > 100 else compact


def _categorize(agent, event_type):
    """Categorize a feed item for color-coding."""
    a = (agent or "").lower()
    et = (event_type or "").lower()

    if "urgent" in et or "spike" in et or "alert" in et:
        return "urgent"
    if "opportunity" in et or "newsjack" in et:
        return "opportunity"
    if a == "scout" or "scan" in et or "trend" in et or "competitive" in et:
        return "intel"
    if "signal" in et or "hot" in et or "breakout" in et:
        return "signal"
    # engagement / posts
    if "outbound" in a or "inbound" in a or "publisher" in a or "post" in et or "engage" in et or "reply" in et:
        return "engagement"
    return "intel"


def get_feed_items(conn, limit=50):
    """Aggregate intel feed, events, and signals into a unified feed.

    Intel feed items are the primary source — these are the actual news
    items Scout finds. Events and signals provide supporting context.
    """
    items = []

    # 1. Intel feed — the real news (from intel_feed table)
    try:
        intel_rows = conn.execute(
            "SELECT * FROM intel_feed ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        for r in intel_rows:
            r = dict(r)
            cat = r.get("category", "intel")
            # Map intel categories to feed categories
            cat_map = {
                "trend": "intel", "tier1_activity": "intel",
                "newsjack": "urgent", "competitive": "intel",
                "opportunity": "opportunity", "conversation": "engagement",
                "seo": "intel", "seo_alert": "urgent",
                "ranking": "intel", "indexing": "intel",
            }
            items.append({
                "id": f"intel-{r['id']}",
                "type": "intel",
                "source": r.get("source_agent", "scout"),
                "event_type": r.get("category", ""),
                "headline": r.get("headline", ""),
                "detail": r.get("detail", ""),
                "timestamp": r.get("created_at", ""),
                "category": cat_map.get(cat, "intel"),
                "target": r.get("target_handle", ""),
                "url": r.get("source_url", ""),
                "relevance": r.get("relevance_score", 0.5),
                "acted_on": bool(r.get("acted_on", 0)),
                "tags": r.get("tags", ""),
                "raw": {},
            })
    except Exception:
        pass  # Table might not exist yet

    # 2. Key agent events (engagement activity)
    rows = conn.execute(
        "SELECT * FROM events WHERE agent IN ('outbound_engager', 'inbound', 'publisher') "
        "AND event_type IN ('post_sent', 'reply_sent', 'qt_sent', 'engagement_sent') "
        "ORDER BY id DESC LIMIT 20"
    ).fetchall()
    for r in rows:
        r = dict(r)
        try:
            details = json.loads(r["details"]) if r.get("details") else {}
        except (json.JSONDecodeError, TypeError):
            details = {}
        items.append({
            "id": r["id"],
            "type": "event",
            "source": r["agent"],
            "event_type": r.get("event_type", ""),
            "headline": _make_headline(r["agent"], r.get("event_type", ""), details),
            "detail": _make_detail(details),
            "timestamp": r.get("timestamp", ""),
            "category": "engagement",
            "raw": details,
        })

    # 3. Pending signals (urgent items)
    signals = conn.execute(
        "SELECT * FROM signals WHERE consumed_at IS NULL ORDER BY id DESC LIMIT 10"
    ).fetchall()
    for s in signals:
        s = dict(s)
        try:
            data = json.loads(s["data"]) if s.get("data") else {}
        except (json.JSONDecodeError, TypeError):
            data = {}
        items.append({
            "id": f"sig-{s['id']}",
            "type": "signal",
            "source": s.get("source_agent", "system"),
            "event_type": s.get("type", "SIGNAL"),
            "headline": f"SIGNAL: {s.get('type', 'UNKNOWN')}",
            "detail": json.dumps(data)[:100] if data else "",
            "timestamp": s.get("created_at", ""),
            "category": "signal",
            "raw": data,
        })

    # Sort by timestamp descending
    items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return items[:limit]


def create_command_signal(conn, item_id, action, context=None):
    """Create a signal in the database from a manual command."""
    action_map = {
        "reply": "MANUAL_ENGAGE",
        "qt": "MANUAL_QT",
        "create": "MANUAL_CREATE",
        "boost": "MANUAL_BOOST",
    }
    signal_type = action_map.get(action)
    if not signal_type:
        return None

    ts = now_iso()
    data = json.dumps({
        "source_item_id": item_id,
        "action": action,
        "context": context or {},
        "created_by": "newsroom_ui",
    })

    cursor = conn.execute(
        "INSERT INTO signals (type, source_agent, data, priority, created_at) "
        "VALUES (?, 'newsroom', ?, 3, ?)",
        (signal_type, data, ts),
    )

    # If this is an intel feed item, mark it as acted on
    if isinstance(item_id, str) and item_id.startswith("intel-"):
        try:
            intel_id = int(item_id.replace("intel-", ""))
            conn.execute(
                "UPDATE intel_feed SET acted_on = 1, acted_action = ? WHERE id = ?",
                (action, intel_id),
            )
        except (ValueError, TypeError):
            pass

    conn.commit()
    return {
        "signal_id": cursor.lastrowid,
        "type": signal_type,
        "created_at": ts,
    }


def get_api_usage(conn):
    """Get API usage counts for the current month."""
    month_start = datetime.now(timezone.utc).strftime("%Y-%m-01T00:00:00Z")
    month_label = datetime.now(timezone.utc).strftime("%Y-%m")

    budgets = {
        "x_reads_per_month": 10000,
        "x_writes_per_month": 1500,
        "linkedin_writes_per_month": 60,
    }

    try:
        rows = conn.execute(
            "SELECT platform, call_type, COUNT(*) as cnt "
            "FROM api_usage WHERE created_at >= ? "
            "GROUP BY platform, call_type",
            (month_start,),
        ).fetchall()
    except Exception:
        # Table might not exist yet
        return {
            "month": month_label,
            "x_reads": 0, "x_writes": 0, "linkedin_writes": 0,
            "total": 0, "budgets": budgets,
        }

    counts = {}
    for r in rows:
        key = f"{r['platform']}_{r['call_type']}"
        counts[key] = r["cnt"]

    x_reads = counts.get("x_read", 0)
    x_writes = counts.get("x_write", 0)
    linkedin_writes = counts.get("linkedin_write", 0)

    return {
        "month": month_label,
        "x_reads": x_reads,
        "x_writes": x_writes,
        "linkedin_writes": linkedin_writes,
        "total": x_reads + x_writes + linkedin_writes,
        "budgets": budgets,
    }


def get_full_state(conn):
    return {
        "brand_safety": get_brand_safety(conn),
        "trust_phase": get_trust_phase(conn),
        "agents": get_agent_status(conn),
        "events": get_recent_events(conn, limit=30),
        "signals": get_pending_signals(conn),
        "schedule": get_schedule(conn),
        "stats": get_quick_stats(conn),
        "feed": get_feed_items(conn, limit=50),
        "usage": get_api_usage(conn),
        "timestamp": now_iso(),
    }


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GROUNDSWELL — Newsroom</title>
<style>
/* ========================================================================
   RESET & BASE
   ======================================================================== */
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:100%;height:100%;overflow:hidden}
body{
  background:#0a0e14;
  color:#c9d1d9;
  font-family:'SF Mono','Cascadia Code','Fira Code','Consolas','Courier New',monospace;
  font-size:13px;
  line-height:1.4;
}

/* ========================================================================
   LAYOUT GRID — full viewport
   ======================================================================== */
.page{
  display:grid;
  grid-template-rows:56px 1fr 44px;
  grid-template-columns:320px 1fr 240px;
  grid-template-areas:
    "topbar   topbar   topbar"
    "newsfeed floor    sidebar"
    "ticker   ticker   ticker";
  width:100vw;height:100vh;
}

/* ========================================================================
   TOP BAR
   ======================================================================== */
.topbar{
  grid-area:topbar;
  display:flex;align-items:center;justify-content:space-between;
  padding:0 24px;
  background:linear-gradient(180deg,#111820 0%,#0d1218 100%);
  border-bottom:1px solid #1b2330;
  z-index:10;
}
.topbar-left{display:flex;align-items:center;gap:20px}
.topbar-title{
  font-size:22px;font-weight:700;letter-spacing:6px;
  color:#c9d1d9;
  text-shadow:0 0 20px rgba(88,166,255,.3),0 0 60px rgba(88,166,255,.1);
}
.safety-dot{
  width:12px;height:12px;border-radius:50%;
  display:inline-block;flex-shrink:0;
  box-shadow:0 0 8px currentColor;
}
.safety-GREEN{background:#3fb950;color:#3fb950}
.safety-YELLOW{background:#d29922;color:#d29922}
.safety-RED{background:#f85149;color:#f85149}
.safety-BLACK{background:#484f58;color:#484f58}
.safety-badge{display:flex;align-items:center;gap:8px}
.safety-label{font-size:11px;font-weight:600;letter-spacing:1px}
.trust-badge{
  padding:2px 10px;border-radius:3px;font-size:11px;font-weight:700;
  background:#1b2330;border:1px solid #30363d;letter-spacing:2px;
}
.topbar-right{display:flex;align-items:center;gap:20px}
.clock{font-size:14px;color:#8b949e;letter-spacing:1px;font-variant-numeric:tabular-nums}

/* ========================================================================
   MAIN FLOOR
   ======================================================================== */
.floor{
  grid-area:floor;
  position:relative;
  overflow:hidden;
  background:
    radial-gradient(ellipse 80% 60% at 50% 50%,rgba(88,166,255,.03) 0%,transparent 70%),
    #0a0e14;
}

/* grid lines on the floor */
.floor::before{
  content:'';position:absolute;inset:0;
  background-image:
    linear-gradient(rgba(88,166,255,.04) 1px,transparent 1px),
    linear-gradient(90deg,rgba(88,166,255,.04) 1px,transparent 1px);
  background-size:60px 60px;
  pointer-events:none;
}

/* scan lines overlay */
.floor::after{
  content:'';position:absolute;inset:0;
  background:repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(0,0,0,.03) 2px,
    rgba(0,0,0,.03) 4px
  );
  pointer-events:none;
  z-index:5;
}

/* radar sweep */
.radar-sweep{
  position:absolute;
  width:600px;height:600px;
  left:50%;top:50%;
  transform:translate(-50%,-50%);
  border-radius:50%;
  pointer-events:none;
  z-index:1;
  opacity:.15;
}
.radar-sweep::after{
  content:'';position:absolute;inset:0;
  border-radius:50%;
  background:conic-gradient(
    from 0deg,
    transparent 0deg,
    rgba(88,166,255,.3) 30deg,
    transparent 60deg
  );
  animation:radarSpin 8s linear infinite;
}
@keyframes radarSpin{to{transform:rotate(360deg)}}

/* ========================================================================
   SVG CONNECTION LINES
   ======================================================================== */
.connections-svg{
  position:absolute;inset:0;
  width:100%;height:100%;
  pointer-events:none;
  z-index:2;
}
.conn-line{
  stroke:#1b2330;stroke-width:1;
  stroke-dasharray:6 4;
  fill:none;
}
.conn-line.active{
  stroke:#58a6ff;stroke-width:1.5;
  animation:linePulse 2s ease-in-out infinite;
}
@keyframes linePulse{
  0%,100%{opacity:.3}
  50%{opacity:.8}
}

/* ========================================================================
   AGENT STATIONS
   ======================================================================== */
.agent-station{
  position:absolute;
  display:flex;flex-direction:column;align-items:center;
  z-index:4;
  transform:translate(-50%,-50%);
  cursor:default;
  transition:all .6s ease;
}
.agent-avatar{
  width:72px;height:72px;
  border-radius:50%;
  display:flex;align-items:center;justify-content:center;
  font-size:28px;
  background:#111820;
  border:3px solid #30363d;
  box-shadow:0 0 0 0 transparent;
  transition:border-color .6s ease,box-shadow .6s ease;
  position:relative;
}
.agent-station.idle .agent-avatar{
  border-color:#30363d;
  animation:idlePulse 4s ease-in-out infinite;
}
.agent-station.active .agent-avatar{
  border-color:#3fb950;
  box-shadow:0 0 20px rgba(63,185,80,.4),0 0 40px rgba(63,185,80,.15);
  animation:activePulse 1.5s ease-in-out infinite;
}
.agent-station.recent .agent-avatar{
  border-color:#58a6ff;
  box-shadow:0 0 12px rgba(88,166,255,.2);
  animation:idlePulse 3s ease-in-out infinite;
}
.agent-station.warning .agent-avatar{
  border-color:#d29922;
  box-shadow:0 0 20px rgba(210,153,34,.4);
  animation:activePulse 1s ease-in-out infinite;
}
.agent-station.error .agent-avatar{
  border-color:#f85149;
  box-shadow:0 0 20px rgba(248,81,73,.5);
  animation:activePulse .8s ease-in-out infinite;
}

@keyframes idlePulse{
  0%,100%{opacity:.6;transform:scale(1)}
  50%{opacity:.8;transform:scale(1.02)}
}
@keyframes activePulse{
  0%,100%{transform:scale(1)}
  50%{transform:scale(1.06)}
}

/* flash when agent just activated */
.agent-station.flash .agent-avatar::after{
  content:'';position:absolute;inset:-6px;
  border-radius:50%;
  border:2px solid rgba(63,185,80,.6);
  animation:flashRing .8s ease-out forwards;
}
@keyframes flashRing{
  0%{transform:scale(1);opacity:1}
  100%{transform:scale(1.5);opacity:0}
}

.agent-name{
  margin-top:8px;
  font-size:11px;font-weight:600;
  letter-spacing:1px;
  text-transform:uppercase;
  color:#8b949e;
  transition:color .6s ease;
}
.agent-station.active .agent-name{color:#c9d1d9}

.agent-status{
  margin-top:3px;
  font-size:10px;
  color:#484f58;
  max-width:140px;
  text-align:center;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
  transition:color .6s ease;
}
.agent-station.active .agent-status{color:#8b949e}

/* ========================================================================
   SIGNAL FLARES
   ======================================================================== */
.signal-flare{
  position:absolute;
  z-index:6;
  padding:3px 8px;
  border-radius:10px;
  font-size:10px;font-weight:700;
  letter-spacing:.5px;
  color:#fff;
  background:rgba(210,153,34,.85);
  border:1px solid rgba(210,153,34,.6);
  box-shadow:0 0 12px rgba(210,153,34,.4);
  animation:flarePulse 2s ease-in-out infinite;
  pointer-events:none;
  white-space:nowrap;
  transform:translate(-50%,-50%);
}
.signal-flare.hot{background:rgba(248,81,73,.85);border-color:rgba(248,81,73,.6);box-shadow:0 0 12px rgba(248,81,73,.4)}
.signal-flare.info{background:rgba(88,166,255,.85);border-color:rgba(88,166,255,.6);box-shadow:0 0 12px rgba(88,166,255,.4)}
@keyframes flarePulse{
  0%,100%{opacity:.85;transform:translate(-50%,-50%) scale(1)}
  50%{opacity:1;transform:translate(-50%,-50%) scale(1.08)}
}

/* ========================================================================
   SIDEBAR
   ======================================================================== */
.sidebar{
  grid-area:sidebar;
  background:#0d1218;
  border-left:1px solid #1b2330;
  padding:16px;
  overflow-y:auto;
  z-index:3;
}
.sidebar h2{
  font-size:10px;font-weight:600;
  text-transform:uppercase;letter-spacing:2px;
  color:#484f58;margin-bottom:10px;
  padding-bottom:6px;
  border-bottom:1px solid #1b2330;
}
.stat-item{
  display:flex;justify-content:space-between;align-items:baseline;
  padding:6px 0;
  border-bottom:1px solid #111820;
}
.stat-label{font-size:11px;color:#8b949e}
.stat-value{font-size:16px;font-weight:700;color:#58a6ff;font-variant-numeric:tabular-nums}
.stat-value.highlight{color:#3fb950}
.stat-value.warn{color:#d29922}

.schedule-item{
  padding:6px 0;
  border-bottom:1px solid #111820;
}
.schedule-task{font-size:11px;color:#c9d1d9;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.schedule-meta{font-size:10px;color:#484f58;margin-top:2px}
.schedule-countdown{color:#d29922;font-weight:600}

.sidebar-section{margin-bottom:20px}

/* ========================================================================
   TICKER
   ======================================================================== */
.ticker{
  grid-area:ticker;
  background:linear-gradient(180deg,#0d1218 0%,#111820 100%);
  border-top:1px solid #1b2330;
  overflow:hidden;
  position:relative;
  z-index:10;
  display:flex;
  align-items:center;
}
.ticker-label{
  flex-shrink:0;
  padding:0 16px;
  font-size:10px;font-weight:700;
  letter-spacing:2px;
  color:#484f58;
  border-right:1px solid #1b2330;
  height:100%;
  display:flex;align-items:center;
}
.ticker-track{
  flex:1;
  overflow:hidden;
  position:relative;
  height:100%;
  display:flex;align-items:center;
  mask-image:linear-gradient(90deg,transparent 0%,black 3%,black 97%,transparent 100%);
  -webkit-mask-image:linear-gradient(90deg,transparent 0%,black 3%,black 97%,transparent 100%);
}
.ticker-content{
  display:flex;
  gap:40px;
  white-space:nowrap;
  animation:tickerScroll var(--ticker-duration,60s) linear infinite;
  padding-left:100%;
}
.ticker-content:hover{animation-play-state:paused}
@keyframes tickerScroll{
  0%{transform:translateX(0)}
  100%{transform:translateX(-50%)}
}
.ticker-item{
  display:inline-flex;align-items:center;gap:8px;
  font-size:12px;color:#8b949e;
  flex-shrink:0;
}
.ticker-agent{font-weight:700;letter-spacing:.5px}
.ticker-sep{color:#30363d}
.ticker-time{color:#484f58;font-size:11px}

/* agent accent colors for ticker */
.ac-orchestrator{color:#58a6ff}
.ac-publisher{color:#3fb950}
.ac-outbound{color:#d2a8ff}
.ac-inbound{color:#79c0ff}
.ac-analyst{color:#d29922}
.ac-creator{color:#f0883e}
.ac-scout{color:#56d364}
.ac-dashboard{color:#8b949e}

/* ========================================================================
   PARTICLES (very subtle ambient)
   ======================================================================== */
.particle{
  position:absolute;
  width:2px;height:2px;
  background:rgba(88,166,255,.3);
  border-radius:50%;
  pointer-events:none;
  z-index:1;
  animation:particleFloat linear infinite;
}
@keyframes particleFloat{
  0%{opacity:0;transform:translateY(0)}
  10%{opacity:1}
  90%{opacity:1}
  100%{opacity:0;transform:translateY(-200px)}
}

/* ========================================================================
   NEWS FEED (Bloomberg-style left sidebar)
   ======================================================================== */
.newsfeed{
  grid-area:newsfeed;
  background:#0c1018;
  border-right:1px solid #1b2330;
  overflow-y:auto;
  scrollbar-width:thin;
  scrollbar-color:#30363d #0c1018;
}
.feed-header{
  position:sticky;
  top:0;
  background:#0c1018;
  padding:12px 16px;
  border-bottom:1px solid #1b2330;
  display:flex;
  align-items:center;
  gap:8px;
  font-size:11px;
  letter-spacing:3px;
  color:#58a6ff;
  z-index:5;
}
.feed-live-dot{
  width:6px;height:6px;border-radius:50%;
  background:#3fb950;
  animation:livePulse 2s ease-in-out infinite;
}
@keyframes livePulse{
  0%,100%{opacity:.4;box-shadow:0 0 2px #3fb950}
  50%{opacity:1;box-shadow:0 0 8px #3fb950}
}
.feed-count{
  margin-left:auto;
  font-size:10px;
  color:#484f58;
  letter-spacing:0;
}
.feed-item{
  padding:10px 16px;
  border-bottom:1px solid #161b22;
  border-left:3px solid transparent;
  cursor:pointer;
  transition:background 0.2s;
  position:relative;
}
.feed-item:nth-child(odd){background:#0d1117}
.feed-item:nth-child(even){background:#111820}
.feed-item:hover{background:#161b22}
.feed-item.category-intel{border-left-color:#58a6ff}
.feed-item.category-engagement{border-left-color:#3fb950}
.feed-item.category-signal{border-left-color:#d29922}
.feed-item.category-opportunity{border-left-color:#d2a8ff}
.feed-item.category-urgent{border-left-color:#f85149}
.feed-item.new{animation:feedFlash 1s ease-out}
@keyframes feedFlash{
  0%{background:rgba(88,166,255,.15)}
  100%{background:transparent}
}
.feed-item-header{
  display:flex;
  align-items:center;
  gap:6px;
  margin-bottom:3px;
}
.feed-time{font-size:10px;color:#484f58;flex-shrink:0}
.feed-source{
  padding:1px 6px;
  border-radius:8px;
  font-size:9px;
  font-weight:700;
  letter-spacing:.5px;
  text-transform:uppercase;
  flex-shrink:0;
}
.feed-source.src-scout{background:rgba(86,211,100,.15);color:#56d364}
.feed-source.src-outbound{background:rgba(210,168,255,.15);color:#d2a8ff}
.feed-source.src-inbound{background:rgba(121,192,255,.15);color:#79c0ff}
.feed-source.src-publisher{background:rgba(63,185,80,.15);color:#3fb950}
.feed-source.src-creator{background:rgba(240,136,62,.15);color:#f0883e}
.feed-source.src-analyst{background:rgba(210,153,34,.15);color:#d29922}
.feed-source.src-orchestrator{background:rgba(88,166,255,.15);color:#58a6ff}
.feed-source.src-system{background:rgba(139,148,158,.15);color:#8b949e}
.feed-headline{
  font-size:12px;
  color:#c9d1d9;
  line-height:1.3;
  margin-bottom:2px;
}
.feed-detail{
  font-size:10px;
  color:#484f58;
  line-height:1.3;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
}
.feed-act-btn{
  position:absolute;
  top:10px;right:10px;
  padding:2px 8px;
  font-size:9px;
  font-weight:700;
  letter-spacing:1px;
  border:1px solid #30363d;
  border-radius:3px;
  background:#0d1117;
  color:#58a6ff;
  cursor:pointer;
  font-family:inherit;
  opacity:0;
  transition:opacity 0.15s;
}
.feed-item:hover .feed-act-btn{opacity:1}
.feed-act-btn:hover{background:#58a6ff;color:#0a0e14;border-color:#58a6ff}
.feed-actions{
  display:none;
  padding:8px 16px;
  background:#161b22;
  border-bottom:1px solid #1b2330;
  gap:6px;
  flex-wrap:wrap;
}
.feed-actions.active{display:flex}
.feed-action-btn{
  padding:4px 10px;
  font-size:10px;
  border:1px solid #30363d;
  border-radius:4px;
  background:#0d1117;
  color:#c9d1d9;
  cursor:pointer;
  font-family:inherit;
  letter-spacing:1px;
  transition:all 0.15s;
}
.feed-action-btn:hover{
  background:#58a6ff;
  color:#0a0e14;
  border-color:#58a6ff;
}
.feed-action-btn.queued{
  background:#3fb950;
  color:#0a0e14;
  border-color:#3fb950;
  pointer-events:none;
}

/* ========================================================================
   SCROLLBAR
   ======================================================================== */
::-webkit-scrollbar{width:4px}
::-webkit-scrollbar-track{background:#0a0e14}
::-webkit-scrollbar-thumb{background:#21262d;border-radius:2px}
::-webkit-scrollbar-thumb:hover{background:#30363d}
</style>
</head>
<body>
<div class="page">

  <!-- ============ TOP BAR ============ -->
  <div class="topbar">
    <div class="topbar-left">
      <div class="topbar-title">GROUNDSWELL</div>
      <div class="safety-badge">
        <span id="safety-dot" class="safety-dot safety-GREEN"></span>
        <span id="safety-label" class="safety-label" style="color:#3fb950">GREEN</span>
      </div>
      <div class="trust-badge" id="trust-badge">PHASE A</div>
    </div>
    <div class="topbar-right">
      <div class="clock" id="clock">00:00:00 UTC</div>
    </div>
  </div>

  <!-- ============ NEWS FEED (Bloomberg-style) ============ -->
  <div class="newsfeed" id="newsfeed">
    <div class="feed-header">
      <div class="feed-live-dot"></div>
      INTEL FEED
      <span class="feed-count" id="feed-count">0 items</span>
    </div>
    <div id="feed-list"></div>
  </div>

  <!-- ============ MAIN FLOOR ============ -->
  <div class="floor" id="floor">
    <div class="radar-sweep"></div>

    <!-- SVG for connection lines -->
    <svg class="connections-svg" id="connections-svg"></svg>

    <!-- Agent stations — positioned by JS -->
    <div class="agent-station idle" id="agent-scout" data-agent="scout">
      <div class="agent-avatar">&#x1F50D;</div>
      <div class="agent-name">Scout</div>
      <div class="agent-status" id="status-scout">Idle</div>
    </div>
    <div class="agent-station idle" id="agent-analyst" data-agent="analyst">
      <div class="agent-avatar">&#x1F4CA;</div>
      <div class="agent-name">Analyst</div>
      <div class="agent-status" id="status-analyst">Idle</div>
    </div>
    <div class="agent-station idle" id="agent-outbound" data-agent="outbound">
      <div class="agent-avatar">&#x1F4E4;</div>
      <div class="agent-name">Outbound</div>
      <div class="agent-status" id="status-outbound">Idle</div>
    </div>
    <div class="agent-station idle" id="agent-orchestrator" data-agent="orchestrator">
      <div class="agent-avatar">&#x1F3AF;</div>
      <div class="agent-name">Orchestrator</div>
      <div class="agent-status" id="status-orchestrator">Idle</div>
    </div>
    <div class="agent-station idle" id="agent-inbound" data-agent="inbound">
      <div class="agent-avatar">&#x1F4E5;</div>
      <div class="agent-name">Inbound</div>
      <div class="agent-status" id="status-inbound">Idle</div>
    </div>
    <div class="agent-station idle" id="agent-creator" data-agent="creator">
      <div class="agent-avatar">&#x270D;&#xFE0F;</div>
      <div class="agent-name">Creator</div>
      <div class="agent-status" id="status-creator">Idle</div>
    </div>
    <div class="agent-station idle" id="agent-publisher" data-agent="publisher">
      <div class="agent-avatar">&#x1F4F0;</div>
      <div class="agent-name">Publisher</div>
      <div class="agent-status" id="status-publisher">Idle</div>
    </div>

    <!-- Signal flares container -->
    <div id="flares-container"></div>
  </div>

  <!-- ============ SIDEBAR ============ -->
  <div class="sidebar">
    <div class="sidebar-section">
      <h2>System Stats</h2>
      <div class="stat-item">
        <span class="stat-label">Posts Today</span>
        <span class="stat-value highlight" id="stat-posts">0</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">Actions / hr</span>
        <span class="stat-value" id="stat-actions">0</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">Pending Signals</span>
        <span class="stat-value warn" id="stat-signals">0</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">Backlog</span>
        <span class="stat-value" id="stat-backlog">0</span>
      </div>
    </div>

    <div class="sidebar-section">
      <h2>API Usage</h2>
      <div id="usage-meters">
        <div style="margin-bottom:8px">
          <div style="display:flex;justify-content:space-between;font-size:10px;margin-bottom:3px">
            <span class="stat-label">X Reads</span>
            <span id="usage-x-reads-label" style="color:#8b949e">0 / 10,000</span>
          </div>
          <div style="background:#161b22;border-radius:3px;height:6px;overflow:hidden">
            <div id="usage-x-reads-bar" style="height:100%;width:0%;border-radius:3px;transition:width 0.6s ease,background 0.6s ease;background:#3fb950"></div>
          </div>
        </div>
        <div style="margin-bottom:8px">
          <div style="display:flex;justify-content:space-between;font-size:10px;margin-bottom:3px">
            <span class="stat-label">X Writes</span>
            <span id="usage-x-writes-label" style="color:#8b949e">0 / 1,500</span>
          </div>
          <div style="background:#161b22;border-radius:3px;height:6px;overflow:hidden">
            <div id="usage-x-writes-bar" style="height:100%;width:0%;border-radius:3px;transition:width 0.6s ease,background 0.6s ease;background:#3fb950"></div>
          </div>
        </div>
        <div style="margin-bottom:8px">
          <div style="display:flex;justify-content:space-between;font-size:10px;margin-bottom:3px">
            <span class="stat-label">LinkedIn</span>
            <span id="usage-linkedin-label" style="color:#8b949e">0 / 60</span>
          </div>
          <div style="background:#161b22;border-radius:3px;height:6px;overflow:hidden">
            <div id="usage-linkedin-bar" style="height:100%;width:0%;border-radius:3px;transition:width 0.6s ease,background 0.6s ease;background:#3fb950"></div>
          </div>
        </div>
      </div>
    </div>

    <div class="sidebar-section">
      <h2>Next Up</h2>
      <div id="schedule-list">
        <div style="color:#484f58;font-size:11px;font-style:italic">Loading...</div>
      </div>
    </div>

    <div class="sidebar-section">
      <h2>Agent Legend</h2>
      <div style="font-size:10px;line-height:2">
        <div><span class="ac-orchestrator">&#9679;</span> <span class="ac-orchestrator">Orchestrator</span></div>
        <div><span class="ac-publisher">&#9679;</span> <span class="ac-publisher">Publisher</span></div>
        <div><span class="ac-outbound">&#9679;</span> <span class="ac-outbound">Outbound</span></div>
        <div><span class="ac-inbound">&#9679;</span> <span class="ac-inbound">Inbound</span></div>
        <div><span class="ac-analyst">&#9679;</span> <span class="ac-analyst">Analyst</span></div>
        <div><span class="ac-creator">&#9679;</span> <span class="ac-creator">Creator</span></div>
        <div><span class="ac-scout">&#9679;</span> <span class="ac-scout">Scout</span></div>
      </div>
    </div>
  </div>

  <!-- ============ TICKER ============ -->
  <div class="ticker">
    <div class="ticker-label">LIVE</div>
    <div class="ticker-track">
      <div class="ticker-content" id="ticker-content">
        <span class="ticker-item" style="color:#484f58">Awaiting events...</span>
      </div>
    </div>
  </div>

</div>

<script>
/* =====================================================================
   CONFIG
   ===================================================================== */
var AGENTS = {
  orchestrator: {emoji:'\u{1F3AF}', color:'#58a6ff', x:.50, y:.48},
  scout:        {emoji:'\u{1F50D}', color:'#56d364', x:.28, y:.24},
  analyst:      {emoji:'\u{1F4CA}', color:'#d29922', x:.72, y:.24},
  outbound:     {emoji:'\u{1F4E4}', color:'#d2a8ff', x:.24, y:.48},
  inbound:      {emoji:'\u{1F4E5}', color:'#79c0ff', x:.76, y:.48},
  creator:      {emoji:'\u{270D}\u{FE0F}', color:'#f0883e', x:.28, y:.72},
  publisher:    {emoji:'\u{1F4F0}', color:'#3fb950', x:.72, y:.72}
};

/* connection topology — lines between agents */
var CONNECTIONS = [
  ['orchestrator','scout'],
  ['orchestrator','analyst'],
  ['orchestrator','outbound'],
  ['orchestrator','inbound'],
  ['orchestrator','creator'],
  ['orchestrator','publisher'],
  ['scout','outbound'],
  ['scout','analyst'],
  ['analyst','creator'],
  ['creator','publisher'],
  ['inbound','outbound']
];

/* map signal types to agent stations */
var SIGNAL_AGENT_MAP = {
  'HOT_TARGET': 'outbound',
  'BREAKOUT_DETECTED': 'analyst',
  'CONTENT_LOW': 'creator',
  'TREND_ALERT': 'scout',
  'PUBLISH_READY': 'publisher',
  'MENTION_SPIKE': 'inbound'
};

var prevAgentStates = {};
var seenEventIds = {};
var tickerEvents = [];

/* =====================================================================
   UTILITIES
   ===================================================================== */
function esc(s){
  if(s==null) return '';
  var d=document.createElement('div');
  d.textContent=String(s);
  return d.innerHTML;
}

function timeAgo(iso){
  if(!iso) return '';
  var d=new Date(iso);
  var now=new Date();
  var sec=Math.floor((now-d)/1000);
  if(sec<0) sec=0;
  if(sec<60) return sec+'s ago';
  var min=Math.floor(sec/60);
  if(min<60) return min+'m ago';
  var hr=Math.floor(min/60);
  if(hr<24) return hr+'h ago';
  return Math.floor(hr/24)+'d ago';
}

function normalizeAgent(name){
  if(!name) return '';
  var n=name.toLowerCase().replace(/[^a-z]/g,'');
  /* handle common variations */
  if(n.indexOf('orchestrat')>=0) return 'orchestrator';
  if(n.indexOf('publish')>=0) return 'publisher';
  if(n.indexOf('outbound')>=0) return 'outbound';
  if(n.indexOf('inbound')>=0) return 'inbound';
  if(n.indexOf('analyst')>=0||n.indexOf('analyt')>=0) return 'analyst';
  if(n.indexOf('creator')>=0||n.indexOf('creat')>=0) return 'creator';
  if(n.indexOf('scout')>=0) return 'scout';
  return n;
}

function agentColorClass(agent){
  var n=normalizeAgent(agent);
  if(AGENTS[n]) return 'ac-'+n;
  return 'ac-dashboard';
}

/* =====================================================================
   CLOCK
   ===================================================================== */
function updateClock(){
  var now=new Date();
  var h=String(now.getUTCHours()).padStart(2,'0');
  var m=String(now.getUTCMinutes()).padStart(2,'0');
  var s=String(now.getUTCSeconds()).padStart(2,'0');
  document.getElementById('clock').textContent=h+':'+m+':'+s+' UTC';
}
setInterval(updateClock,1000);
updateClock();

/* =====================================================================
   POSITION AGENTS ON FLOOR
   ===================================================================== */
function positionAgents(){
  var floor=document.getElementById('floor');
  var w=floor.clientWidth;
  var h=floor.clientHeight;
  for(var key in AGENTS){
    var el=document.getElementById('agent-'+key);
    if(!el) continue;
    el.style.left=(AGENTS[key].x*w)+'px';
    el.style.top=(AGENTS[key].y*h)+'px';
  }
  drawConnections();
}

/* =====================================================================
   CONNECTION LINES
   ===================================================================== */
function drawConnections(){
  var floor=document.getElementById('floor');
  var w=floor.clientWidth;
  var h=floor.clientHeight;
  var svg=document.getElementById('connections-svg');
  var html='';
  for(var i=0;i<CONNECTIONS.length;i++){
    var a=CONNECTIONS[i][0], b=CONNECTIONS[i][1];
    var ax=AGENTS[a].x*w, ay=AGENTS[a].y*h;
    var bx=AGENTS[b].x*w, by=AGENTS[b].y*h;
    var aEl=document.getElementById('agent-'+a);
    var bEl=document.getElementById('agent-'+b);
    var aActive=aEl&&(aEl.classList.contains('active')||aEl.classList.contains('recent'));
    var bActive=bEl&&(bEl.classList.contains('active')||bEl.classList.contains('recent'));
    var cls='conn-line'+(aActive&&bActive?' active':'');
    html+='<line x1="'+ax+'" y1="'+ay+'" x2="'+bx+'" y2="'+by+'" class="'+cls+'"/>';
  }
  svg.innerHTML=html;
}

/* =====================================================================
   PARTICLES
   ===================================================================== */
function spawnParticles(){
  var floor=document.getElementById('floor');
  var w=floor.clientWidth;
  for(var i=0;i<12;i++){
    var p=document.createElement('div');
    p.className='particle';
    p.style.left=Math.random()*w+'px';
    p.style.top=(Math.random()*100+60)+'%';
    var dur=8+Math.random()*12;
    p.style.animationDuration=dur+'s';
    p.style.animationDelay=Math.random()*dur+'s';
    p.style.width=(1+Math.random()*2)+'px';
    p.style.height=p.style.width;
    p.style.opacity=.1+Math.random()*.2;
    floor.appendChild(p);
  }
}

/* =====================================================================
   UPDATE AGENTS
   ===================================================================== */
function updateAgents(agentsData){
  /* build a lookup: normalized name -> {last_active, event_type} */
  var lookup={};
  if(agentsData){
    for(var i=0;i<agentsData.length;i++){
      var n=normalizeAgent(agentsData[i].agent);
      if(AGENTS[n]){
        lookup[n]=agentsData[i];
      }
    }
  }

  var now=new Date();
  for(var key in AGENTS){
    var el=document.getElementById('agent-'+key);
    var statusEl=document.getElementById('status-'+key);
    if(!el||!statusEl) continue;

    var info=lookup[key];
    var newState='idle';
    var statusText='Idle';

    if(info && info.last_active){
      var last=new Date(info.last_active);
      var diffMin=(now-last)/(1000*60);
      if(diffMin<5){
        newState='active';
        statusText=(info.event_type||'Active')+' \u00B7 '+timeAgo(info.last_active);
      } else if(diffMin<30){
        newState='recent';
        statusText=(info.event_type||'Recent')+' \u00B7 '+timeAgo(info.last_active);
      } else {
        statusText='Idle \u00B7 '+timeAgo(info.last_active);
      }
    }

    /* detect transitions -> flash */
    var prev=prevAgentStates[key]||'idle';
    if(newState==='active' && prev!=='active'){
      el.classList.add('flash');
      setTimeout((function(e){return function(){e.classList.remove('flash')}})(el),1000);
    }
    prevAgentStates[key]=newState;

    el.className='agent-station '+newState;
    statusEl.textContent=statusText;
  }
  drawConnections();
}

/* =====================================================================
   UPDATE SIGNAL FLARES
   ===================================================================== */
function updateFlares(signals){
  var container=document.getElementById('flares-container');
  container.innerHTML='';
  if(!signals||signals.length===0) return;

  var floor=document.getElementById('floor');
  var w=floor.clientWidth;
  var h=floor.clientHeight;

  /* group signals by type */
  var groups={};
  for(var i=0;i<signals.length;i++){
    var s=signals[i];
    var t=s.type||'SIGNAL';
    if(!groups[t]) groups[t]={count:0,type:t};
    groups[t].count++;
  }

  for(var type in groups){
    var agentKey=SIGNAL_AGENT_MAP[type];
    if(!agentKey) agentKey='orchestrator';
    var ax=AGENTS[agentKey].x;
    var ay=AGENTS[agentKey].y;

    var flare=document.createElement('div');
    var isHot=type.indexOf('HOT')>=0||type.indexOf('SPIKE')>=0;
    var isInfo=type.indexOf('TREND')>=0||type.indexOf('BREAKOUT')>=0;
    flare.className='signal-flare'+(isHot?' hot':'')+(isInfo?' info':'');
    flare.style.left=(ax*w+40)+'px';
    flare.style.top=(ay*h-30)+'px';
    flare.textContent=type.replace(/_/g,' ')+(groups[type].count>1?' \u00D7'+groups[type].count:'');
    container.appendChild(flare);
  }
}

/* =====================================================================
   UPDATE TICKER
   ===================================================================== */
function updateTicker(events){
  if(!events||events.length===0) return;

  var items=[];
  for(var i=0;i<events.length;i++){
    var e=events[i];
    var ac=agentColorClass(e.agent);
    var details=e.details||'';
    if(details.length>60) details=details.substring(0,60)+'\u2026';
    items.push(
      '<span class="ticker-item">'+
        '<span class="ticker-agent '+ac+'">'+esc(e.agent||'system').toUpperCase()+'</span>'+
        '<span class="ticker-sep">\u2502</span>'+
        '<span>'+esc(e.event_type||'')+'</span>'+
        (details?' <span class="ticker-sep">\u2014</span> <span>'+esc(details)+'</span>':'')+
        '<span class="ticker-time">\u00B7 '+timeAgo(e.timestamp)+'</span>'+
      '</span>'
    );
  }

  /* duplicate for seamless loop */
  var html=items.join('')+items.join('');

  var container=document.getElementById('ticker-content');
  /* adjust speed based on content */
  var dur=Math.max(30, events.length*4);
  container.style.setProperty('--ticker-duration',dur+'s');
  container.innerHTML=html;
}

/* =====================================================================
   UPDATE SIDEBAR
   ===================================================================== */
function usageBarColor(pct){
  if(pct>=80) return '#f85149';
  if(pct>=50) return '#d29922';
  return '#3fb950';
}

function updateUsageMeter(barId, labelId, current, budget, label){
  var bar=document.getElementById(barId);
  var lbl=document.getElementById(labelId);
  if(!bar||!lbl) return;
  var pct=budget>0?Math.min((current/budget)*100,100):0;
  bar.style.width=pct+'%';
  bar.style.background=usageBarColor(pct);
  lbl.textContent=current.toLocaleString()+' / '+budget.toLocaleString();
}

function updateSidebar(data){
  if(data.stats){
    document.getElementById('stat-posts').textContent=data.stats.posts_today;
    document.getElementById('stat-actions').textContent=data.stats.actions_this_hour;
    document.getElementById('stat-signals').textContent=data.stats.pending_signals;
    document.getElementById('stat-backlog').textContent=data.stats.pending_approvals;
  }

  /* api usage */
  if(data.usage){
    var u=data.usage;
    var b=u.budgets||{};
    updateUsageMeter('usage-x-reads-bar','usage-x-reads-label',u.x_reads||0,b.x_reads_per_month||10000);
    updateUsageMeter('usage-x-writes-bar','usage-x-writes-label',u.x_writes||0,b.x_writes_per_month||1500);
    updateUsageMeter('usage-linkedin-bar','usage-linkedin-label',u.linkedin_writes||0,b.linkedin_writes_per_month||60);
  }

  /* schedule */
  var list=document.getElementById('schedule-list');
  if(!data.schedule||data.schedule.length===0){
    list.innerHTML='<div style="color:#484f58;font-size:11px;font-style:italic">No scheduled tasks</div>';
    return;
  }
  var html='';
  var shown=Math.min(data.schedule.length,5);
  for(var i=0;i<shown;i++){
    var s=data.schedule[i];
    var due=s.next_due?timeAgo(s.next_due):'--';
    /* is it overdue? */
    var overdue=s.next_due&&new Date(s.next_due)<new Date();
    html+='<div class="schedule-item">'+
      '<div class="schedule-task">'+esc(s.task||s.agent||'Task')+'</div>'+
      '<div class="schedule-meta">'+esc(s.agent||'')+' &middot; '+
        '<span class="schedule-countdown'+(overdue?' style="color:#f85149"':'')+'">'+
          (overdue?'OVERDUE':due)+
        '</span>'+
      '</div>'+
    '</div>';
  }
  list.innerHTML=html;
}

/* =====================================================================
   UPDATE TOP BAR
   ===================================================================== */
function updateTopbar(data){
  var color=(data.brand_safety&&data.brand_safety.color)||'GREEN';
  var dot=document.getElementById('safety-dot');
  dot.className='safety-dot safety-'+color;
  var label=document.getElementById('safety-label');
  label.textContent=color;
  var colors={'GREEN':'#3fb950','YELLOW':'#d29922','RED':'#f85149','BLACK':'#484f58'};
  label.style.color=colors[color]||'#c9d1d9';

  var phase=data.trust_phase||'A';
  document.getElementById('trust-badge').textContent='PHASE '+phase;
}

/* =====================================================================
   NEWS FEED
   ===================================================================== */
var knownFeedIds = {};
var activeActionPanel = null;

function feedSourceClass(source){
  var s = (source||'').toLowerCase();
  if(s.indexOf('scout')>=0) return 'src-scout';
  if(s.indexOf('outbound')>=0) return 'src-outbound';
  if(s.indexOf('inbound')>=0) return 'src-inbound';
  if(s.indexOf('publisher')>=0) return 'src-publisher';
  if(s.indexOf('creator')>=0) return 'src-creator';
  if(s.indexOf('analyst')>=0) return 'src-analyst';
  if(s.indexOf('orchestrat')>=0) return 'src-orchestrator';
  return 'src-system';
}

function feedSourceLabel(source){
  var s = (source||'').toLowerCase();
  if(s.indexOf('scout')>=0) return 'SCT';
  if(s.indexOf('outbound')>=0) return 'OUT';
  if(s.indexOf('inbound')>=0) return 'INB';
  if(s.indexOf('publisher')>=0) return 'PUB';
  if(s.indexOf('creator')>=0) return 'CRE';
  if(s.indexOf('analyst')>=0) return 'ANL';
  if(s.indexOf('orchestrat')>=0) return 'ORC';
  return 'SYS';
}

function toggleActions(itemId){
  var panel = document.getElementById('actions-'+itemId);
  if(!panel) return;
  if(activeActionPanel && activeActionPanel !== panel){
    activeActionPanel.classList.remove('active');
  }
  panel.classList.toggle('active');
  activeActionPanel = panel.classList.contains('active') ? panel : null;
}

function sendCommand(action, itemId, rawData, btn){
  btn.textContent = 'SENDING...';
  btn.classList.add('queued');
  fetch('/api/command', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({item_id: itemId, action: action, context: rawData || {}})
  })
  .then(function(r){ return r.json(); })
  .then(function(data){
    btn.textContent = 'QUEUED';
    setTimeout(function(){
      btn.textContent = action.toUpperCase();
      btn.classList.remove('queued');
      var panel = btn.parentElement;
      if(panel) panel.classList.remove('active');
      activeActionPanel = null;
    }, 1500);
  })
  .catch(function(e){
    btn.textContent = 'ERROR';
    btn.classList.remove('queued');
    setTimeout(function(){ btn.textContent = action.toUpperCase(); }, 2000);
  });
}

function dismissFeedItem(itemId, btn){
  var item = document.getElementById('feed-'+itemId);
  if(item){
    item.style.opacity = '0.3';
    item.style.pointerEvents = 'none';
  }
  var panel = btn.parentElement;
  if(panel) panel.classList.remove('active');
  activeActionPanel = null;
}

function updateFeed(feedData){
  if(!feedData || feedData.length === 0) return;

  var list = document.getElementById('feed-list');
  var countEl = document.getElementById('feed-count');
  countEl.textContent = feedData.length + ' items';

  var html = '';
  for(var i=0; i<feedData.length; i++){
    var item = feedData[i];
    var id = item.id;
    var isNew = !knownFeedIds[id];
    knownFeedIds[id] = true;

    var catClass = 'category-' + (item.category || 'intel');
    var newClass = isNew ? ' new' : '';
    var srcClass = feedSourceClass(item.source);
    var srcLabel = feedSourceLabel(item.source);
    var rawJson = esc(JSON.stringify(item.raw || {}));

    html += '<div class="feed-item ' + catClass + newClass + '" id="feed-' + esc(String(id)) + '" onclick="toggleActions(\'' + esc(String(id)) + '\')">';
    html += '<button class="feed-act-btn" onclick="event.stopPropagation();toggleActions(\'' + esc(String(id)) + '\')">ACT</button>';
    html += '<div class="feed-item-header">';
    html += '<span class="feed-time">' + timeAgo(item.timestamp) + '</span>';
    html += '<span class="feed-source ' + srcClass + '">' + srcLabel + '</span>';
    html += '</div>';
    html += '<div class="feed-headline">' + esc(item.headline) + '</div>';
    if(item.detail){
      html += '<div class="feed-detail">' + esc(item.detail) + '</div>';
    }
    html += '</div>';

    /* Action panel */
    html += '<div class="feed-actions" id="actions-' + esc(String(id)) + '">';
    html += '<button class="feed-action-btn" onclick="event.stopPropagation();sendCommand(\'reply\',\'' + esc(String(id)) + '\',' + rawJson + ',this)">REPLY</button>';
    html += '<button class="feed-action-btn" onclick="event.stopPropagation();sendCommand(\'qt\',\'' + esc(String(id)) + '\',' + rawJson + ',this)">QT</button>';
    html += '<button class="feed-action-btn" onclick="event.stopPropagation();sendCommand(\'create\',\'' + esc(String(id)) + '\',' + rawJson + ',this)">CREATE</button>';
    html += '<button class="feed-action-btn" onclick="event.stopPropagation();sendCommand(\'boost\',\'' + esc(String(id)) + '\',' + rawJson + ',this)">BOOST</button>';
    html += '<button class="feed-action-btn" onclick="event.stopPropagation();dismissFeedItem(\'' + esc(String(id)) + '\',this)">DISMISS</button>';
    html += '</div>';
  }

  list.innerHTML = html;
}

/* =====================================================================
   MAIN UPDATE
   ===================================================================== */
function updateAll(data){
  updateTopbar(data);
  updateAgents(data.agents);
  updateFlares(data.signals);
  updateTicker(data.events);
  updateSidebar(data);
  updateFeed(data.feed);
}

function fetchState(){
  fetch('/api/state')
    .then(function(r){return r.json()})
    .then(updateAll)
    .catch(function(e){
      console.error('Fetch error:',e);
    });
}

/* =====================================================================
   INIT
   ===================================================================== */
function init(){
  positionAgents();
  spawnParticles();
  fetchState();
  setInterval(fetchState,5000);
}

window.addEventListener('resize',function(){
  positionAgents();
  /* reposition flares on resize */
  fetchState();
});

/* wait for DOM */
if(document.readyState==='loading'){
  document.addEventListener('DOMContentLoaded',init);
} else {
  init();
}
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------

class NewsroomHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        sys.stderr.write(f"[newsroom] {args[0]}\n")

    def _send_json(self, data, status=200):
        body = json.dumps(data, indent=2, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html, status=200):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if path == "/":
            self._send_html(HTML_PAGE)

        elif path == "/api/state":
            conn = get_conn()
            try:
                self._send_json(get_full_state(conn))
            finally:
                conn.close()

        elif path == "/api/events":
            limit = int(qs.get("limit", [30])[0])
            conn = get_conn()
            try:
                data = get_recent_events(conn, limit=limit)
                self._send_json({"events": data, "count": len(data)})
            finally:
                conn.close()

        elif path == "/api/agents":
            conn = get_conn()
            try:
                data = get_agent_status(conn)
                self._send_json({"agents": data})
            finally:
                conn.close()

        elif path == "/api/feed":
            limit = int(qs.get("limit", [50])[0])
            conn = get_conn()
            try:
                data = get_feed_items(conn, limit=limit)
                self._send_json({"feed": data, "count": len(data)})
            finally:
                conn.close()

        elif path == "/api/usage":
            conn = get_conn()
            try:
                self._send_json(get_api_usage(conn))
            finally:
                conn.close()

        else:
            self._send_json({"error": "Not found"}, status=404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else b""

        if path == "/api/command":
            try:
                payload = json.loads(body) if body else {}
            except json.JSONDecodeError:
                self._send_json({"error": "Invalid JSON"}, status=400)
                return

            item_id = payload.get("item_id")
            action = payload.get("action", "")
            context = payload.get("context", {})

            if action == "dismiss":
                self._send_json({"status": "dismissed", "item_id": item_id})
                return

            if action not in ("reply", "qt", "create", "boost"):
                self._send_json({"error": f"Unknown action: {action}"}, status=400)
                return

            conn = get_conn()
            try:
                result = create_command_signal(conn, item_id, action, context)
                if result:
                    self._send_json({"status": "queued", **result})
                else:
                    self._send_json({"error": "Failed to create signal"}, status=500)
            finally:
                conn.close()
        else:
            self._send_json({"error": "Not found"}, status=404)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Groundswell Newsroom — cinematic ops-center dashboard")
    parser.add_argument("--port", type=int, default=8501, help="Port (default: 8501)")
    args = parser.parse_args()

    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}", file=sys.stderr)
        print("Run 'python3 tools/db.py init' first.", file=sys.stderr)
        sys.exit(1)

    server = HTTPServer(("0.0.0.0", args.port), NewsroomHandler)
    print(f"Groundswell Newsroom running on http://0.0.0.0:{args.port}")
    print(f"Database: {DB_PATH}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
