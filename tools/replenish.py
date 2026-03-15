#!/usr/bin/env python3
"""
replenish.py — Blog-to-social content pipeline for Groundswell.

Scans Brad's blog, git commits, and Claude Code sessions for raw material.
The Creator agent calls this tool, then uses its own reasoning to generate
social content from the results. This script handles scanning, parsing,
and backlog management — not content generation.

Usage:
    python3 tools/replenish.py scan-blog
    python3 tools/replenish.py scan-commits [--days 1]
    python3 tools/replenish.py scan-sessions [--hours 24]
    python3 tools/replenish.py add-to-backlog --platform x --type native --text "..."  [--priority 5]
    python3 tools/replenish.py add-thread --platform x --texts '["t1","t2"]' [--priority 5]
    python3 tools/replenish.py backlog-status
    python3 tools/replenish.py mark-processed --slug "post-slug"
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import uuid

from _common import REPO_ROOT, DATA_DIR

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BACKLOG_PATH = os.path.join(DATA_DIR, "backlog.json")
REPLENISH_LOG_PATH = os.path.join(DATA_DIR, "replenish_log.json")
BLOG_DIR = os.path.expanduser("~/Projects/dbradwood.com/content/writing")

SKIP_SLUGS = {"post-template", "privacy-policy"}

COMMIT_REPOS = [
    os.path.expanduser("~/Projects/groundswell"),
    os.path.expanduser("~/Projects/forge-ecosystem"),
    os.path.expanduser("~/Projects/forge-brain"),
    os.path.expanduser("~/Projects/leroy"),
    os.path.expanduser("~/Projects/dbradwood.com"),
]

# Backlog burn rates for estimating days of content remaining
BURN_RATES = {
    "x": 5,         # 5 posts/day
    "linkedin": 2,  # 2 posts/day
    "threads": 3,
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _load_json(path, default=None):
    if default is None:
        default = []
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return default


def _save_json(path, data):
    _ensure_data_dir()
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
        f.write("\n")


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _out(obj):
    """Print JSON to stdout."""
    print(json.dumps(obj, indent=2, default=str))


def _err(msg):
    """Print error to stderr and exit 1."""
    print(json.dumps({"error": msg}), file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# MDX Parsing
# ---------------------------------------------------------------------------

def parse_mdx(filepath):
    """Parse an MDX file, extracting frontmatter and body."""
    with open(filepath, "r") as f:
        raw = f.read()

    result = {
        "title": "",
        "summary": "",
        "tags": [],
        "slug": "",
        "published_at": "",
        "body": "",
        "filepath": filepath,
    }

    fname = os.path.basename(filepath)
    result["slug"] = fname.replace(".mdx", "")

    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", raw, re.DOTALL)
    if fm_match:
        fm_text = fm_match.group(1)
        for line in fm_text.split("\n"):
            line = line.strip()
            if line.startswith("title:"):
                result["title"] = line[6:].strip().strip("'\"")
            elif line.startswith("summary:"):
                result["summary"] = line[8:].strip().strip("'\"")
            elif line.startswith("publishedAt:"):
                result["published_at"] = line[12:].strip().strip("'\"")
            elif line.startswith("tags:"):
                # tags might be inline YAML list: tags: [a, b, c]
                tag_str = line[5:].strip()
                tag_match = re.match(r"\[(.*?)\]", tag_str)
                if tag_match:
                    result["tags"] = [
                        t.strip().strip("'\"")
                        for t in tag_match.group(1).split(",")
                        if t.strip()
                    ]
        result["body"] = raw[fm_match.end():].strip()
    else:
        result["body"] = raw.strip()

    return result


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_scan_blog():
    """Scan blog directory for unprocessed MDX posts."""
    if not os.path.isdir(BLOG_DIR):
        _err(f"Blog directory not found: {BLOG_DIR}")

    log = _load_json(REPLENISH_LOG_PATH, default={})
    if isinstance(log, list):
        # Migrate old list format to dict if needed
        log = {}

    processed_slugs = set(log.keys())

    mdx_files = sorted(
        f for f in os.listdir(BLOG_DIR)
        if f.endswith(".mdx")
    )

    unprocessed = []
    total = 0

    for fname in mdx_files:
        slug = fname.replace(".mdx", "")
        if slug in SKIP_SLUGS:
            continue
        total += 1

        if slug in processed_slugs:
            continue

        filepath = os.path.join(BLOG_DIR, fname)
        parsed = parse_mdx(filepath)
        unprocessed.append({
            "slug": parsed["slug"],
            "title": parsed["title"],
            "summary": parsed["summary"],
            "tags": parsed["tags"],
            "published_at": parsed["published_at"],
            "filepath": parsed["filepath"],
        })

    _out({
        "unprocessed": unprocessed,
        "processed_count": total - len(unprocessed),
        "total_count": total,
    })


def cmd_scan_commits(days=1):
    """Scan recent git commits across Brad's repos."""
    since = f"{days} days ago"
    all_commits = []

    for repo_path in COMMIT_REPOS:
        if not os.path.isdir(repo_path):
            continue
        repo_name = os.path.basename(repo_path)
        try:
            result = subprocess.run(
                [
                    "git", "log",
                    f"--since={since}",
                    "--all",
                    "--format=%H|%h|%s|%aI",
                ],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode != 0:
                continue

            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split("|", 3)
                if len(parts) < 4:
                    continue
                full_hash, short_hash, message, date = parts

                # Get files changed for this commit
                diff_result = subprocess.run(
                    ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", full_hash],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                files_changed = [
                    f.strip() for f in diff_result.stdout.strip().split("\n")
                    if f.strip()
                ] if diff_result.returncode == 0 else []

                all_commits.append({
                    "repo": repo_name,
                    "hash": short_hash,
                    "message": message,
                    "date": date,
                    "files_changed": files_changed,
                })

        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

    _out({
        "commits": all_commits,
        "total": len(all_commits),
    })


def cmd_scan_sessions(hours=24):
    """Scan recent Claude Code session files for system mining material."""
    claude_projects = os.path.expanduser("~/.claude/projects")
    if not os.path.isdir(claude_projects):
        _out({"sessions": [], "total": 0})
        return

    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours)
    sessions = []

    for root, _dirs, files in os.walk(claude_projects):
        for fname in files:
            if not fname.endswith(".jsonl"):
                continue
            fpath = os.path.join(root, fname)
            try:
                stat = os.stat(fpath)
                mtime = datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.timezone.utc)
                if mtime < cutoff:
                    continue

                # Extract project from path
                rel = os.path.relpath(fpath, claude_projects)
                project = rel.split(os.sep)[0] if os.sep in rel else "unknown"

                size_kb = round(stat.st_size / 1024, 1)

                sessions.append({
                    "project": project,
                    "file": fpath,
                    "modified_at": mtime.isoformat(),
                    "size_kb": size_kb,
                })
            except OSError:
                continue

    # Sort by modification time, newest first
    sessions.sort(key=lambda s: s["modified_at"], reverse=True)

    _out({
        "sessions": sessions,
        "total": len(sessions),
    })


def cmd_add_to_backlog(platform, content_type, text, priority=5, content_mix=None):
    """Add a single post to the backlog."""
    backlog = _load_json(BACKLOG_PATH, default=[])

    # Dedup check
    for item in backlog:
        existing_text = item.get("text", "")
        if isinstance(existing_text, str) and existing_text == text:
            _out({"ok": True, "skipped": True, "reason": "duplicate"})
            return

    post_id = uuid.uuid4().hex[:8]
    entry = {
        "id": post_id,
        "type": content_type,
        "platform": platform,
        "priority": priority,
        "format": "single",
        "text": text,
        "created_at": _now_iso(),
    }
    if content_mix:
        entry["content_mix"] = content_mix

    backlog.append(entry)
    _save_json(BACKLOG_PATH, backlog)
    _out({"ok": True, "id": post_id})


def cmd_add_thread(platform, texts, content_type="thread", priority=5, content_mix=None):
    """Add a thread to the backlog."""
    if not isinstance(texts, list) or len(texts) < 2:
        _err("--texts must be a JSON array with at least 2 items")

    backlog = _load_json(BACKLOG_PATH, default=[])

    # Dedup check — compare first tweet of thread
    for item in backlog:
        existing_text = item.get("text", "")
        if isinstance(existing_text, list) and len(existing_text) > 0:
            if existing_text[0] == texts[0]:
                _out({"ok": True, "skipped": True, "reason": "duplicate"})
                return

    post_id = uuid.uuid4().hex[:8]
    entry = {
        "id": post_id,
        "type": content_type,
        "platform": platform,
        "priority": priority,
        "format": "thread",
        "text": texts,
        "created_at": _now_iso(),
    }
    if content_mix:
        entry["content_mix"] = content_mix

    backlog.append(entry)
    _save_json(BACKLOG_PATH, backlog)
    _out({"ok": True, "id": post_id})


def cmd_backlog_status():
    """Report current backlog health."""
    backlog = _load_json(BACKLOG_PATH, default=[])

    total = len(backlog)
    pending = [b for b in backlog if "posted_at" not in b]
    posted = [b for b in backlog if "posted_at" in b]

    # Group by platform
    by_platform = {}
    for item in pending:
        plat = item.get("platform", "unknown")
        by_platform.setdefault(plat, 0)
        by_platform[plat] += 1

    # Group by type
    by_type = {}
    for item in pending:
        t = item.get("type", "unknown")
        by_type.setdefault(t, 0)
        by_type[t] += 1

    # Group by content_mix
    by_mix = {}
    for item in pending:
        m = item.get("content_mix", "untagged")
        by_mix.setdefault(m, 0)
        by_mix[m] += 1

    # Estimate days remaining per platform
    days_remaining = {}
    for plat, count in by_platform.items():
        rate = BURN_RATES.get(plat, 3)
        days_remaining[plat] = round(count / rate, 1)

    _out({
        "total": total,
        "pending": len(pending),
        "posted": len(posted),
        "by_platform": by_platform,
        "by_type": by_type,
        "by_content_mix": by_mix,
        "days_remaining": days_remaining,
    })


def cmd_mark_processed(slug):
    """Mark a blog post slug as processed."""
    log = _load_json(REPLENISH_LOG_PATH, default={})
    if isinstance(log, list):
        log = {}

    if slug in log:
        _out({"ok": True, "already_processed": True, "slug": slug})
        return

    log[slug] = {"processed_at": _now_iso()}
    _save_json(REPLENISH_LOG_PATH, log)
    _out({"ok": True, "slug": slug, "processed_at": log[slug]["processed_at"]})


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Groundswell content replenishment pipeline"
    )
    sub = parser.add_subparsers(dest="command")

    # scan-blog
    sub.add_parser("scan-blog", help="Find unprocessed blog posts")

    # scan-commits
    p_commits = sub.add_parser("scan-commits", help="Recent commits across repos")
    p_commits.add_argument("--days", type=int, default=1)

    # scan-sessions
    p_sessions = sub.add_parser("scan-sessions", help="Recent Claude Code sessions")
    p_sessions.add_argument("--hours", type=int, default=24)

    # add-to-backlog
    p_add = sub.add_parser("add-to-backlog", help="Add single post to backlog")
    p_add.add_argument("--platform", required=True)
    p_add.add_argument("--type", required=True, dest="content_type")
    p_add.add_argument("--text", required=True)
    p_add.add_argument("--priority", type=int, default=5)
    p_add.add_argument("--content-mix", default=None)

    # add-thread
    p_thread = sub.add_parser("add-thread", help="Add thread to backlog")
    p_thread.add_argument("--platform", required=True)
    p_thread.add_argument("--type", default="thread", dest="content_type")
    p_thread.add_argument("--texts", required=True, help="JSON array of strings")
    p_thread.add_argument("--priority", type=int, default=5)
    p_thread.add_argument("--content-mix", default=None)

    # backlog-status
    sub.add_parser("backlog-status", help="Current backlog health")

    # mark-processed
    p_mark = sub.add_parser("mark-processed", help="Mark blog post as processed")
    p_mark.add_argument("--slug", required=True)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "scan-blog":
            cmd_scan_blog()
        elif args.command == "scan-commits":
            cmd_scan_commits(days=args.days)
        elif args.command == "scan-sessions":
            cmd_scan_sessions(hours=args.hours)
        elif args.command == "add-to-backlog":
            cmd_add_to_backlog(
                platform=args.platform,
                content_type=args.content_type,
                text=args.text,
                priority=args.priority,
                content_mix=args.content_mix,
            )
        elif args.command == "add-thread":
            try:
                texts = json.loads(args.texts)
            except json.JSONDecodeError:
                _err("--texts must be valid JSON array")
            cmd_add_thread(
                platform=args.platform,
                texts=texts,
                content_type=args.content_type,
                priority=args.priority,
                content_mix=args.content_mix,
            )
        elif args.command == "backlog-status":
            cmd_backlog_status()
        elif args.command == "mark-processed":
            cmd_mark_processed(slug=args.slug)
    except Exception as exc:
        _err(str(exc))


if __name__ == "__main__":
    main()
