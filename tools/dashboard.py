#!/usr/bin/env python3
"""
Groundswell Dashboard — local web UI for approvals and status monitoring.

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


def get_pending_approvals(conn):
    rows = conn.execute(
        "SELECT * FROM pending_actions WHERE status = 'pending' ORDER BY created_at ASC"
    ).fetchall()
    return rows_to_list(rows)


def get_recent_events(conn, limit=20):
    rows = conn.execute(
        "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return rows_to_list(rows)


def get_schedule(conn):
    rows = conn.execute(
        "SELECT * FROM schedule ORDER BY next_due ASC"
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


def get_full_state(conn):
    safety = get_brand_safety(conn)
    return {
        "brand_safety": safety,
        "trust_phase": get_trust_phase(conn),
        "approvals": get_pending_approvals(conn),
        "events": get_recent_events(conn),
        "schedule": get_schedule(conn),
        "signals": get_pending_signals(conn),
        "stats": get_quick_stats(conn),
        "timestamp": now_iso(),
    }


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Groundswell Dashboard</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    background: #0d1117;
    color: #c9d1d9;
    font-family: 'SF Mono', 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
    font-size: 14px;
    line-height: 1.5;
    padding: 16px;
}
h1 {
    color: #3fb950;
    font-size: 20px;
    margin-bottom: 4px;
}
h2 {
    color: #8b949e;
    font-size: 14px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 8px;
    padding-bottom: 4px;
    border-bottom: 1px solid #21262d;
}
.header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid #21262d;
}
.header-right {
    text-align: right;
    font-size: 12px;
    color: #8b949e;
}
.grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
}
@media (max-width: 900px) {
    .grid { grid-template-columns: 1fr; }
}
.card {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 6px;
    padding: 16px;
}
.card.full-width {
    grid-column: 1 / -1;
}
.banner {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 12px 16px;
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 6px;
    margin-bottom: 16px;
}
.safety-dot {
    width: 16px;
    height: 16px;
    border-radius: 50%;
    flex-shrink: 0;
    box-shadow: 0 0 8px currentColor;
}
.safety-GREEN { background: #3fb950; color: #3fb950; }
.safety-YELLOW { background: #d29922; color: #d29922; }
.safety-RED { background: #f85149; color: #f85149; }
.safety-BLACK { background: #484f58; color: #484f58; }
.stats-row {
    display: flex;
    gap: 16px;
    margin-bottom: 16px;
}
.stat-box {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 6px;
    padding: 12px 16px;
    flex: 1;
    text-align: center;
}
.stat-value {
    font-size: 28px;
    font-weight: 700;
    color: #3fb950;
}
.stat-label {
    font-size: 11px;
    color: #8b949e;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}
th {
    text-align: left;
    color: #8b949e;
    font-weight: 600;
    padding: 6px 8px;
    border-bottom: 1px solid #21262d;
    font-size: 11px;
    text-transform: uppercase;
}
td {
    padding: 6px 8px;
    border-bottom: 1px solid #21262d;
    max-width: 300px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
tr:hover { background: #1c2128; }
.btn {
    padding: 4px 12px;
    border: 1px solid #30363d;
    border-radius: 4px;
    background: #21262d;
    color: #c9d1d9;
    cursor: pointer;
    font-family: inherit;
    font-size: 12px;
    margin-right: 4px;
}
.btn:hover { background: #30363d; }
.btn-approve { border-color: #3fb950; color: #3fb950; }
.btn-approve:hover { background: #238636; color: #fff; }
.btn-reject { border-color: #f85149; color: #f85149; }
.btn-reject:hover { background: #da3633; color: #fff; }
.btn-kill { border-color: #f85149; color: #f85149; }
.btn-kill:hover { background: #da3633; color: #fff; }
.btn-resume { border-color: #3fb950; color: #3fb950; }
.btn-resume:hover { background: #238636; color: #fff; }
.empty { color: #484f58; font-style: italic; padding: 12px 0; }
.tag {
    display: inline-block;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 11px;
    font-weight: 600;
}
.tag-enabled { background: #0d4429; color: #3fb950; }
.tag-disabled { background: #3d1f17; color: #f85149; }
.priority-high { color: #f85149; }
.priority-med { color: #d29922; }
.priority-low { color: #8b949e; }
.actions-bar {
    display: flex;
    gap: 8px;
    margin-bottom: 16px;
}
</style>
</head>
<body>

<div class="header">
    <div>
        <h1>GROUNDSWELL</h1>
        <span style="color: #8b949e; font-size: 12px;">Multi-Agent Social Growth Engine</span>
    </div>
    <div class="header-right">
        <div id="last-updated">Loading...</div>
        <div class="actions-bar" style="margin-top: 8px; margin-bottom: 0;">
            <button class="btn btn-kill" onclick="killSwitch()">KILL SWITCH</button>
            <button class="btn btn-resume" onclick="resumeSystem()">RESUME</button>
        </div>
    </div>
</div>

<div id="banner" class="banner">
    <div id="safety-dot" class="safety-dot safety-GREEN"></div>
    <div>
        <span id="safety-label" style="font-weight: 700;">GREEN</span>
        <span style="color: #8b949e; margin: 0 8px;">|</span>
        <span style="color: #8b949e;">Trust Phase:</span>
        <span id="trust-phase" style="font-weight: 700;">A</span>
    </div>
</div>

<div class="stats-row" id="stats-row">
    <div class="stat-box"><div class="stat-value" id="stat-posts">-</div><div class="stat-label">Posts Today</div></div>
    <div class="stat-box"><div class="stat-value" id="stat-actions">-</div><div class="stat-label">Actions / Hour</div></div>
    <div class="stat-box"><div class="stat-value" id="stat-signals">-</div><div class="stat-label">Pending Signals</div></div>
    <div class="stat-box"><div class="stat-value" id="stat-approvals">-</div><div class="stat-label">Pending Approvals</div></div>
</div>

<div class="grid">

    <div class="card full-width">
        <h2>Pending Approvals</h2>
        <div id="approvals-content"><div class="empty">Loading...</div></div>
    </div>

    <div class="card">
        <h2>Recent Activity</h2>
        <div id="events-content"><div class="empty">Loading...</div></div>
    </div>

    <div class="card">
        <h2>Signals Queue</h2>
        <div id="signals-content"><div class="empty">Loading...</div></div>
    </div>

    <div class="card full-width">
        <h2>Schedule</h2>
        <div id="schedule-content"><div class="empty">Loading...</div></div>
    </div>

</div>

<script>
function esc(s) {
    if (s == null) return '';
    var d = document.createElement('div');
    d.textContent = String(s);
    return d.innerHTML;
}

function shortTime(iso) {
    if (!iso) return '-';
    try {
        var d = new Date(iso);
        return d.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
    } catch(e) { return iso; }
}

function shortDateTime(iso) {
    if (!iso) return '-';
    try {
        var d = new Date(iso);
        return d.toLocaleDateString([], {month:'short', day:'numeric'}) + ' ' +
               d.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
    } catch(e) { return iso; }
}

function truncate(s, n) {
    if (!s) return '';
    s = String(s);
    return s.length > n ? s.substring(0, n) + '...' : s;
}

function priorityClass(p) {
    if (p <= 3) return 'priority-high';
    if (p <= 6) return 'priority-med';
    return 'priority-low';
}

function renderApprovals(approvals) {
    var el = document.getElementById('approvals-content');
    if (!approvals || approvals.length === 0) {
        el.innerHTML = '<div class="empty">No pending approvals</div>';
        return;
    }
    var html = '<table><tr><th>Key</th><th>Agent</th><th>Type</th><th>Payload</th><th>Created</th><th>Actions</th></tr>';
    for (var i = 0; i < approvals.length; i++) {
        var a = approvals[i];
        html += '<tr>';
        html += '<td>' + esc(a.idempotency_key) + '</td>';
        html += '<td>' + esc(a.agent) + '</td>';
        html += '<td>' + esc(a.action_type) + '</td>';
        html += '<td title="' + esc(a.payload) + '">' + esc(truncate(a.payload, 60)) + '</td>';
        html += '<td>' + shortDateTime(a.created_at) + '</td>';
        html += '<td>';
        html += '<button class="btn btn-approve" onclick="doApproval(\'' + esc(a.idempotency_key) + '\', \'approve\')">Approve</button>';
        html += '<button class="btn btn-reject" onclick="doApproval(\'' + esc(a.idempotency_key) + '\', \'reject\')">Reject</button>';
        html += '</td>';
        html += '</tr>';
    }
    html += '</table>';
    el.innerHTML = html;
}

function renderEvents(events) {
    var el = document.getElementById('events-content');
    if (!events || events.length === 0) {
        el.innerHTML = '<div class="empty">No recent events</div>';
        return;
    }
    var html = '<table><tr><th>Time</th><th>Agent</th><th>Type</th><th>Details</th></tr>';
    for (var i = 0; i < events.length; i++) {
        var e = events[i];
        html += '<tr>';
        html += '<td>' + shortDateTime(e.timestamp) + '</td>';
        html += '<td>' + esc(e.agent) + '</td>';
        html += '<td>' + esc(e.event_type) + '</td>';
        html += '<td title="' + esc(e.details) + '">' + esc(truncate(e.details, 80)) + '</td>';
        html += '</tr>';
    }
    html += '</table>';
    el.innerHTML = html;
}

function renderSignals(signals) {
    var el = document.getElementById('signals-content');
    if (!signals || signals.length === 0) {
        el.innerHTML = '<div class="empty">No pending signals</div>';
        return;
    }
    var html = '<table><tr><th>Pri</th><th>Type</th><th>Source</th><th>Data</th><th>Created</th></tr>';
    for (var i = 0; i < signals.length; i++) {
        var s = signals[i];
        html += '<tr>';
        html += '<td class="' + priorityClass(s.priority) + '">' + esc(s.priority) + '</td>';
        html += '<td>' + esc(s.type) + '</td>';
        html += '<td>' + esc(s.source_agent) + '</td>';
        html += '<td title="' + esc(s.data) + '">' + esc(truncate(s.data, 60)) + '</td>';
        html += '<td>' + shortDateTime(s.created_at) + '</td>';
        html += '</tr>';
    }
    html += '</table>';
    el.innerHTML = html;
}

function renderSchedule(schedule) {
    var el = document.getElementById('schedule-content');
    if (!schedule || schedule.length === 0) {
        el.innerHTML = '<div class="empty">No scheduled tasks</div>';
        return;
    }
    var html = '<table><tr><th>Task</th><th>Agent</th><th>Interval</th><th>Next Due</th><th>Last Run</th><th>Result</th><th>Status</th></tr>';
    for (var i = 0; i < schedule.length; i++) {
        var s = schedule[i];
        var interval = '';
        if (s.interval_minutes) interval = s.interval_minutes + 'm';
        else if (s.daily_at) interval = 'daily ' + s.daily_at;
        else if (s.weekly_at) interval = 'weekly ' + s.weekly_at;
        html += '<tr>';
        html += '<td>' + esc(s.task) + '</td>';
        html += '<td>' + esc(s.agent) + '</td>';
        html += '<td>' + esc(interval) + '</td>';
        html += '<td>' + shortDateTime(s.next_due) + '</td>';
        html += '<td>' + shortDateTime(s.last_run) + '</td>';
        html += '<td>' + esc(truncate(s.last_result, 40)) + '</td>';
        html += '<td>' + (s.enabled ? '<span class="tag tag-enabled">ON</span>' : '<span class="tag tag-disabled">OFF</span>') + '</td>';
        html += '</tr>';
    }
    html += '</table>';
    el.innerHTML = html;
}

function updateDashboard(data) {
    // Safety banner
    var color = data.brand_safety ? data.brand_safety.color : 'GREEN';
    var dot = document.getElementById('safety-dot');
    dot.className = 'safety-dot safety-' + color;
    var label = document.getElementById('safety-label');
    label.textContent = color;
    label.style.color = {'GREEN':'#3fb950','YELLOW':'#d29922','RED':'#f85149','BLACK':'#484f58'}[color] || '#c9d1d9';

    document.getElementById('trust-phase').textContent = data.trust_phase || 'A';

    // Stats
    if (data.stats) {
        document.getElementById('stat-posts').textContent = data.stats.posts_today;
        document.getElementById('stat-actions').textContent = data.stats.actions_this_hour;
        document.getElementById('stat-signals').textContent = data.stats.pending_signals;
        document.getElementById('stat-approvals').textContent = data.stats.pending_approvals;
    }

    renderApprovals(data.approvals);
    renderEvents(data.events);
    renderSignals(data.signals);
    renderSchedule(data.schedule);

    document.getElementById('last-updated').textContent = 'Updated: ' + new Date().toLocaleTimeString();
}

function fetchState() {
    fetch('/api/state')
        .then(function(r) { return r.json(); })
        .then(updateDashboard)
        .catch(function(e) {
            document.getElementById('last-updated').textContent = 'Error: ' + e.message;
        });
}

function doApproval(key, decision) {
    fetch('/api/approve', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({key: key, decision: decision})
    })
    .then(function(r) { return r.json(); })
    .then(function(d) {
        if (d.ok) fetchState();
        else alert('Error: ' + JSON.stringify(d));
    })
    .catch(function(e) { alert('Error: ' + e.message); });
}

function killSwitch() {
    if (!confirm('Set brand safety to BLACK? This halts all agent activity.')) return;
    fetch('/api/kill', { method: 'POST' })
        .then(function(r) { return r.json(); })
        .then(function(d) { if (d.ok) fetchState(); })
        .catch(function(e) { alert('Error: ' + e.message); });
}

function resumeSystem() {
    if (!confirm('Resume system? Brand safety will be set to GREEN.')) return;
    fetch('/api/resume', { method: 'POST' })
        .then(function(r) { return r.json(); })
        .then(function(d) { if (d.ok) fetchState(); })
        .catch(function(e) { alert('Error: ' + e.message); });
}

// Initial load + polling
fetchState();
setInterval(fetchState, 10000);
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------

class DashboardHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        # Quieter logging: just method + path
        sys.stderr.write(f"[dashboard] {args[0]}\n")

    def _send_json(self, data, status=200):
        body = json.dumps(data, indent=2, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
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
        qs = urllib.parse.parse_qs(parsed.query)

        if path == "/":
            self._send_html(HTML_PAGE)

        elif path == "/api/state":
            conn = get_conn()
            try:
                self._send_json(get_full_state(conn))
            finally:
                conn.close()

        elif path == "/api/approvals":
            conn = get_conn()
            try:
                data = get_pending_approvals(conn)
                self._send_json({"approvals": data, "count": len(data)})
            finally:
                conn.close()

        elif path == "/api/events":
            limit = int(qs.get("limit", [20])[0])
            conn = get_conn()
            try:
                data = get_recent_events(conn, limit=limit)
                self._send_json({"events": data, "count": len(data)})
            finally:
                conn.close()

        elif path == "/api/schedule":
            conn = get_conn()
            try:
                data = get_schedule(conn)
                self._send_json({"schedule": data, "count": len(data)})
            finally:
                conn.close()

        elif path == "/api/signals":
            conn = get_conn()
            try:
                data = get_pending_signals(conn)
                self._send_json({"signals": data, "count": len(data)})
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
                    # Log the approval/rejection event
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
# CLI commands
# ---------------------------------------------------------------------------

def cmd_serve(port):
    if not os.path.exists(DB_PATH):
        print(f"Warning: Database not found at {DB_PATH}", file=sys.stderr)
        print("Run 'python3 tools/db.py init' first.", file=sys.stderr)
        sys.exit(1)

    server = HTTPServer(("0.0.0.0", port), DashboardHandler)
    print(f"Groundswell Dashboard running on http://0.0.0.0:{port}")
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
        state = get_full_state(conn)
        print(json.dumps(state, indent=2, default=str))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Groundswell Dashboard")
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
