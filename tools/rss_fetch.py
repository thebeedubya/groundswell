#!/usr/bin/env python3
"""
Groundswell RSS Fetcher — pure Python, zero Claude cost.

Fetches RSS/Atom feeds defined in config/rss_feeds.yaml, deduplicates by URL,
and writes new items to the rss_items table in SQLite.

Usage:
    python3 tools/rss_fetch.py fetch          # Fetch all enabled feeds
    python3 tools/rss_fetch.py fetch --category cannabis   # Fetch only cannabis feeds
    python3 tools/rss_fetch.py fetch --category tech_ai    # Fetch only tech/AI feeds
    python3 tools/rss_fetch.py status         # Show fetch stats
    python3 tools/rss_fetch.py unscored       # List unscored items (for scouts)
    python3 tools/rss_fetch.py unscored --category cannabis --limit 20
"""

import argparse
import json
import os
import sqlite3
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.request import urlopen, Request
from urllib.error import URLError

try:
    import yaml as _yaml
except ImportError:
    _yaml = None

from _common import (
    DB_PATH as DEFAULT_DB_PATH,
    REPO_ROOT,
    emit,
    fail,
    now_iso,
    get_db,
    rows_to_list,
)

FEEDS_PATH = os.path.join(REPO_ROOT, "config", "rss_feeds.yaml")
USER_AGENT = "Groundswell/1.0 (RSS Fetcher)"
FETCH_TIMEOUT = 15  # seconds per feed


# ---------------------------------------------------------------------------
# Feed loading
# ---------------------------------------------------------------------------

def load_feeds(category=None):
    """Load feed definitions from config/rss_feeds.yaml."""
    if _yaml is None:
        fail("PyYAML is required: pip install pyyaml")
    try:
        with open(FEEDS_PATH, "r") as f:
            data = _yaml.safe_load(f)
    except FileNotFoundError:
        fail(f"Feed config not found: {FEEDS_PATH}")
    except _yaml.YAMLError as exc:
        fail(f"Invalid feed config: {exc}")

    feeds = []
    for cat, items in data.items():
        if category and cat != category:
            continue
        for item in items:
            item["category"] = cat
            feeds.append(item)
    return feeds


# ---------------------------------------------------------------------------
# RSS/Atom parsing
# ---------------------------------------------------------------------------

def parse_feed(xml_text, feed_name, feed_category):
    """Parse RSS or Atom XML into a list of item dicts."""
    items = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items

    ns = {"atom": "http://www.w3.org/2005/Atom"}

    # Try Atom format first
    atom_entries = root.findall("atom:entry", ns) or root.findall("{http://www.w3.org/2005/Atom}entry")
    if atom_entries:
        for entry in atom_entries:
            title_el = entry.find("{http://www.w3.org/2005/Atom}title")
            link_el = entry.find("{http://www.w3.org/2005/Atom}link")
            summary_el = entry.find("{http://www.w3.org/2005/Atom}summary") or entry.find("{http://www.w3.org/2005/Atom}content")
            published_el = entry.find("{http://www.w3.org/2005/Atom}published") or entry.find("{http://www.w3.org/2005/Atom}updated")

            title = title_el.text.strip() if title_el is not None and title_el.text else None
            url = link_el.get("href") if link_el is not None else None
            summary = summary_el.text.strip()[:500] if summary_el is not None and summary_el.text else None
            published = published_el.text.strip() if published_el is not None and published_el.text else None

            if title and url:
                items.append({
                    "feed_name": feed_name,
                    "feed_category": feed_category,
                    "title": title,
                    "url": url,
                    "summary": summary,
                    "published_at": _normalize_date(published),
                })
        return items

    # Try RSS 2.0 format
    for channel in root.iter("channel"):
        for item_el in channel.findall("item"):
            title_el = item_el.find("title")
            link_el = item_el.find("link")
            desc_el = item_el.find("description")
            pub_el = item_el.find("pubDate")

            title = title_el.text.strip() if title_el is not None and title_el.text else None
            url = link_el.text.strip() if link_el is not None and link_el.text else None
            summary = desc_el.text.strip()[:500] if desc_el is not None and desc_el.text else None
            published = pub_el.text.strip() if pub_el is not None and pub_el.text else None

            if title and url:
                items.append({
                    "feed_name": feed_name,
                    "feed_category": feed_category,
                    "title": title,
                    "url": url,
                    "summary": summary,
                    "published_at": _normalize_date(published),
                })

    # Try RDF/RSS 1.0 format
    if not items:
        rdf_ns = "http://purl.org/rss/1.0/"
        for item_el in root.findall(f"{{{rdf_ns}}}item"):
            title_el = item_el.find(f"{{{rdf_ns}}}title")
            link_el = item_el.find(f"{{{rdf_ns}}}link")
            desc_el = item_el.find(f"{{{rdf_ns}}}description")

            title = title_el.text.strip() if title_el is not None and title_el.text else None
            url = link_el.text.strip() if link_el is not None and link_el.text else None
            summary = desc_el.text.strip()[:500] if desc_el is not None and desc_el.text else None

            if title and url:
                items.append({
                    "feed_name": feed_name,
                    "feed_category": feed_category,
                    "title": title,
                    "url": url,
                    "summary": summary,
                    "published_at": None,
                })

    return items


def _normalize_date(date_str):
    """Best-effort parse of date strings to ISO format."""
    if not date_str:
        return None
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.isoformat().replace("+00:00", "Z")
    except Exception:
        pass
    # Try ISO format directly
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.isoformat().replace("+00:00", "Z")
    except Exception:
        return date_str


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def fetch_feed_xml(url):
    """Fetch raw XML from a feed URL."""
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (URLError, OSError) as e:
        return None


def store_items(conn, items):
    """Insert new items, skip duplicates by URL. Returns count of new items."""
    new_count = 0
    ts = now_iso()
    for item in items:
        try:
            conn.execute(
                "INSERT INTO rss_items (feed_name, feed_category, title, url, summary, published_at, fetched_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    item["feed_name"],
                    item["feed_category"],
                    item["title"],
                    item["url"],
                    item.get("summary"),
                    item.get("published_at"),
                    ts,
                ),
            )
            new_count += 1
        except sqlite3.IntegrityError:
            # URL already exists — skip
            pass
    conn.commit()
    return new_count


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_fetch(args):
    feeds = load_feeds(args.category)
    if not feeds:
        fail(f"No feeds found for category: {args.category or 'all'}")

    conn = get_db(args.db)
    conn.execute("PRAGMA foreign_keys=ON")

    total_new = 0
    total_fetched = 0
    errors = []

    for feed in feeds:
        xml_text = fetch_feed_xml(feed["url"])
        if xml_text is None:
            errors.append({"feed": feed["name"], "error": "fetch failed"})
            continue

        items = parse_feed(xml_text, feed["name"], feed["category"])
        total_fetched += len(items)
        new = store_items(conn, items)
        total_new += new

    conn.close()
    emit({
        "ok": True,
        "feeds_checked": len(feeds),
        "items_fetched": total_fetched,
        "new_items": total_new,
        "errors": errors,
        "timestamp": now_iso(),
    })


def cmd_status(args):
    conn = get_db(args.db)
    conn.execute("PRAGMA foreign_keys=ON")

    total = conn.execute("SELECT COUNT(*) as cnt FROM rss_items").fetchone()["cnt"]
    unscored = conn.execute("SELECT COUNT(*) as cnt FROM rss_items WHERE scored = 0").fetchone()["cnt"]
    by_category = rows_to_list(conn.execute(
        "SELECT feed_category, COUNT(*) as cnt, SUM(CASE WHEN scored = 0 THEN 1 ELSE 0 END) as unscored "
        "FROM rss_items GROUP BY feed_category"
    ).fetchall())
    latest = conn.execute(
        "SELECT feed_name, fetched_at FROM rss_items ORDER BY fetched_at DESC LIMIT 1"
    ).fetchone()

    conn.close()
    emit({
        "total_items": total,
        "unscored_items": unscored,
        "by_category": by_category,
        "latest_fetch": dict(latest) if latest else None,
    })


def cmd_unscored(args):
    conn = get_db(args.db)
    conn.execute("PRAGMA foreign_keys=ON")

    limit = args.limit or 30
    if args.category:
        rows = conn.execute(
            "SELECT * FROM rss_items WHERE scored = 0 AND feed_category = ? ORDER BY fetched_at DESC LIMIT ?",
            (args.category, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM rss_items WHERE scored = 0 ORDER BY fetched_at DESC LIMIT ?",
            (limit,),
        ).fetchall()

    conn.close()
    emit({"items": rows_to_list(rows), "count": len(rows)})


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(description="Groundswell RSS Fetcher")
    parser.add_argument("--db", default=None, help="Override database path")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("fetch", help="Fetch RSS feeds and store new items")
    p.add_argument("--category", default=None, help="Filter by category (cannabis, tech_ai)")

    sub.add_parser("status", help="Show RSS fetch statistics")

    p = sub.add_parser("unscored", help="List unscored RSS items for scouts")
    p.add_argument("--category", default=None, help="Filter by category")
    p.add_argument("--limit", type=int, default=30)

    return parser


COMMANDS = {
    "fetch": cmd_fetch,
    "status": cmd_status,
    "unscored": cmd_unscored,
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
