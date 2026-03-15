#!/usr/bin/env python3
"""
Groundswell Threads API Tool — Post, reply, and get mentions.

Requires THREADS_ACCESS_TOKEN environment variable for live API calls.
Returns dry_run data when not configured.

Usage:
    python3 tools/threads.py post --text "..."
    python3 tools/threads.py reply --post-id X --text "..."
    python3 tools/threads.py mentions
"""

import argparse
import json
import os
import sys


def emit(data):
    json.dump(data, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    sys.exit(0)


def is_configured():
    return bool(os.environ.get("THREADS_ACCESS_TOKEN"))


def stub_response(message):
    emit({"ok": False, "error": "not_configured", "message": message})


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def cmd_post(args):
    text = args.text
    if not text:
        emit({"ok": False, "error": "missing_text", "message": "--text is required"})

    if is_configured():
        stub_response("Threads post API not yet implemented. Token is configured but code is pending.")

    print(f"[dry_run] Would post to Threads: {text[:100]}...", file=sys.stderr)
    emit({
        "ok": True,
        "dry_run": True,
        "platform": "threads",
        "text": text,
        "post_id": None,
        "message": "Dry run — set THREADS_ACCESS_TOKEN to post for real",
    })


def cmd_reply(args):
    post_id = args.post_id
    text = args.text

    if not text:
        emit({"ok": False, "error": "missing_text", "message": "--text is required"})

    if is_configured():
        stub_response("Threads reply API not yet implemented. Token is configured but code is pending.")

    print(f"[dry_run] Would reply to Threads post {post_id}: {text[:80]}...", file=sys.stderr)
    emit({
        "ok": True,
        "dry_run": True,
        "platform": "threads",
        "parent_post_id": post_id,
        "text": text,
        "reply_id": None,
        "message": "Dry run — set THREADS_ACCESS_TOKEN to reply for real",
    })


def cmd_mentions(args):
    if is_configured():
        stub_response("Threads mentions API not yet implemented. Token is configured but code is pending.")

    emit({
        "ok": True,
        "dry_run": True,
        "platform": "threads",
        "mentions": [],
        "count": 0,
        "message": "Dry run — set THREADS_ACCESS_TOKEN for live mentions",
    })


# ---------------------------------------------------------------------------
# CLI parser
# ---------------------------------------------------------------------------


def build_parser():
    parser = argparse.ArgumentParser(
        description="Groundswell Threads API Tool — Post, reply, and get mentions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    # post
    p = sub.add_parser("post", help="Publish a post to Threads")
    p.add_argument("--text", required=True, help="Post text content")

    # reply
    p = sub.add_parser("reply", help="Reply to a Threads post")
    p.add_argument("--post-id", required=True, help="Threads post ID to reply to")
    p.add_argument("--text", required=True, help="Reply text")

    # mentions
    sub.add_parser("mentions", help="Get recent mentions on Threads")

    return parser


COMMANDS = {
    "post": cmd_post,
    "reply": cmd_reply,
    "mentions": cmd_mentions,
}


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help(sys.stderr)
        sys.exit(1)

    handler = COMMANDS.get(args.command)
    if not handler:
        emit({"ok": False, "error": "unknown_command", "message": f"Unknown command: {args.command}"})

    try:
        handler(args)
    except Exception as e:
        emit({"ok": False, "error": "exception", "message": str(e)})


if __name__ == "__main__":
    main()
