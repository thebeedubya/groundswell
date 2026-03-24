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
import subprocess
import sys
import time


GRAPH_URL = "https://graph.threads.net/v1.0"


def emit(data):
    json.dump(data, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    sys.exit(0)


def get_credentials():
    token = os.environ.get("THREADS_BRAD_ACCESS_TOKEN") or os.environ.get("THREADS_ACCESS_TOKEN")
    user_id = os.environ.get("THREADS_BRAD_USER_ID") or os.environ.get("THREADS_USER_ID")
    return token, user_id


def is_configured():
    token, user_id = get_credentials()
    return bool(token and user_id)


def stub_response(message):
    emit({"ok": False, "error": "not_configured", "message": message})


def _curl_post(url, data_pairs):
    """Make a POST request via curl with --data-urlencode pairs."""
    cmd = ["curl", "-s", "-X", "POST", url]
    for k, v in data_pairs:
        cmd.extend(["--data-urlencode", f"{k}={v}"])
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"error": {"message": f"Non-JSON response: {result.stdout[:200]}", "code": -1}}


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def cmd_post(args):
    text = args.text
    if not text:
        emit({"ok": False, "error": "missing_text", "message": "--text is required"})

    if not is_configured():
        print(f"[dry_run] Would post to Threads: {text[:100]}...", file=sys.stderr)
        emit({
            "ok": True,
            "dry_run": True,
            "platform": "threads",
            "text": text,
            "post_id": None,
            "message": "Dry run — set THREADS_BRAD_ACCESS_TOKEN and THREADS_BRAD_USER_ID to post for real",
        })
        return

    token, user_id = get_credentials()

    # Step 1: Create media container
    container_resp = _curl_post(
        f"{GRAPH_URL}/{user_id}/threads",
        [("media_type", "TEXT"), ("text", text), ("access_token", token)],
    )

    if "error" in container_resp:
        err = container_resp["error"]
        emit({
            "ok": False,
            "error": "container_creation_failed",
            "api_error": err.get("message", str(err)),
            "api_code": err.get("code", -1),
        })
        return

    container_id = container_resp.get("id")
    if not container_id:
        emit({"ok": False, "error": "no_container_id", "response": container_resp})
        return

    # Step 2: Wait then publish
    time.sleep(3)

    publish_resp = _curl_post(
        f"{GRAPH_URL}/{user_id}/threads_publish",
        [("creation_id", container_id), ("access_token", token)],
    )

    if "error" in publish_resp:
        err = publish_resp["error"]
        emit({
            "ok": False,
            "error": "publish_failed",
            "container_id": container_id,
            "api_error": err.get("message", str(err)),
            "api_code": err.get("code", -1),
        })
        return

    post_id = publish_resp.get("id")
    emit({
        "ok": True,
        "dry_run": False,
        "platform": "threads",
        "text": text,
        "post_id": post_id,
        "container_id": container_id,
        "message": f"Posted to Threads: {post_id}",
    })


def cmd_reply(args):
    parent_id = args.post_id
    text = args.text

    if not text:
        emit({"ok": False, "error": "missing_text", "message": "--text is required"})

    if not is_configured():
        print(f"[dry_run] Would reply to Threads post {parent_id}: {text[:80]}...", file=sys.stderr)
        emit({
            "ok": True,
            "dry_run": True,
            "platform": "threads",
            "parent_post_id": parent_id,
            "text": text,
            "reply_id": None,
            "message": "Dry run — set THREADS_BRAD_ACCESS_TOKEN and THREADS_BRAD_USER_ID to reply for real",
        })
        return

    token, user_id = get_credentials()

    # Step 1: Create reply container
    container_resp = _curl_post(
        f"{GRAPH_URL}/{user_id}/threads",
        [
            ("media_type", "TEXT"),
            ("text", text),
            ("reply_to_id", parent_id),
            ("access_token", token),
        ],
    )

    if "error" in container_resp:
        err = container_resp["error"]
        emit({
            "ok": False,
            "error": "reply_container_failed",
            "api_error": err.get("message", str(err)),
            "api_code": err.get("code", -1),
        })
        return

    container_id = container_resp.get("id")
    if not container_id:
        emit({"ok": False, "error": "no_container_id", "response": container_resp})
        return

    # Step 2: Wait then publish
    time.sleep(3)

    publish_resp = _curl_post(
        f"{GRAPH_URL}/{user_id}/threads_publish",
        [("creation_id", container_id), ("access_token", token)],
    )

    if "error" in publish_resp:
        err = publish_resp["error"]
        emit({
            "ok": False,
            "error": "reply_publish_failed",
            "container_id": container_id,
            "api_error": err.get("message", str(err)),
            "api_code": err.get("code", -1),
        })
        return

    reply_id = publish_resp.get("id")
    emit({
        "ok": True,
        "dry_run": False,
        "platform": "threads",
        "parent_post_id": parent_id,
        "text": text,
        "reply_id": reply_id,
        "container_id": container_id,
        "message": f"Replied on Threads: {reply_id}",
    })


def cmd_mentions(args):
    if not is_configured():
        emit({
            "ok": True,
            "dry_run": True,
            "platform": "threads",
            "mentions": [],
            "count": 0,
            "message": "Dry run — set THREADS_BRAD_ACCESS_TOKEN for live mentions",
        })
        return

    token, user_id = get_credentials()

    # Fetch recent threads (own posts + replies to them)
    cmd = [
        "curl", "-s",
        f"{GRAPH_URL}/{user_id}/threads?fields=id,text,timestamp,username&access_token={token}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        emit({"ok": False, "error": "parse_error", "message": result.stdout[:200]})
        return

    if "error" in data:
        err = data["error"]
        emit({
            "ok": False,
            "error": "mentions_fetch_failed",
            "api_error": err.get("message", str(err)),
            "api_code": err.get("code", -1),
        })
        return

    threads_list = data.get("data", [])
    emit({
        "ok": True,
        "dry_run": False,
        "platform": "threads",
        "threads": threads_list,
        "count": len(threads_list),
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
