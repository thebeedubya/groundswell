#!/usr/bin/env python3
"""
Groundswell Dashboard v2 — operational command center.

Modern light-theme dashboard with Tailwind CSS, Alpine.js, and bento grid layout.
Three-layer information hierarchy: Glance → Scan → Drill.

Usage:
    python3 tools/dashboard.py serve [--port 8500]
    python3 tools/dashboard.py status
"""

import argparse
import json
import os
import sqlite3
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler

from _common import (
    DB_PATH,
    CONFIG_PATH,
    DATA_DIR,
    now_iso,
    get_db,
    rows_to_list,
    load_config,
)


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Data Layer — all dashboard query functions
# ---------------------------------------------------------------------------

def get_agent_grid(conn):
    """For each ENABLED scheduled task: agent, task, last_run, last_result,
    next_due, overdue flag, today's event count for that agent."""
    now = now_iso()
    today_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%dT")

    rows = conn.execute(
        "SELECT * FROM schedule WHERE enabled = 1 ORDER BY next_due ASC"
    ).fetchall()

    agents = []
    for r in rows:
        agent_name = r["agent"]
        event_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM events WHERE agent = ? AND timestamp >= ?",
            (agent_name, today_prefix),
        ).fetchone()["cnt"]

        agents.append({
            "agent": agent_name,
            "task": r["task"],
            "last_run": r["last_run"],
            "last_result": r["last_result"],
            "next_due": r["next_due"],
            "overdue": bool(r["next_due"] and r["next_due"] < now),
            "today_count": event_count,
        })

    return agents


def get_attention_items(conn):
    """Items needing human attention: recent errors, overdue tasks,
    brand safety != GREEN."""
    now = now_iso()
    one_day_ago = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat().replace("+00:00", "Z")
    items = []

    # Errors in last 24h (exclude rate limits — the system handling its own limits is not an error)
    error_rows = conn.execute(
        "SELECT * FROM events WHERE timestamp >= ? "
        "AND (event_type LIKE '%error%' OR event_type LIKE '%block%' OR event_type LIKE '%fail%') "
        "AND event_type NOT LIKE '%rate_limit%' "
        "AND details NOT LIKE '%rate_limit%' "
        "ORDER BY id DESC",
        (one_day_ago,),
    ).fetchall()
    for r in error_rows:
        # Parse details JSON for a human-readable summary
        detail_summary = ""
        if r["details"]:
            try:
                d = json.loads(r["details"])
                # Prefer note/reason/error fields, fall back to item_id + platform
                if d.get("note"):
                    detail_summary = d["note"]
                elif d.get("reason"):
                    detail_summary = d["reason"]
                elif d.get("error"):
                    detail_summary = d["error"]
                else:
                    parts = []
                    if d.get("platform"):
                        parts.append(d["platform"])
                    if d.get("item_id"):
                        parts.append(d["item_id"])
                    detail_summary = " | ".join(parts) if parts else ""
            except (json.JSONDecodeError, TypeError):
                detail_summary = str(r["details"])[:120]

        items.append({
            "type": "error",
            "message": f"[{r['agent']}] {r['event_type']}: {detail_summary}",
            "severity": "high",
            "timestamp": r["timestamp"],
        })

    # Overdue tasks
    overdue_rows = conn.execute(
        "SELECT * FROM schedule WHERE enabled = 1 AND next_due IS NOT NULL AND next_due < ?",
        (now,),
    ).fetchall()
    for r in overdue_rows:
        items.append({
            "type": "overdue",
            "message": f"Task '{r['task']}' ({r['agent']}) overdue since {r['next_due']}",
            "severity": "medium",
            "timestamp": r["next_due"],
        })

    # Brand safety
    row = conn.execute(
        "SELECT value, updated_at FROM strategy_state WHERE key = 'brand_safety_color'"
    ).fetchone()
    if row:
        try:
            color = json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            color = row["value"]
        if color != "GREEN":
            items.append({
                "type": "brand_safety",
                "message": f"Brand safety is {color}",
                "severity": "high" if color in ("RED", "BLACK") else "medium",
                "timestamp": row["updated_at"],
            })

    return items


def get_intel_feed(conn, limit=20):
    """Recent intel_feed items plus unacted count."""
    rows = conn.execute(
        "SELECT id, category, headline, detail, relevance_score, acted_on, "
        "source_agent, source_url, created_at "
        "FROM intel_feed ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()

    unacted_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM intel_feed WHERE acted_on = 0"
    ).fetchone()["cnt"]

    return {
        "items": rows_to_list(rows),
        "unacted_count": unacted_count,
    }


def get_backlog_status():
    """Read data/backlog.json. Count items by platform, by status, total ready."""
    backlog_path = os.path.join(DATA_DIR, "backlog.json")
    try:
        with open(backlog_path, "r") as f:
            items = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"by_platform": {}, "by_status": {}, "total_ready": 0, "total": 0}

    by_platform = {}
    by_status = {}
    total_ready = 0

    for item in items:
        plat = item.get("platform", "unknown")
        status = item.get("status", "unknown")
        by_platform[plat] = by_platform.get(plat, 0) + 1
        by_status[status] = by_status.get(status, 0) + 1
        if status == "ready":
            total_ready += 1

    return {
        "by_platform": by_platform,
        "by_status": by_status,
        "total_ready": total_ready,
        "total": len(items),
    }


def get_api_budget(conn):
    """Today's API calls by call_type, this week total, plus config limits."""
    today_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%dT")
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat().replace("+00:00", "Z")

    today_rows = conn.execute(
        "SELECT call_type, COUNT(*) as cnt FROM api_usage "
        "WHERE created_at >= ? GROUP BY call_type",
        (today_prefix,),
    ).fetchall()

    today_reads = 0
    today_writes = 0
    for r in today_rows:
        ct = r["call_type"].lower()
        if ct in ("read", "search", "mentions_check", "metrics_check", "get"):
            today_reads += r["cnt"]
        else:
            today_writes += r["cnt"]

    week_total = conn.execute(
        "SELECT COUNT(*) as cnt FROM api_usage WHERE created_at >= ?",
        (week_ago,),
    ).fetchone()["cnt"]

    limits = {"reads_per_day": 300, "posts_per_day": 50}
    try:
        cfg = load_config()
        api_budget = cfg.get("platforms", {}).get("x", {}).get("api_budget", {})
        if api_budget:
            limits["reads_per_day"] = api_budget.get("reads_per_day", 300)
            limits["posts_per_day"] = api_budget.get("posts_per_day", 50)
    except (SystemExit, Exception):
        pass

    return {
        "today": {"reads": today_reads, "writes": today_writes},
        "week_total": week_total,
        "limits": limits,
    }


def get_rss_health(conn):
    """RSS items: total, unscored, scored, by category, latest fetch time."""
    total = conn.execute("SELECT COUNT(*) as cnt FROM rss_items").fetchone()["cnt"]
    unscored = conn.execute(
        "SELECT COUNT(*) as cnt FROM rss_items WHERE scored = 0"
    ).fetchone()["cnt"]
    scored = conn.execute(
        "SELECT COUNT(*) as cnt FROM rss_items WHERE scored = 1"
    ).fetchone()["cnt"]

    cat_rows = conn.execute(
        "SELECT feed_category, COUNT(*) as cnt, "
        "SUM(CASE WHEN scored = 1 THEN 1 ELSE 0 END) as scored_cnt "
        "FROM rss_items GROUP BY feed_category"
    ).fetchall()
    by_category = {
        r["feed_category"]: {"total": r["cnt"], "scored": r["scored_cnt"]}
        for r in cat_rows
    }

    latest_row = conn.execute(
        "SELECT MAX(fetched_at) as latest FROM rss_items"
    ).fetchone()
    latest_fetch = latest_row["latest"] if latest_row else None

    return {
        "total": total,
        "unscored": unscored,
        "scored": scored,
        "by_category": by_category,
        "latest_fetch": latest_fetch,
    }


def get_activity_feed(conn, limit=30):
    """Recent events ordered by id DESC. Parse details JSON where possible."""
    rows = conn.execute(
        "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        if d.get("details"):
            try:
                d["details"] = json.loads(d["details"])
            except (json.JSONDecodeError, TypeError):
                pass
        result.append(d)

    return result


def get_schedule_status(conn):
    """All schedule rows with computed overdue flag."""
    now = now_iso()
    rows = conn.execute(
        "SELECT * FROM schedule ORDER BY next_due ASC"
    ).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        d["overdue"] = bool(d.get("next_due") and d["next_due"] < now and d.get("enabled"))
        result.append(d)

    return result


def get_posting_history(conn, days=7):
    """Post counts per day for the last N days, for sparkline rendering."""
    result = []
    now_dt = datetime.now(timezone.utc)

    for i in range(days - 1, -1, -1):
        day = now_dt - timedelta(days=i)
        date_str = day.strftime("%Y-%m-%d")
        prefix = day.strftime("%Y-%m-%dT")
        next_prefix = (day + timedelta(days=1)).strftime("%Y-%m-%dT")

        count = conn.execute(
            "SELECT COUNT(*) as cnt FROM events "
            "WHERE event_type LIKE '%post%' AND timestamp >= ? AND timestamp < ?",
            (prefix, next_prefix),
        ).fetchone()["cnt"]

        result.append({"date": date_str, "count": count})

    return result


def get_telegram_stats(conn):
    """Stats from telegram_approvals table."""
    try:
        total = conn.execute(
            "SELECT COUNT(*) as cnt FROM telegram_approvals"
        ).fetchone()["cnt"]
        approved = conn.execute(
            "SELECT COUNT(*) as cnt FROM telegram_approvals WHERE decision = 'approve'"
        ).fetchone()["cnt"]
        rejected = conn.execute(
            "SELECT COUNT(*) as cnt FROM telegram_approvals WHERE decision = 'reject'"
        ).fetchone()["cnt"]
        no_decision = conn.execute(
            "SELECT COUNT(*) as cnt FROM telegram_approvals WHERE decision IS NULL"
        ).fetchone()["cnt"]
    except sqlite3.OperationalError:
        return {"total": 0, "approved": 0, "rejected": 0, "no_decision": 0}

    return {
        "total": total,
        "approved": approved,
        "rejected": rejected,
        "no_decision": no_decision,
    }


def get_brand_safety(conn):
    """Brand safety color and update time."""
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
    """Current trust phase from strategy_state."""
    row = conn.execute(
        "SELECT value FROM strategy_state WHERE key = 'trust_phase'"
    ).fetchone()
    if row:
        try:
            return json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            return row["value"]
    return "A"


def get_quick_stats(conn):
    """Quick stats: posts today, actions this hour, pending signals/approvals."""
    today_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%dT")
    one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")

    posts_today = conn.execute(
        "SELECT COUNT(*) as cnt FROM events WHERE event_type LIKE '%post%' AND timestamp >= ?",
        (today_prefix,),
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


def get_full_dashboard_state(conn):
    """Combined dict with all dashboard data."""
    return {
        "brand_safety": get_brand_safety(conn),
        "trust_phase": get_trust_phase(conn),
        "agents": get_agent_grid(conn),
        "attention": get_attention_items(conn),
        "intel": get_intel_feed(conn),
        "backlog": get_backlog_status(),
        "api_budget": get_api_budget(conn),
        "rss_health": get_rss_health(conn),
        "activity": get_activity_feed(conn),
        "schedule": get_schedule_status(conn),
        "posting_history": get_posting_history(conn),
        "telegram_stats": get_telegram_stats(conn),
        "stats": get_quick_stats(conn),
        "timestamp": now_iso(),
    }


# ---------------------------------------------------------------------------
# HTML Template
# ---------------------------------------------------------------------------

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Groundswell Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.tailwindcss.com"></script>
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js"></script>
<script>
tailwind.config = {
  theme: {
    extend: {
      fontFamily: { sans: ['Inter', 'system-ui', 'sans-serif'] },
    }
  }
}
</script>
<style>
  [x-cloak] { display: none !important; }
  .custom-scroll::-webkit-scrollbar { width: 4px; }
  .custom-scroll::-webkit-scrollbar-track { background: transparent; }
  .custom-scroll::-webkit-scrollbar-thumb { background: #d1d5db; border-radius: 2px; }
  .custom-scroll::-webkit-scrollbar-thumb:hover { background: #9ca3af; }
</style>
</head>
<body class="bg-gray-50 font-sans text-gray-900 antialiased" x-data="dashboard()" x-init="init()">

<!-- TOP BAR -->
<header class="sticky top-0 z-50 bg-white/80 backdrop-blur-md border-b border-gray-200">
  <div class="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
    <div class="flex items-center gap-3">
      <h1 class="text-base font-bold tracking-widest text-gray-900">GROUNDSWELL</h1>
      <span class="hidden sm:inline text-xs text-gray-400 font-medium">Operations</span>
    </div>
    <div class="flex items-center gap-4">
      <template x-if="systemStatus === 'critical'">
        <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-red-50 text-red-700 ring-1 ring-red-200">
          <span class="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse"></span> Critical
        </span>
      </template>
      <template x-if="systemStatus === 'warning'">
        <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 ring-1 ring-amber-200">
          <span class="w-1.5 h-1.5 rounded-full bg-amber-500"></span> Needs Attention
        </span>
      </template>
      <template x-if="systemStatus === 'ok'">
        <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200">
          <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span> All Clear
        </span>
      </template>
      <span class="text-xs text-gray-400" x-text="lastUpdated"></span>
      <div class="flex items-center gap-1.5">
        <button @click="killSwitch()"
          class="px-3 py-1.5 text-xs font-medium rounded-lg border border-red-200 text-red-600 hover:bg-red-50 transition-colors">
          Kill
        </button>
        <button @click="resumeSystem()"
          class="px-3 py-1.5 text-xs font-medium rounded-lg border border-emerald-200 text-emerald-600 hover:bg-emerald-50 transition-colors">
          Resume
        </button>
      </div>
    </div>
  </div>
</header>

<main class="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">

<!-- LAYER 1: THE GLANCE -->

<!-- Agent Health Grid -->
<section>
  <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-3">
    <template x-for="agent in agents" :key="agent.task">
      <div class="bg-white border border-gray-200 rounded-xl p-3.5 shadow-sm hover:shadow transition-shadow">
        <div class="flex items-center justify-between mb-1.5">
          <span class="text-sm font-semibold text-gray-900 truncate" x-text="formatAgentName(agent.task)"></span>
          <span class="w-2 h-2 rounded-full flex-shrink-0"
            :class="agentDotColor(agent)"></span>
        </div>
        <div class="flex items-center justify-between">
          <span class="text-xs text-gray-400" x-text="relTime(agent.last_run)"></span>
          <span class="text-xs font-medium text-gray-500" x-text="agent.today_count + ' today'"></span>
        </div>
      </div>
    </template>
  </div>
</section>

<!-- Attention Banner -->
<template x-if="attention.length > 0">
  <div x-data="{ expanded: false }"
    class="rounded-xl border px-4 py-3 shadow-sm"
    :class="hasError ? 'bg-red-50 border-red-200' : 'bg-amber-50 border-amber-200'">
    <button @click="expanded = !expanded" class="w-full flex items-center justify-between">
      <div class="flex items-center gap-2">
        <svg class="w-4 h-4" :class="hasError ? 'text-red-500' : 'text-amber-500'" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
        </svg>
        <span class="text-sm font-semibold" :class="hasError ? 'text-red-800' : 'text-amber-800'"
          x-text="attention.length + ' item' + (attention.length !== 1 ? 's' : '') + ' need' + (attention.length === 1 ? 's' : '') + ' attention'"></span>
      </div>
      <svg class="w-4 h-4 text-gray-400 transition-transform" :class="expanded && 'rotate-180'" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
      </svg>
    </button>
    <div x-show="expanded" x-cloak x-transition class="mt-3 space-y-1.5">
      <template x-for="item in attention" :key="item.timestamp + item.message">
        <div class="flex items-start gap-2 text-sm">
          <span class="mt-0.5 w-1.5 h-1.5 rounded-full flex-shrink-0"
            :class="item.severity === 'high' ? 'bg-red-500' : 'bg-amber-500'"></span>
          <span :class="hasError ? 'text-red-700' : 'text-amber-700'" x-text="item.message"></span>
          <span class="ml-auto text-xs text-gray-400 flex-shrink-0" x-text="relTime(item.timestamp)"></span>
        </div>
      </template>
    </div>
  </div>
</template>

<!-- LAYER 2: THE SCAN -->

<!-- Stats Row -->
<section class="grid grid-cols-2 lg:grid-cols-4 gap-3">
  <div class="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
    <div class="flex items-center justify-between mb-1">
      <span class="text-xs font-medium text-gray-500 uppercase tracking-wide">Posts Today</span>
      <div id="spark-posts" class="h-6 w-16"></div>
    </div>
    <span class="text-2xl font-bold text-gray-900" x-text="stats.posts_today ?? '-'"></span>
  </div>
  <div class="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
    <div class="flex items-center justify-between mb-1">
      <span class="text-xs font-medium text-gray-500 uppercase tracking-wide">Actions / Hour</span>
    </div>
    <span class="text-2xl font-bold text-gray-900" x-text="stats.actions_this_hour ?? '-'"></span>
  </div>
  <div class="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
    <div class="flex items-center justify-between mb-1">
      <span class="text-xs font-medium text-gray-500 uppercase tracking-wide">Pending Signals</span>
    </div>
    <span class="text-2xl font-bold text-gray-900" x-text="stats.pending_signals ?? '-'"></span>
  </div>
  <div class="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
    <div class="flex items-center justify-between mb-1">
      <span class="text-xs font-medium text-gray-500 uppercase tracking-wide">API Calls Today</span>
    </div>
    <span class="text-2xl font-bold text-gray-900" x-text="(apibudget.today?.reads ?? 0) + (apibudget.today?.writes ?? 0)"></span>
  </div>
</section>

<!-- Intel Feed + Content Pipeline -->
<section class="grid grid-cols-1 lg:grid-cols-3 gap-3">
  <!-- Intel Feed -->
  <div class="lg:col-span-2 bg-white border border-gray-200 rounded-xl shadow-sm flex flex-col" style="max-height: 420px;">
    <div class="px-5 pt-4 pb-3 border-b border-gray-100 flex items-center justify-between">
      <h2 class="text-sm font-semibold text-gray-900 uppercase tracking-wide">Intel Feed</h2>
      <span class="text-xs text-gray-400" x-text="(intel.unacted_count ?? 0) + ' unacted'"></span>
    </div>
    <div class="overflow-y-auto custom-scroll flex-1 divide-y divide-gray-100">
      <template x-if="!intel.items || intel.items.length === 0">
        <div class="px-5 py-8 text-center text-sm text-gray-400 italic">No intel items</div>
      </template>
      <template x-for="item in (intel.items || [])" :key="item.id">
        <div class="px-5 py-3 flex items-start gap-3 hover:bg-gray-50/50 transition-colors"
          :class="!item.acted_on && 'border-l-2 border-l-indigo-400'">
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-1">
              <span class="inline-flex px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider"
                :class="categoryColor(item.category)"
                x-text="item.category || 'general'"></span>
              <span class="text-xs text-gray-400" x-text="relTime(item.created_at)"></span>
            </div>
            <p class="text-sm font-medium text-gray-800 leading-snug truncate" x-text="item.headline"></p>
            <div class="mt-1.5 flex items-center gap-3">
              <div class="flex-1 h-1 bg-gray-100 rounded-full overflow-hidden max-w-[120px]">
                <div class="h-full bg-indigo-500 rounded-full" :style="'width:' + ((item.relevance_score || 0) * 100) + '%'"></div>
              </div>
              <span class="text-[11px] text-gray-400" x-text="item.source_agent || ''"></span>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>

  <!-- Content Pipeline -->
  <div class="bg-white border border-gray-200 rounded-xl shadow-sm p-5">
    <h2 class="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-4">Content Pipeline</h2>
    <div class="text-center mb-5">
      <span class="text-4xl font-bold text-gray-900" x-text="backlog.total_ready ?? 0"></span>
      <p class="text-xs text-gray-400 mt-0.5">Ready to publish</p>
    </div>
    <div class="space-y-3">
      <template x-for="[platform, count] in Object.entries(backlog.by_platform || {})" :key="platform">
        <div>
          <div class="flex items-center justify-between mb-1">
            <span class="text-xs font-medium text-gray-600 uppercase" x-text="platform"></span>
            <span class="text-xs font-semibold text-gray-900" x-text="count"></span>
          </div>
          <div class="h-2 bg-gray-100 rounded-full overflow-hidden">
            <div class="h-full rounded-full bg-indigo-500 transition-all duration-500"
              :style="'width:' + Math.min(100, (count / Math.max(...Object.values(backlog.by_platform || {1:1}))) * 100) + '%'"></div>
          </div>
        </div>
      </template>
    </div>
    <div class="mt-5 pt-4 border-t border-gray-100 grid grid-cols-3 gap-2 text-center">
      <div>
        <span class="text-lg font-bold text-gray-900" x-text="backlog.by_status?.ready ?? 0"></span>
        <p class="text-[10px] text-gray-400 uppercase">Ready</p>
      </div>
      <div>
        <span class="text-lg font-bold text-gray-900" x-text="backlog.by_status?.posted ?? 0"></span>
        <p class="text-[10px] text-gray-400 uppercase">Posted</p>
      </div>
      <div>
        <span class="text-lg font-bold text-gray-900" x-text="backlog.by_status?.dead_letter ?? 0"></span>
        <p class="text-[10px] text-gray-400 uppercase">Dead</p>
      </div>
    </div>
  </div>
</section>

<!-- API Budget + RSS Health -->
<section class="grid grid-cols-1 lg:grid-cols-2 gap-3">
  <!-- API Budget -->
  <div class="bg-white border border-gray-200 rounded-xl shadow-sm p-5">
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-sm font-semibold text-gray-900 uppercase tracking-wide">API Budget</h2>
      <span class="text-xs text-gray-400" x-text="'Week: ' + (apibudget.week_total ?? 0) + ' calls'"></span>
    </div>
    <div class="space-y-4">
      <div>
        <div class="flex items-center justify-between mb-1.5">
          <span class="text-xs font-medium text-gray-600">Reads</span>
          <span class="text-xs text-gray-500">
            <span class="font-semibold text-gray-900" x-text="apibudget.today?.reads ?? 0"></span>
            / <span x-text="apibudget.limits?.reads_per_day ?? 300"></span>
          </span>
        </div>
        <div class="h-2.5 bg-gray-100 rounded-full overflow-hidden">
          <div class="h-full rounded-full transition-all duration-500"
            :class="budgetBarColor(apibudget.today?.reads, apibudget.limits?.reads_per_day)"
            :style="'width:' + Math.min(100, ((apibudget.today?.reads ?? 0) / (apibudget.limits?.reads_per_day || 300)) * 100) + '%'"></div>
        </div>
      </div>
      <div>
        <div class="flex items-center justify-between mb-1.5">
          <span class="text-xs font-medium text-gray-600">Writes</span>
          <span class="text-xs text-gray-500">
            <span class="font-semibold text-gray-900" x-text="apibudget.today?.writes ?? 0"></span>
            / <span x-text="apibudget.limits?.posts_per_day ?? 50"></span>
          </span>
        </div>
        <div class="h-2.5 bg-gray-100 rounded-full overflow-hidden">
          <div class="h-full rounded-full transition-all duration-500"
            :class="budgetBarColor(apibudget.today?.writes, apibudget.limits?.posts_per_day)"
            :style="'width:' + Math.min(100, ((apibudget.today?.writes ?? 0) / (apibudget.limits?.posts_per_day || 50)) * 100) + '%'"></div>
        </div>
      </div>
    </div>
  </div>

  <!-- RSS Health -->
  <div class="bg-white border border-gray-200 rounded-xl shadow-sm p-5">
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-sm font-semibold text-gray-900 uppercase tracking-wide">RSS Health</h2>
      <span class="text-xs text-gray-400" x-text="'Fetched ' + relTime(rss.latest_fetch)"></span>
    </div>
    <div class="flex items-center gap-6">
      <div class="relative w-24 h-24 flex-shrink-0">
        <svg class="w-24 h-24 -rotate-90" viewBox="0 0 36 36">
          <circle cx="18" cy="18" r="15.5" fill="none" stroke="#f3f4f6" stroke-width="3"></circle>
          <circle cx="18" cy="18" r="15.5" fill="none" stroke="#6366f1" stroke-width="3" stroke-linecap="round"
            :stroke-dasharray="scoredPct * 97.39 / 100 + ' ' + 97.39"
            class="transition-all duration-700"></circle>
        </svg>
        <div class="absolute inset-0 flex items-center justify-center">
          <span class="text-lg font-bold text-gray-900" x-text="scoredPct + '%'"></span>
        </div>
      </div>
      <div class="space-y-2 flex-1">
        <div class="flex justify-between">
          <span class="text-xs text-gray-500">Total Items</span>
          <span class="text-sm font-semibold text-gray-900" x-text="rss.total ?? 0"></span>
        </div>
        <div class="flex justify-between">
          <span class="text-xs text-gray-500">Scored</span>
          <span class="text-sm font-semibold text-emerald-600" x-text="rss.scored ?? 0"></span>
        </div>
        <div class="flex justify-between">
          <span class="text-xs text-gray-500">Unscored</span>
          <span class="text-sm font-semibold text-gray-400" x-text="rss.unscored ?? 0"></span>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- LAYER 3: THE DRILL -->

<!-- Activity Feed -->
<section x-data="{ agentFilter: 'all' }" class="bg-white border border-gray-200 rounded-xl shadow-sm">
  <div class="px-5 pt-4 pb-3 border-b border-gray-100 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
    <h2 class="text-sm font-semibold text-gray-900 uppercase tracking-wide">Activity Feed</h2>
    <div class="flex items-center gap-1 flex-wrap">
      <button @click="agentFilter = 'all'"
        class="px-2.5 py-1 rounded-md text-xs font-medium transition-colors"
        :class="agentFilter === 'all' ? 'bg-indigo-100 text-indigo-700' : 'text-gray-500 hover:bg-gray-100'">All</button>
      <template x-for="name in uniqueAgents" :key="name">
        <button @click="agentFilter = name"
          class="px-2.5 py-1 rounded-md text-xs font-medium transition-colors"
          :class="agentFilter === name ? 'bg-indigo-100 text-indigo-700' : 'text-gray-500 hover:bg-gray-100'"
          x-text="formatAgentName(name)"></button>
      </template>
    </div>
  </div>
  <div class="divide-y divide-gray-100 max-h-[400px] overflow-y-auto custom-scroll">
    <template x-if="!filteredActivity.length">
      <div class="px-5 py-8 text-center text-sm text-gray-400 italic">No activity</div>
    </template>
    <template x-for="ev in filteredActivity" :key="ev.id">
      <div x-data="{ open: false }" class="px-5 py-2.5 hover:bg-gray-50/50 transition-colors">
        <button @click="open = !open" class="w-full flex items-center gap-3 text-left">
          <span class="text-xs text-gray-400 w-16 flex-shrink-0 text-right tabular-nums" x-text="relTime(ev.timestamp)"></span>
          <span class="inline-flex px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider flex-shrink-0"
            :class="agentBadgeColor(ev.agent)"
            x-text="formatAgentName(ev.agent)"></span>
          <span class="text-xs font-medium text-gray-600 flex-shrink-0" x-text="ev.event_type"></span>
          <span class="text-xs text-gray-400 truncate flex-1" x-text="summarizeDetails(ev.details)"></span>
          <svg class="w-3.5 h-3.5 text-gray-300 transition-transform flex-shrink-0" :class="open && 'rotate-180'" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
          </svg>
        </button>
        <div x-show="open" x-cloak x-transition class="mt-2 ml-[76px] p-3 bg-gray-50 rounded-lg text-xs text-gray-600 font-mono whitespace-pre-wrap break-all"
          x-text="formatDetails(ev.details)"></div>
      </div>
    </template>
  </div>
</section>

<!-- Schedule -->
<section class="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
  <div class="px-5 pt-4 pb-3 border-b border-gray-100">
    <h2 class="text-sm font-semibold text-gray-900 uppercase tracking-wide">Schedule</h2>
  </div>
  <div class="overflow-x-auto">
    <table class="w-full text-sm">
      <thead>
        <tr class="border-b border-gray-100">
          <th class="px-5 py-2.5 text-left text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Task</th>
          <th class="px-3 py-2.5 text-left text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Agent</th>
          <th class="px-3 py-2.5 text-left text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Interval</th>
          <th class="px-3 py-2.5 text-left text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Next Due</th>
          <th class="px-3 py-2.5 text-left text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Last Run</th>
          <th class="px-3 py-2.5 text-left text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Result</th>
          <th class="px-3 py-2.5 text-center text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Enabled</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-gray-50">
        <template x-for="s in schedule" :key="s.task">
          <tr class="hover:bg-gray-50/50 transition-colors" :class="s.overdue && 'bg-red-50/40'">
            <td class="px-5 py-2.5 font-medium text-gray-900" x-text="s.task"></td>
            <td class="px-3 py-2.5">
              <span class="inline-flex px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider"
                :class="agentBadgeColor(s.agent)" x-text="formatAgentName(s.agent)"></span>
            </td>
            <td class="px-3 py-2.5 text-gray-500 text-xs" x-text="formatInterval(s)"></td>
            <td class="px-3 py-2.5 text-xs tabular-nums" :class="s.overdue ? 'text-red-600 font-medium' : 'text-gray-500'" x-text="relTime(s.next_due)"></td>
            <td class="px-3 py-2.5 text-gray-400 text-xs tabular-nums" x-text="relTime(s.last_run)"></td>
            <td class="px-3 py-2.5">
              <span class="inline-flex px-2 py-0.5 rounded-full text-[10px] font-semibold"
                :class="s.last_result === 'success' ? 'bg-emerald-50 text-emerald-700' : s.last_result === 'error' ? 'bg-red-50 text-red-700' : 'bg-gray-100 text-gray-500'"
                x-text="s.last_result || '-'"></span>
            </td>
            <td class="px-3 py-2.5 text-center">
              <span class="w-2 h-2 rounded-full inline-block" :class="s.enabled ? 'bg-emerald-500' : 'bg-gray-300'"></span>
            </td>
          </tr>
        </template>
      </tbody>
    </table>
  </div>
</section>

<!-- Telegram Stats -->
<section class="bg-white border border-gray-200 rounded-xl shadow-sm p-5 max-w-md">
  <h2 class="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-4">Telegram Approvals</h2>
  <div class="flex items-center gap-6">
    <div class="text-center">
      <span class="text-3xl font-bold text-gray-900" x-text="telegram.total ?? 0"></span>
      <p class="text-[10px] text-gray-400 uppercase mt-0.5">Total</p>
    </div>
    <div class="flex-1 space-y-2">
      <div class="flex items-center gap-2">
        <span class="text-[10px] text-gray-500 w-14 text-right">Approved</span>
        <div class="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
          <div class="h-full bg-emerald-500 rounded-full transition-all duration-500"
            :style="'width:' + (telegram.total ? (telegram.approved / telegram.total * 100) : 0) + '%'"></div>
        </div>
        <span class="text-xs font-semibold text-gray-700 w-8" x-text="telegram.approved ?? 0"></span>
      </div>
      <div class="flex items-center gap-2">
        <span class="text-[10px] text-gray-500 w-14 text-right">Rejected</span>
        <div class="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
          <div class="h-full bg-red-500 rounded-full transition-all duration-500"
            :style="'width:' + (telegram.total ? (telegram.rejected / telegram.total * 100) : 0) + '%'"></div>
        </div>
        <span class="text-xs font-semibold text-gray-700 w-8" x-text="telegram.rejected ?? 0"></span>
      </div>
      <div class="flex items-center gap-2">
        <span class="text-[10px] text-gray-500 w-14 text-right">Pending</span>
        <div class="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
          <div class="h-full bg-amber-400 rounded-full transition-all duration-500"
            :style="'width:' + (telegram.total ? (telegram.no_decision / telegram.total * 100) : 0) + '%'"></div>
        </div>
        <span class="text-xs font-semibold text-gray-700 w-8" x-text="telegram.no_decision ?? 0"></span>
      </div>
    </div>
  </div>
</section>

</main>

<footer class="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8 py-6 text-center text-xs text-gray-300">
  Groundswell Operations Dashboard
</footer>

<script>
function dashboard() {
  return {
    agents: [],
    attention: [],
    intel: {},
    backlog: { by_platform: {}, by_status: {}, total_ready: 0 },
    apibudget: { today: {}, limits: {}, week_total: 0 },
    rss: {},
    activity: [],
    schedule: [],
    telegram: {},
    stats: {},
    postingHistory: [],
    lastUpdated: '',
    systemStatus: 'ok',
    hasError: false,

    get scoredPct() {
      const total = this.rss.total || 0;
      if (!total) return 0;
      return Math.round(((this.rss.scored || 0) / total) * 100);
    },

    get uniqueAgents() {
      const set = new Set(this.activity.map(e => e.agent).filter(Boolean));
      return [...set].sort();
    },

    get filteredActivity() {
      const f = this.$data?.agentFilter || 'all';
      if (f === 'all') return this.activity;
      return this.activity.filter(e => e.agent === f);
    },

    init() {
      this.fetchState();
      setInterval(() => this.fetchState(), 300000);
    },

    fetchState() {
      fetch('/api/state')
        .then(r => r.json())
        .then(data => this.updateDashboard(data))
        .catch(e => { this.lastUpdated = 'Error: ' + e.message; });
    },

    updateDashboard(data) {
      this.agents = data.agents || [];
      this.attention = data.attention || [];
      this.intel = data.intel || {};
      this.backlog = data.backlog || { by_platform: {}, by_status: {}, total_ready: 0 };
      this.apibudget = data.api_budget || { today: {}, limits: {}, week_total: 0 };
      this.rss = data.rss_health || {};
      this.activity = data.activity || [];
      this.schedule = data.schedule || [];
      this.telegram = data.telegram_stats || {};
      this.stats = data.stats || {};
      this.postingHistory = data.posting_history || [];

      const safety = data.brand_safety?.color || 'GREEN';
      this.hasError = this.attention.some(a => a.severity === 'high');
      if (safety === 'BLACK' || safety === 'RED' || this.hasError) {
        this.systemStatus = 'critical';
      } else if (safety === 'YELLOW' || this.attention.length > 0) {
        this.systemStatus = 'warning';
      } else {
        this.systemStatus = 'ok';
      }

      this.lastUpdated = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

      this.$nextTick(() => {
        if (this.postingHistory.length > 1) {
          const counts = this.postingHistory.map(d => d.count);
          this.renderSparkline('spark-posts', counts, '#6366f1');
        }
      });
    },

    relTime(iso) {
      if (!iso) return '-';
      const now = Date.now();
      const then = new Date(iso).getTime();
      const diff = Math.max(0, now - then);
      const s = Math.floor(diff / 1000);
      if (s < 60) return s + 's ago';
      const m = Math.floor(s / 60);
      if (m < 60) return m + 'm ago';
      const h = Math.floor(m / 60);
      if (h < 24) return h + 'h ago';
      const d = Math.floor(h / 24);
      return d + 'd ago';
    },

    formatAgentName(name) {
      if (!name) return '';
      return name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    },

    formatInterval(s) {
      if (s.interval_minutes) return s.interval_minutes + 'm';
      if (s.daily_at) return 'Daily ' + s.daily_at;
      if (s.weekly_at) return 'Weekly ' + s.weekly_at;
      return '-';
    },

    agentDotColor(agent) {
      if (agent.last_result === 'success') return 'bg-emerald-500';
      if (agent.last_result === 'error') return 'bg-red-500';
      if (agent.overdue) return 'bg-amber-500';
      return 'bg-gray-300';
    },

    agentBadgeColor(name) {
      const colors = {
        orchestrator: 'bg-violet-100 text-violet-700',
        publisher: 'bg-blue-100 text-blue-700',
        x_scout: 'bg-teal-100 text-teal-700',
        x_agent: 'bg-sky-100 text-sky-700',
        linkedin_agent: 'bg-blue-100 text-blue-700',
        rss_scout_tech: 'bg-cyan-100 text-cyan-700',
        rss_scout_cannabis: 'bg-green-100 text-green-700',
        rss_fetch: 'bg-gray-100 text-gray-600',
        marketing_manager: 'bg-indigo-100 text-indigo-700',
        creator: 'bg-pink-100 text-pink-700',
        analyst: 'bg-amber-100 text-amber-700',
        scout: 'bg-teal-100 text-teal-700',
        inbound_engager: 'bg-cyan-100 text-cyan-700',
        outbound_engager: 'bg-emerald-100 text-emerald-700',
        seo: 'bg-orange-100 text-orange-700',
        diary: 'bg-purple-100 text-purple-700',
        blog_publisher: 'bg-rose-100 text-rose-700',
        telegram: 'bg-blue-100 text-blue-700',
        dashboard: 'bg-gray-100 text-gray-700',
      };
      return colors[name] || 'bg-gray-100 text-gray-600';
    },

    categoryColor(cat) {
      const c = (cat || '').toLowerCase();
      const map = {
        tier1_activity: 'bg-violet-100 text-violet-700',
        trend: 'bg-blue-100 text-blue-700',
        competitive: 'bg-red-100 text-red-700',
        opportunity: 'bg-emerald-100 text-emerald-700',
        newsjack: 'bg-amber-100 text-amber-700',
        market_signal: 'bg-cyan-100 text-cyan-700',
        cannabis_industry: 'bg-green-100 text-green-700',
        conversation: 'bg-indigo-100 text-indigo-700',
        event_monitoring: 'bg-pink-100 text-pink-700',
      };
      return map[c] || 'bg-gray-100 text-gray-600';
    },

    budgetBarColor(used, limit) {
      const pct = (used || 0) / (limit || 1);
      if (pct >= 0.9) return 'bg-red-500';
      if (pct >= 0.7) return 'bg-amber-500';
      return 'bg-emerald-500';
    },

    summarizeDetails(details) {
      if (!details) return '';
      try {
        const obj = typeof details === 'string' ? JSON.parse(details) : details;
        const keys = Object.keys(obj);
        if (keys.length === 0) return '';
        for (const k of keys) {
          const v = obj[k];
          if (typeof v === 'string' && v.length > 0) return v.substring(0, 80);
        }
        return keys.join(', ');
      } catch { return String(details).substring(0, 80); }
    },

    formatDetails(details) {
      if (!details) return '';
      try {
        const obj = typeof details === 'string' ? JSON.parse(details) : details;
        return JSON.stringify(obj, null, 2);
      } catch { return String(details); }
    },

    renderSparkline(id, data, color) {
      const el = document.getElementById(id);
      if (!el || !data.length) return;
      const w = 64, h = 24;
      const max = Math.max(...data, 1);
      const min = Math.min(...data, 0);
      const range = max - min || 1;
      const pts = data.map((v, i) => {
        const x = (i / Math.max(data.length - 1, 1)) * w;
        const y = h - ((v - min) / range) * (h - 4) - 2;
        return x + ',' + y;
      }).join(' ');
      el.innerHTML = '<svg width="' + w + '" height="' + h + '" viewBox="0 0 ' + w + ' ' + h + '"><polyline fill="none" stroke="' + color + '" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" points="' + pts + '"/></svg>';
    },

    killSwitch() {
      if (!confirm('Set brand safety to BLACK? This halts all agent activity.')) return;
      fetch('/api/kill', { method: 'POST' })
        .then(r => r.json())
        .then(d => { if (d.ok) this.fetchState(); })
        .catch(e => alert('Error: ' + e.message));
    },

    resumeSystem() {
      if (!confirm('Resume system? Brand safety will be set to GREEN.')) return;
      fetch('/api/resume', { method: 'POST' })
        .then(r => r.json())
        .then(d => { if (d.ok) this.fetchState(); })
        .catch(e => alert('Error: ' + e.message));
    },
  };
}
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------

class DashboardHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        sys.stderr.write(f"[dashboard] {args[0]}\n")

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

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/":
            self._send_html(HTML_PAGE)

        elif path == "/api/state":
            conn = get_conn()
            try:
                self._send_json(get_full_dashboard_state(conn))
            finally:
                conn.close()

        else:
            self._send_json({"error": "Not found"}, status=404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/approve":
            body = self._read_body()
            key = body.get("key")
            decision = body.get("decision", "").lower()
            if not key or decision not in ("approve", "reject"):
                self._send_json({"error": "key and decision (approve/reject) required"}, status=400)
                return

            new_status = "approved" if decision == "approve" else "rejected"
            ts = now_iso()
            conn = get_conn()
            try:
                cur = conn.execute(
                    "UPDATE pending_actions SET status = ?, completed_at = ? "
                    "WHERE idempotency_key = ? AND status = 'pending'",
                    (new_status, ts, key),
                )
                conn.commit()
                if cur.rowcount == 0:
                    self._send_json({"error": f"Action '{key}' not found or not pending"}, status=404)
                else:
                    conn.execute(
                        "INSERT INTO events (timestamp, agent, event_type, details) VALUES (?, 'dashboard', ?, ?)",
                        (ts, f"action_{new_status}", json.dumps({"key": key})),
                    )
                    conn.commit()
                    self._send_json({"ok": True, "key": key, "status": new_status})
            finally:
                conn.close()

        elif path == "/api/kill":
            ts = now_iso()
            conn = get_conn()
            try:
                self._set_brand_safety(conn, "BLACK", "Kill switch from dashboard", ts)
                self._send_json({"ok": True, "color": "BLACK"})
            finally:
                conn.close()

        elif path == "/api/resume":
            ts = now_iso()
            conn = get_conn()
            try:
                self._set_brand_safety(conn, "GREEN", "Resume from dashboard", ts)
                self._send_json({"ok": True, "color": "GREEN"})
            finally:
                conn.close()

        else:
            self._send_json({"error": "Not found"}, status=404)

    def _set_brand_safety(self, conn, color, reason, ts):
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
        conn.execute(
            "INSERT INTO events (timestamp, agent, event_type, details) VALUES (?, 'dashboard', 'brand_safety_change', ?)",
            (ts, json.dumps({"color": color, "reason": reason})),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_serve(port):
    if not os.path.exists(DB_PATH):
        print(f"Warning: Database not found at {DB_PATH}", file=sys.stderr)
        print("Run 'python3 tools/db.py init' first.", file=sys.stderr)
        sys.exit(1)

    server = HTTPServer(("0.0.0.0", port), DashboardHandler)
    print(f"Groundswell Dashboard v2 running on http://localhost:{port}")
    print(f"Database: {DB_PATH}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


def cmd_status():
    if not os.path.exists(DB_PATH):
        print(json.dumps({"error": f"Database not found: {DB_PATH}"}))
        sys.exit(1)

    conn = get_conn()
    try:
        state = get_full_dashboard_state(conn)
        print(json.dumps(state, indent=2, default=str))
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Groundswell Dashboard v2")
    sub = parser.add_subparsers(dest="command")

    serve_p = sub.add_parser("serve", help="Start the dashboard web server")
    serve_p.add_argument("--port", type=int, default=8500, help="Port (default: 8500)")

    sub.add_parser("status", help="Print system state as JSON")

    args = parser.parse_args()

    if args.command == "serve":
        cmd_serve(args.port)
    elif args.command == "status":
        cmd_status()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
