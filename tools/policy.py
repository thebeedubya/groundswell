#!/usr/bin/env python3
"""
Groundswell Policy Gate — Brand safety and content policy CLI.

Every agent calls this before every action. Checks brand safety color,
platform cooldowns, rate limits, content filters, tier targets, and
trust phase gates.

Usage:
    python3 tools/policy.py check --action post --text "..." --platform x
    python3 tools/policy.py check --action reply --text "..." --target "@kim" --platform x
    python3 tools/policy.py check --action engage --target "@handle" --platform x
    python3 tools/policy.py status
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

try:
    import yaml
except ImportError:
    print(
        json.dumps({"error": "PyYAML is required: pip install pyyaml"}),
        file=sys.stderr,
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# Paths — resolve relative to the repo root (two levels up from this file)
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(REPO_ROOT, "config.yaml")
DB_PATH = os.path.join(REPO_ROOT, "data", "groundswell.db")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_config():
    """Load config.yaml and return the parsed dict."""
    try:
        with open(CONFIG_PATH, "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        fatal(f"config.yaml not found at {CONFIG_PATH}")
    except yaml.YAMLError as exc:
        fatal(f"Invalid config.yaml: {exc}")


def get_db():
    """Return a sqlite3 connection. Creates data/ dir if needed."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def utcnow_iso():
    """Current UTC time as ISO-8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fatal(msg):
    """Print error to stderr and exit 1 (tool error, not a policy decision)."""
    print(json.dumps({"error": msg}), file=sys.stderr)
    sys.exit(1)


def table_exists(conn, name):
    """Check whether a table exists in the database."""
    cur = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    )
    return cur.fetchone() is not None


# ---------------------------------------------------------------------------
# Policy checks — each returns (decision_override, reasons, warnings)
#   decision_override: "BLOCK" | "ESCALATE" | None (no opinion)
# ---------------------------------------------------------------------------


def check_brand_safety_color(conn, config):
    """Check brand_safety_color from strategy_state table."""
    reasons = []
    warnings = []
    decision = None

    # Read color from DB; fall back to config default
    color = config.get("policy", {}).get("brand_safety", {}).get("initial_color", "GREEN")

    if table_exists(conn, "strategy_state"):
        row = conn.execute(
            "SELECT value FROM strategy_state WHERE key = 'brand_safety_color'"
        ).fetchone()
        if row:
            color = row["value"].strip().strip('"').upper()

    if color == "BLACK":
        decision = "BLOCK"
        reasons.append("brand_safety_black: system halted")
    elif color == "RED":
        decision = "ESCALATE"
        reasons.append("brand_safety_red: all actions require approval")
    elif color == "YELLOW":
        # Caller will check action type to decide ESCALATE vs APPROVE
        decision = "YELLOW"  # sentinel — handled in run_checks
        reasons.append("brand_safety_yellow: elevated caution")

    return decision, reasons, warnings, color


def check_platform_cooldown(conn, platform):
    """Check platform_cooldowns table for an active cooldown."""
    reasons = []

    if not table_exists(conn, "platform_cooldowns"):
        return None, reasons, []

    row = conn.execute(
        "SELECT cooldown_until, reason FROM platform_cooldowns WHERE platform = ?",
        (platform,),
    ).fetchone()

    if row:
        cooldown_until = row["cooldown_until"]
        try:
            until_dt = datetime.fromisoformat(cooldown_until.replace("Z", "+00:00"))
            now_dt = datetime.now(timezone.utc)
            if until_dt > now_dt:
                reason_text = row["reason"] or ""
                reasons.append(
                    f"platform_cooldown: {platform} until {cooldown_until}"
                    + (f" ({reason_text})" if reason_text else "")
                )
                return "BLOCK", reasons, []
        except (ValueError, TypeError):
            pass  # Malformed timestamp — skip

    return None, reasons, []


def check_rate_limits(conn, config, agent="system"):
    """Count events in the last hour and compare to configured limit."""
    reasons = []
    warnings = []
    decision = None

    max_actions = (
        config.get("policy", {})
        .get("rate_limits", {})
        .get("max_actions_per_hour", 30)
    )

    count = 0
    if table_exists(conn, "events"):
        row = conn.execute(
            """
            SELECT COUNT(*) as cnt FROM events
            WHERE timestamp > datetime('now', '-1 hour')
            """,
        ).fetchone()
        count = row["cnt"] if row else 0

    if count >= max_actions:
        decision = "BLOCK"
        reasons.append(f"rate_limit_exceeded: {count}/{max_actions} actions this hour")
    elif count >= int(max_actions * 0.9):
        warnings.append(
            f"approaching_rate_limit: {count}/{max_actions} actions this hour"
        )

    return decision, reasons, warnings, count


def check_content_filter(config, text):
    """Check text against blocked topics and cannabis never-say phrases."""
    reasons = []

    if not text:
        return None, reasons, []

    content_filter = config.get("policy", {}).get("content_filter", {})
    text_lower = text.lower()

    # Blocked topics — check if topic keywords appear in text
    blocked_topics = content_filter.get("blocked_topics", [])
    for topic in blocked_topics:
        # Convert underscore-separated topic names to space-separated for matching
        topic_words = topic.replace("_", " ")
        if topic_words in text_lower:
            reasons.append(f"content_blocked: blocked topic '{topic}'")

    # Cannabis never-say phrases — case-insensitive substring match
    cannabis_rules = content_filter.get("cannabis_rules", {})
    never_say = cannabis_rules.get("never_say", [])
    for phrase in never_say:
        if phrase.lower() in text_lower:
            reasons.append(f"content_blocked: cannabis never-say phrase '{phrase}'")

    decision = "BLOCK" if reasons else None
    return decision, reasons, []


def check_tier_target(conn, config, target, platform):
    """Look up target in tier_targets table and apply trust phase rules."""
    reasons = []

    if not target:
        return None, reasons, []

    # Normalize handle — strip leading @
    handle = target.lstrip("@")

    trust_phase = config.get("trust", {}).get("current_phase", "A").upper()

    # Look up tier from DB
    tier = None
    if table_exists(conn, "tier_targets"):
        row = conn.execute(
            "SELECT tier FROM tier_targets WHERE handle = ? AND platform = ?",
            (handle, platform),
        ).fetchone()
        if row:
            tier = row["tier"]
        else:
            # Try without platform filter (handle might be unique)
            row = conn.execute(
                "SELECT tier FROM tier_targets WHERE handle = ?",
                (handle,),
            ).fetchone()
            if row:
                tier = row["tier"]

    if tier is None:
        # Unknown target — in Phase A escalate, otherwise approve
        if trust_phase == "A":
            reasons.append(f"tier_unknown: @{handle} not in tier_targets, phase A requires approval")
            return "ESCALATE", reasons, []
        return None, reasons, []

    if trust_phase == "A":
        reasons.append(f"tier{tier}_target: @{handle} is Tier {tier}, phase A requires approval")
        return "ESCALATE", reasons, []
    elif trust_phase == "B":
        if tier <= 2:
            reasons.append(
                f"tier{tier}_target: @{handle} is Tier {tier}, requires approval in phase B"
            )
            return "ESCALATE", reasons, []
        return None, reasons, []
    else:
        # Phase C — approve all
        return None, reasons, []


def check_posting_window(config, platform):
    """Block posts outside configured posting windows. Replies/engagement are always allowed."""
    reasons = []
    warnings = []

    platform_config = config.get("platforms", {}).get(platform, {})
    windows = platform_config.get("post_windows")
    if not windows:
        return None, reasons, []  # No windows configured — allow

    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        return None, reasons, []  # Can't check without zoneinfo

    tz_name = config.get("schedule", {}).get("timezone", "America/Chicago")
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        return None, reasons, []

    now = datetime.now(tz)
    day_type = "weekend" if now.weekday() >= 5 else "weekday"
    day_windows = windows.get(day_type, [])

    if not day_windows:
        reasons.append(f"posting_window_closed: no {platform} posting on {day_type}s")
        return "BLOCK", reasons, []

    current_time = now.strftime("%H:%M")
    in_window = False
    next_window = None
    for w in day_windows:
        parts = w.split("-")
        if len(parts) == 2:
            start, end = parts[0].strip(), parts[1].strip()
            if start <= current_time <= end:
                in_window = True
                break
            if start > current_time and (next_window is None or start < next_window):
                next_window = start

    if not in_window:
        window_str = ", ".join(day_windows)
        msg = f"posting_window_closed: {platform} posts only allowed {window_str} CT ({day_type})"
        if next_window:
            msg += f" — next window at {next_window}"
        reasons.append(msg)
        return "BLOCK", reasons, []

    return None, reasons, []


def check_trust_phase_post(config, action):
    """Trust phase gate for post actions."""
    reasons = []

    if action != "post":
        return None, reasons, []

    trust_phase = config.get("trust", {}).get("current_phase", "A").upper()

    if trust_phase == "A":
        reasons.append("trust_phase_a: all posts require approval")
        return "ESCALATE", reasons, []
    elif trust_phase == "B":
        # Approve routine posts; novel content would need a content-type flag
        # which is beyond scope — approve by default in phase B for posts
        return None, reasons, []

    # Phase C — approve all
    return None, reasons, []


# ---------------------------------------------------------------------------
# Main check orchestration
# ---------------------------------------------------------------------------

DECISION_RANK = {"APPROVE": 0, "ESCALATE": 1, "BLOCK": 2}


def merge_decision(current, incoming):
    """Return the more restrictive of two decisions."""
    if incoming is None:
        return current
    if DECISION_RANK.get(incoming, 0) > DECISION_RANK.get(current, 0):
        return incoming
    return current


def run_checks(action, text, target, platform, config, conn):
    """Run all policy checks in order and return the final verdict."""
    final_decision = "APPROVE"
    all_reasons = []
    all_warnings = []

    # 1. Brand Safety Color
    decision, reasons, warnings, color = check_brand_safety_color(conn, config)
    if decision == "YELLOW":
        # YELLOW: ESCALATE posts, APPROVE low-risk replies/engage
        if action == "post":
            final_decision = merge_decision(final_decision, "ESCALATE")
            all_reasons.extend(reasons)
        else:
            all_warnings.extend(reasons)  # Demote to warning for non-post
    else:
        final_decision = merge_decision(final_decision, decision)
        all_reasons.extend(reasons)
    all_warnings.extend(warnings)

    # 2. Platform Cooldown
    decision, reasons, warnings = check_platform_cooldown(conn, platform)
    final_decision = merge_decision(final_decision, decision)
    all_reasons.extend(reasons)
    all_warnings.extend(warnings)

    # 3. Rate Limits
    decision, reasons, warnings, _ = check_rate_limits(conn, config)
    final_decision = merge_decision(final_decision, decision)
    all_reasons.extend(reasons)
    all_warnings.extend(warnings)

    # 4. Content Filter (post/reply with text)
    if action in ("post", "reply") and text:
        decision, reasons, warnings = check_content_filter(config, text)
        final_decision = merge_decision(final_decision, decision)
        all_reasons.extend(reasons)
        all_warnings.extend(warnings)

    # 5. Tier Target Check (reply/engage with target)
    if action in ("reply", "engage") and target:
        decision, reasons, warnings = check_tier_target(conn, config, target, platform)
        final_decision = merge_decision(final_decision, decision)
        all_reasons.extend(reasons)
        all_warnings.extend(warnings)

    # 6. Trust Phase Gate (post actions)
    if action == "post":
        decision, reasons, warnings = check_trust_phase_post(config, action)
        final_decision = merge_decision(final_decision, decision)
        all_reasons.extend(reasons)
        all_warnings.extend(warnings)

    # 7. Posting Window Check (post actions only — replies/engagement anytime)
    if action == "post" and platform:
        decision, reasons, warnings = check_posting_window(config, platform)
        final_decision = merge_decision(final_decision, decision)
        all_reasons.extend(reasons)
        all_warnings.extend(warnings)

    return {
        "decision": final_decision,
        "reasons": all_reasons,
        "warnings": all_warnings,
    }


# ---------------------------------------------------------------------------
# Status command
# ---------------------------------------------------------------------------


def run_status(config, conn):
    """Return current policy state summary."""
    # Brand safety color
    color = config.get("policy", {}).get("brand_safety", {}).get("initial_color", "GREEN")
    if table_exists(conn, "strategy_state"):
        row = conn.execute(
            "SELECT value FROM strategy_state WHERE key = 'brand_safety_color'"
        ).fetchone()
        if row:
            color = row["value"].strip().strip('"').upper()

    # Trust phase
    trust_phase = config.get("trust", {}).get("current_phase", "A")

    # Active cooldowns
    active_cooldowns = {}
    if table_exists(conn, "platform_cooldowns"):
        now_iso = utcnow_iso()
        rows = conn.execute(
            "SELECT platform, cooldown_until, reason FROM platform_cooldowns WHERE cooldown_until > ?",
            (now_iso,),
        ).fetchall()
        for r in rows:
            active_cooldowns[r["platform"]] = {
                "until": r["cooldown_until"],
                "reason": r["reason"],
            }

    # Actions this hour
    actions_this_hour = 0
    if table_exists(conn, "events"):
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM events WHERE timestamp > datetime('now', '-1 hour')"
        ).fetchone()
        actions_this_hour = row["cnt"] if row else 0

    max_actions = (
        config.get("policy", {})
        .get("rate_limits", {})
        .get("max_actions_per_hour", 30)
    )

    # Enabled platforms
    platforms_cfg = config.get("platforms", {})
    enabled_platforms = [p for p, v in platforms_cfg.items() if v.get("enabled")]

    return {
        "brand_safety_color": color,
        "trust_phase": trust_phase,
        "active_cooldowns": active_cooldowns,
        "actions_this_hour": actions_this_hour,
        "max_actions_per_hour": max_actions,
        "enabled_platforms": enabled_platforms,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser():
    parser = argparse.ArgumentParser(
        description="Groundswell Policy Gate",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    # check
    check_parser = sub.add_parser("check", help="Run policy checks on a proposed action")
    check_parser.add_argument(
        "--action",
        required=True,
        choices=["post", "reply", "engage"],
        help="Type of action",
    )
    check_parser.add_argument("--text", default=None, help="Content text to check")
    check_parser.add_argument(
        "--target", default=None, help="Target handle (e.g. @kimrivers)"
    )
    check_parser.add_argument(
        "--platform",
        required=True,
        choices=["x", "linkedin", "threads"],
        help="Platform",
    )

    # status
    sub.add_parser("status", help="Show current policy state summary")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help(sys.stderr)
        sys.exit(1)

    config = load_config()
    conn = get_db()

    try:
        if args.command == "check":
            result = run_checks(
                action=args.action,
                text=args.text,
                target=args.target,
                platform=args.platform,
                config=config,
                conn=conn,
            )
        elif args.command == "status":
            result = run_status(config, conn)
        else:
            fatal(f"Unknown command: {args.command}")
            return  # unreachable

        print(json.dumps(result, indent=2))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
