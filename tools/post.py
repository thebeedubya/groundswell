#!/usr/bin/env python3
"""
Groundswell Post Tool — Publish content to social platforms.

Supports X (Twitter) with real API, LinkedIn and Threads as stubs.

Usage:
    python3 tools/post.py x --text "..." [--reply-to ID] [--quote-tweet-id ID] [--image PATH]
    python3 tools/post.py verify --platform x --id 12345
    python3 tools/post.py linkedin --text "..."
    python3 tools/post.py threads --text "..."
"""

import argparse
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request

from _common import DB_PATH, now_iso

from _x_auth import (
    REQUIRED_CREDS,
    load_env,
    _build_auth_header,
    _api_error,
)


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def emit(data):
    json.dump(data, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    sys.exit(0)


def _log_api_call(platform, call_type, endpoint):
    """Log an API call to the api_usage table."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO api_usage (platform, call_type, endpoint, created_at) VALUES (?, ?, ?, ?)",
            (platform, call_type, endpoint, now_iso()),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # Don't let logging failures break API calls


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------

def cmd_x(args):
    text = args.text
    if not text:
        emit({"ok": False, "error": "missing_text", "message": "--text is required"})

    env = load_env()
    missing = [k for k in REQUIRED_CREDS if not env.get(k)]
    if missing:
        print(f"Missing credentials: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    if args.image:
        print("[stub] Image upload not yet implemented — posting text only", file=sys.stderr)

    # Build JSON body
    body = {"text": text}
    if args.reply_to:
        body["reply"] = {"in_reply_to_tweet_id": args.reply_to}
    if args.quote_tweet_id:
        body["quote_tweet_id"] = args.quote_tweet_id

    url = "https://api.x.com/2/tweets"
    # POST with JSON body: only oauth params in signature (no body params)
    auth_header = _build_auth_header(
        "POST", url, {},
        env["X_API_KEY"], env["X_API_SECRET"],
        env["X_ACCESS_TOKEN"], env["X_ACCESS_TOKEN_SECRET"],
    )

    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Authorization", auth_header)
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            post_id = data.get("data", {}).get("id")
            _log_api_call("x", "write", "/2/tweets")
            emit({
                "ok": True,
                "platform": "x",
                "post_id": post_id,
                "text": text,
            })
    except urllib.error.HTTPError as e:
        err = _api_error(e)
        if err.get("error") == "forbidden":
            err["text"] = text
            err["reply_to"] = args.reply_to
            err["quote_tweet_id"] = args.quote_tweet_id
        emit(err)


def cmd_verify(args):
    platform = args.platform
    post_id = args.id

    if platform != "x":
        emit({
            "ok": True,
            "dry_run": True,
            "platform": platform,
            "post_id": post_id,
            "verified": None,
            "message": f"Verification for {platform} not yet implemented",
        })
        return

    env = load_env()
    missing = [k for k in REQUIRED_CREDS if not env.get(k)]
    if missing:
        print(f"Missing credentials: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    url = f"https://api.x.com/2/tweets/{post_id}"
    query_params = {"tweet.fields": "public_metrics"}
    qs = urllib.parse.urlencode(query_params)
    full_url = f"{url}?{qs}"

    auth_header = _build_auth_header(
        "GET", url, query_params,
        env["X_API_KEY"], env["X_API_SECRET"],
        env["X_ACCESS_TOKEN"], env["X_ACCESS_TOKEN_SECRET"],
    )

    req = urllib.request.Request(full_url, method="GET")
    req.add_header("Authorization", auth_header)

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            tweet_data = data.get("data", {})
            metrics = tweet_data.get("public_metrics", {})
            emit({
                "ok": True,
                "verified": True,
                "platform": "x",
                "post_id": post_id,
                "metrics": metrics,
            })
    except urllib.error.HTTPError as e:
        if e.code == 404:
            emit({"ok": True, "verified": False, "platform": "x", "post_id": post_id})
        else:
            emit(_api_error(e))


def post_to_linkedin(text, person_id, access_token):
    """Post to LinkedIn via the Posts API. Pure stdlib."""
    url = "https://api.linkedin.com/rest/posts"
    payload = {
        "author": person_id,
        "commentary": text,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "LinkedIn-Version": "202602",
            "X-Restli-Protocol-Version": "2.0.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            _log_api_call("linkedin", "write", "/rest/posts")
            return {
                "ok": True,
                "platform": "linkedin",
                "status": resp.status,
                "post_id": resp.headers.get("x-restli-id", "unknown"),
            }
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {"ok": False, "platform": "linkedin", "error": e.code, "detail": body}


def cmd_linkedin(args):
    text = args.text
    if not text:
        emit({"ok": False, "error": "missing_text", "message": "--text is required"})
        return

    env = load_env()
    token = env.get("LINKEDIN_ACCESS_TOKEN", "")
    person_id = env.get("LINKEDIN_PERSON_ID", "")

    if not token or not person_id:
        emit({
            "ok": False,
            "error": "missing_credentials",
            "message": "Set LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_ID in ~/.zsh_env",
        })
        return

    result = post_to_linkedin(text, person_id, token)
    emit(result)


def cmd_threads(args):
    text = args.text
    if not text:
        emit({"ok": False, "error": "missing_text", "message": "--text is required"})

    emit({
        "ok": True,
        "dry_run": True,
        "platform": "threads",
        "text": text,
        "post_id": None,
        "message": "Threads posting not yet implemented",
    })


# ---------------------------------------------------------------------------
# CLI parser
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        description="Groundswell Post Tool — Publish content to social platforms",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    # x
    p = sub.add_parser("x", help="Post to X (Twitter)")
    p.add_argument("--text", required=True, help="Text content to post")
    p.add_argument("--reply-to", default=None, help="Tweet ID to reply to")
    p.add_argument("--quote-tweet-id", default=None, help="Tweet ID to quote")
    p.add_argument("--image", default=None, help="Path to image to attach (stub)")

    # linkedin
    p = sub.add_parser("linkedin", help="Post to LinkedIn")
    p.add_argument("--text", required=True, help="Text content to post")
    p.add_argument("--image", default=None, help="Path to image to attach")

    # threads
    p = sub.add_parser("threads", help="Post to Threads")
    p.add_argument("--text", required=True, help="Text content to post")
    p.add_argument("--image", default=None, help="Path to image to attach")

    # verify
    p = sub.add_parser("verify", help="Verify a post was published successfully")
    p.add_argument("--platform", required=True, choices=["x", "linkedin", "threads"], help="Platform to verify on")
    p.add_argument("--id", required=True, help="Post ID to verify")

    return parser


COMMANDS = {
    "x": cmd_x,
    "linkedin": cmd_linkedin,
    "threads": cmd_threads,
    "verify": cmd_verify,
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
