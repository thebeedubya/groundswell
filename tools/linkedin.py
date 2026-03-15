#!/usr/bin/env python3
"""
Groundswell LinkedIn API Tool — Post, comment, and get metrics.

Requires LINKEDIN_ACCESS_TOKEN environment variable for live API calls.
Returns dry_run data when not configured.

Usage:
    python3 tools/linkedin.py post --text "..."
    python3 tools/linkedin.py comment --post-id X --text "..."
    python3 tools/linkedin.py metrics
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
    return bool(os.environ.get("LINKEDIN_ACCESS_TOKEN"))


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
        stub_response("LinkedIn post API not yet implemented. Token is configured but code is pending.")

    print(f"[dry_run] Would post to LinkedIn: {text[:100]}...", file=sys.stderr)
    emit({
        "ok": True,
        "dry_run": True,
        "platform": "linkedin",
        "text": text,
        "post_id": None,
        "word_count": len(text.split()),
        "message": "Dry run — set LINKEDIN_ACCESS_TOKEN to post for real",
    })


def cmd_comment(args):
    post_id = args.post_id
    text = args.text

    if not text:
        emit({"ok": False, "error": "missing_text", "message": "--text is required"})

    if is_configured():
        stub_response("LinkedIn comment API not yet implemented. Token is configured but code is pending.")

    print(f"[dry_run] Would comment on LinkedIn post {post_id}: {text[:80]}...", file=sys.stderr)
    emit({
        "ok": True,
        "dry_run": True,
        "platform": "linkedin",
        "post_id": post_id,
        "comment_text": text,
        "comment_id": None,
        "message": "Dry run — set LINKEDIN_ACCESS_TOKEN to comment for real",
    })


def cmd_metrics(args):
    if is_configured():
        stub_response("LinkedIn metrics API not yet implemented. Token is configured but code is pending.")

    emit({
        "ok": True,
        "dry_run": True,
        "platform": "linkedin",
        "metrics": {
            "followers_count": None,
            "connections_count": None,
            "posts_last_30d": None,
            "impressions_last_30d": None,
            "engagement_rate": None,
        },
        "message": "Dry run — set LINKEDIN_ACCESS_TOKEN for live metrics",
    })


# ---------------------------------------------------------------------------
# CLI parser
# ---------------------------------------------------------------------------


def build_parser():
    parser = argparse.ArgumentParser(
        description="Groundswell LinkedIn API Tool — Post, comment, and get metrics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    # post
    p = sub.add_parser("post", help="Publish a post to LinkedIn")
    p.add_argument("--text", required=True, help="Post text content")

    # comment
    p = sub.add_parser("comment", help="Comment on a LinkedIn post")
    p.add_argument("--post-id", required=True, help="LinkedIn post ID to comment on")
    p.add_argument("--text", required=True, help="Comment text")

    # metrics
    sub.add_parser("metrics", help="Get LinkedIn account metrics")

    return parser


COMMANDS = {
    "post": cmd_post,
    "comment": cmd_comment,
    "metrics": cmd_metrics,
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
