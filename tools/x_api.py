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
import base64
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import uuid

BRAD_USER_ID = "1072871854195515392"

# ---------------------------------------------------------------------------
# Credential loading
# ---------------------------------------------------------------------------

REQUIRED_CREDS = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"]
ALL_CREDS = REQUIRED_CREDS + ["X_BEARER_TOKEN"]


def load_env():
    env = {}
    zsh_env = os.path.expanduser("~/.zsh_env")
    if os.path.exists(zsh_env):
        with open(zsh_env) as f:
            for line in f:
                line = line.strip()
                if line.startswith("export ") and "=" in line:
                    key, _, val = line[7:].partition("=")
                    val = val.strip("'\"")
                    env[key] = val
    for key in ALL_CREDS:
        env[key] = os.environ.get(key, env.get(key, ""))
    return env


def require_creds():
    env = load_env()
    missing = [k for k in REQUIRED_CREDS if not env.get(k)]
    if missing:
        print(f"Missing credentials: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)
    return env


# ---------------------------------------------------------------------------
# OAuth 1.0a
# ---------------------------------------------------------------------------

def _x_oauth_signature(method, url, params, consumer_secret, token_secret):
    sorted_params = "&".join(
        f"{urllib.parse.quote(k, safe='')}" + "=" + f"{urllib.parse.quote(v, safe='')}"
        for k, v in sorted(params.items())
    )
    base_string = "&".join(
        urllib.parse.quote(s, safe="")
        for s in [method.upper(), url, sorted_params]
    )
    signing_key = (
        f"{urllib.parse.quote(consumer_secret, safe='')}"
        + "&"
        + f"{urllib.parse.quote(token_secret, safe='')}"
    )
    signature = hmac.new(
        signing_key.encode("utf-8"),
        base_string.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    return base64.b64encode(signature).decode("utf-8")


def _build_auth_header(method, url, query_params, api_key, api_secret, access_token, access_token_secret):
    oauth_params = {
        "oauth_consumer_key": api_key,
        "oauth_nonce": uuid.uuid4().hex,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": access_token,
        "oauth_version": "1.0",
    }
    sig_params = {**oauth_params, **query_params}
    signature = _x_oauth_signature(method, url, sig_params, api_secret, access_token_secret)
    oauth_params["oauth_signature"] = signature
    return "OAuth " + ", ".join(
        f'{urllib.parse.quote(k, safe="")}="{urllib.parse.quote(v, safe="")}"'
        for k, v in sorted(oauth_params.items())
    )


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def emit(data):
    json.dump(data, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    sys.exit(0)


def _api_error(e):
    """Parse an HTTP error into a structured response."""
    status = e.code
    try:
        body = e.read().decode("utf-8")
    except Exception:
        body = str(e)
    if status == 429:
        retry_after = e.headers.get("retry-after", "60")
        return {"ok": False, "error": "rate_limited", "retry_after": int(retry_after)}
    elif status == 401:
        return {"ok": False, "error": "auth_expired"}
    elif status == 403:
        return {"ok": False, "error": "forbidden", "detail": body}
    else:
        return {"ok": False, "error": status, "detail": body}


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
