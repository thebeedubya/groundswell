#!/usr/bin/env python3
"""
Groundswell X (Twitter) API Tool — Search, mentions, metrics, and user data.

Uses OAuth 1.0a with credentials from environment or ~/.zsh_env.

Usage:
    python3 tools/x_api.py search --query "AI agents" [--count 20]
    python3 tools/x_api.py mentions [--since-id ID]
    python3 tools/x_api.py metrics [--handle @dbaborneforreal]
    python3 tools/x_api.py user --handle @kimrivers
    python3 tools/x_api.py tweet --id 12345
    python3 tools/x_api.py followers [--handle @dbaborneforreal]
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from _x_auth import (
    BRAD_USER_ID,
    REQUIRED_CREDS,
    load_env,
    _build_auth_header,
    _api_error,
)


# ---------------------------------------------------------------------------
# Credential helpers
# ---------------------------------------------------------------------------

def require_creds():
    env = load_env()
    missing = [k for k in REQUIRED_CREDS if not env.get(k)]
    if missing:
        print(f"Missing credentials: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)
    return env


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def emit(data):
    json.dump(data, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    sys.exit(0)


def _get(env, url, query_params):
    """Make an authenticated GET request to the X API v2."""
    auth_header = _build_auth_header(
        "GET", url, query_params,
        env["X_API_KEY"], env["X_API_SECRET"],
        env["X_ACCESS_TOKEN"], env["X_ACCESS_TOKEN_SECRET"],
    )
    qs = urllib.parse.urlencode(query_params)
    full_url = f"{url}?{qs}" if qs else url

    req = urllib.request.Request(full_url, method="GET")
    req.add_header("Authorization", auth_header)

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {"ok": True, "data": data}
    except urllib.error.HTTPError as e:
        return _api_error(e)


def _lookup_user_id(env, handle):
    """Look up a user ID by handle. Returns (user_id, error_response)."""
    handle = handle.lstrip("@")
    url = f"https://api.x.com/2/users/by/username/{handle}"
    result = _get(env, url, {})
    if not result.get("ok"):
        return None, result
    user_id = result["data"].get("data", {}).get("id")
    if not user_id:
        return None, {"ok": False, "error": "user_not_found", "detail": f"@{handle} not found"}
    return user_id, None


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------

def cmd_search(args):
    env = require_creds()
    url = "https://api.x.com/2/tweets/search/recent"
    count = min(max(args.count, 10), 100)
    query_params = {
        "query": args.query,
        "max_results": str(count),
        "tweet.fields": "created_at,public_metrics,author_id",
        "expansions": "author_id",
        "user.fields": "username,name,public_metrics",
    }
    result = _get(env, url, query_params)
    emit(result)


def cmd_mentions(args):
    env = require_creds()
    url = f"https://api.x.com/2/users/{BRAD_USER_ID}/mentions"
    query_params = {
        "tweet.fields": "created_at,public_metrics,conversation_id",
        "expansions": "author_id",
        "user.fields": "username,name,public_metrics",
    }
    if args.since_id:
        query_params["since_id"] = args.since_id
    result = _get(env, url, query_params)
    emit(result)


def cmd_metrics(args):
    env = require_creds()
    handle = args.handle.lstrip("@")
    url = f"https://api.x.com/2/users/by/username/{handle}"
    query_params = {
        "user.fields": "public_metrics,description,created_at",
    }
    result = _get(env, url, query_params)
    emit(result)


def cmd_user(args):
    env = require_creds()
    handle = args.handle.lstrip("@")
    url = f"https://api.x.com/2/users/by/username/{handle}"
    query_params = {
        "user.fields": "public_metrics,description,created_at",
    }
    result = _get(env, url, query_params)
    emit(result)


def cmd_tweet(args):
    env = require_creds()
    url = f"https://api.x.com/2/tweets/{args.id}"
    query_params = {
        "tweet.fields": "created_at,public_metrics,conversation_id",
        "expansions": "author_id",
        "user.fields": "username,name",
    }
    result = _get(env, url, query_params)
    emit(result)


def cmd_followers(args):
    env = require_creds()
    handle = args.handle.lstrip("@")

    # Determine if this is Brad's handle or someone else's
    # For Brad's account, use the known ID directly
    if handle.lower() == "dbaborneforreal":
        user_id = BRAD_USER_ID
    else:
        # Look up user ID first
        user_id, err = _lookup_user_id(env, handle)
        if err:
            emit(err)
        time.sleep(1)  # rate limit courtesy between API calls

    url = f"https://api.x.com/2/users/{user_id}/followers"
    query_params = {
        "max_results": "100",
        "user.fields": "username,name,public_metrics,description",
    }
    result = _get(env, url, query_params)
    emit(result)


# ---------------------------------------------------------------------------
# CLI parser
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        description="Groundswell X (Twitter) API Tool — Search, mentions, metrics, and user data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    # search
    p = sub.add_parser("search", help="Search recent tweets")
    p.add_argument("--query", required=True, help="Search query string")
    p.add_argument("--count", type=int, default=20, help="Number of results (default: 20, max: 100)")

    # mentions
    p = sub.add_parser("mentions", help="Get recent mentions of Brad's account")
    p.add_argument("--since-id", default=None, help="Only return mentions after this tweet ID")

    # metrics
    p = sub.add_parser("metrics", help="Get account metrics for a handle")
    p.add_argument("--handle", default="@dbaborneforreal", help="Twitter handle (default: @dbaborneforreal)")

    # user
    p = sub.add_parser("user", help="Look up user profile by handle")
    p.add_argument("--handle", required=True, help="Twitter handle (e.g. @kimrivers)")

    # tweet
    p = sub.add_parser("tweet", help="Look up a specific tweet by ID")
    p.add_argument("--id", required=True, help="Tweet ID to look up")

    # followers
    p = sub.add_parser("followers", help="Get followers for a handle")
    p.add_argument("--handle", default="@dbaborneforreal", help="Twitter handle (default: @dbaborneforreal)")

    return parser


COMMANDS = {
    "search": cmd_search,
    "mentions": cmd_mentions,
    "metrics": cmd_metrics,
    "user": cmd_user,
    "tweet": cmd_tweet,
    "followers": cmd_followers,
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
