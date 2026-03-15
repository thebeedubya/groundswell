"""
Shared X (Twitter) OAuth 1.0a authentication and credential loading.

Extracted from tools/post.py and tools/x_api.py to eliminate duplication.
Also used by tools/telegram.py for load_env().
"""

import base64
import hashlib
import hmac
import os
import time
import urllib.parse
import uuid


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BRAD_USER_ID = "1072871854195515392"

REQUIRED_CREDS = [
    "X_API_KEY",
    "X_API_SECRET",
    "X_ACCESS_TOKEN",
    "X_ACCESS_TOKEN_SECRET",
]

ALL_CREDS = REQUIRED_CREDS + [
    "X_BEARER_TOKEN",
    "LINKEDIN_ACCESS_TOKEN",
    "LINKEDIN_PERSON_ID",
]


# ---------------------------------------------------------------------------
# Credential loading
# ---------------------------------------------------------------------------

def load_env(keys=None):
    """Parse ~/.zsh_env and overlay env vars for the given key names.

    Args:
        keys: list of env-var names to extract.  Defaults to ALL_CREDS.
    """
    if keys is None:
        keys = ALL_CREDS

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
    for key in keys:
        env[key] = os.environ.get(key, env.get(key, ""))
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
# HTTP error parser
# ---------------------------------------------------------------------------

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
