#!/usr/bin/env python3
"""
Threads OAuth Helper — handles the callback, exchanges tokens, saves to env.

Usage:
    1. python3 tools/threads_auth.py serve
       (starts local HTTPS server on port 8443)
    2. Open the auth URL it prints
    3. Authorize in browser
    4. Server catches the callback, exchanges for long-lived token, prints it

    Or manually:
    python3 tools/threads_auth.py exchange --code CODE
"""

import argparse
import json
import os
import ssl
import sys
import urllib.parse
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler

# Your Threads app credentials
APP_ID = os.environ.get("THREADS_APP_ID", "1326461779314589")
APP_SECRET = os.environ.get("THREADS_APP_SECRET", "5ce8622cf031440ef05d6feed82dfc05")
REDIRECT_URI = os.environ.get("THREADS_REDIRECT_URI", "https://localhost:8443/callback")

GRAPH_URL = "https://graph.threads.net"


def exchange_code_for_token(code):
    """Exchange auth code for short-lived token, then long-lived token."""
    # Step 1: Short-lived token (use curl — Python's urlencode mangles the redirect_uri)
    import subprocess
    curl_result = subprocess.run([
        "curl", "-s", "-X", "POST", f"{GRAPH_URL}/oauth/access_token",
        "--data-urlencode", f"client_id={APP_ID}",
        "--data-urlencode", f"client_secret={APP_SECRET}",
        "--data-urlencode", "grant_type=authorization_code",
        "--data-urlencode", f"redirect_uri={REDIRECT_URI}",
        "--data-urlencode", f"code={code}",
    ], capture_output=True, text=True, timeout=30)

    try:
        short_lived = json.loads(curl_result.stdout)
    except json.JSONDecodeError:
        print(f"ERROR exchanging code: {curl_result.stdout} {curl_result.stderr}", file=sys.stderr)
        return None

    if "error" in short_lived:
        print(f"ERROR exchanging code: {json.dumps(short_lived, indent=2)}", file=sys.stderr)
        return None

    short_token = short_lived.get("access_token")
    user_id = short_lived.get("user_id")
    print(f"\nShort-lived token obtained (user_id: {user_id})")

    # Step 2: Long-lived token
    params = urllib.parse.urlencode({
        "grant_type": "th_exchange_token",
        "client_secret": APP_SECRET,
        "access_token": short_token,
    })
    req = urllib.request.Request(f"{GRAPH_URL}/access_token?{params}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            long_lived = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"ERROR getting long-lived token: {e.code} {body}", file=sys.stderr)
        print(f"Short-lived token (use this if long-lived fails): {short_token}")
        return {"access_token": short_token, "user_id": user_id, "expires_in": 3600}

    long_token = long_lived.get("access_token")
    expires_in = long_lived.get("expires_in", 5184000)

    print(f"\n{'='*60}")
    print(f"SUCCESS! Long-lived token obtained.")
    print(f"Expires in: {expires_in // 86400} days")
    print(f"User ID: {user_id}")
    print(f"{'='*60}")
    print(f"\nAdd these to ~/.zsh_env:")
    print(f'export THREADS_ACCESS_TOKEN="{long_token}"')
    print(f'export THREADS_USER_ID="{user_id}"')
    print(f"{'='*60}\n")

    return {
        "access_token": long_token,
        "user_id": user_id,
        "expires_in": expires_in,
    }


class CallbackHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Quiet

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/callback":
            code = qs.get("code", [None])[0]
            error = qs.get("error", [None])[0]

            if error:
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(f"<h1>Error: {error}</h1><p>{qs.get('error_description', [''])[0]}</p>".encode())
                print(f"\nAuth error: {error} — {qs.get('error_description', [''])[0]}")
                return

            if code:
                # Strip the trailing #_ that Meta adds
                code = code.rstrip("#_").split("#")[0]

                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h1>Got it!</h1><p>Check your terminal for the token. You can close this tab.</p>")

                # Exchange the code
                result = exchange_code_for_token(code)
                if result:
                    # Signal the server to stop
                    self.server._token_result = result
                return

        self.send_response(404)
        self.end_headers()


def generate_self_signed_cert():
    """Generate a temporary self-signed cert for localhost HTTPS."""
    import subprocess
    import tempfile
    cert_dir = tempfile.mkdtemp()
    cert_file = os.path.join(cert_dir, "cert.pem")
    key_file = os.path.join(cert_dir, "key.pem")

    subprocess.run([
        "openssl", "req", "-x509", "-newkey", "rsa:2048",
        "-keyout", key_file, "-out", cert_file,
        "-days", "1", "-nodes",
        "-subj", "/CN=localhost",
    ], capture_output=True)

    return cert_file, key_file


def cmd_serve(args):
    if not APP_SECRET:
        print("ERROR: Set THREADS_APP_SECRET in your environment first:")
        print(f'  export THREADS_APP_SECRET="your_secret_here"')
        sys.exit(1)

    # Generate self-signed cert
    print("Generating temporary SSL certificate...")
    cert_file, key_file = generate_self_signed_cert()

    # Build auth URL
    auth_url = (
        f"https://threads.net/oauth/authorize"
        f"?client_id={APP_ID}"
        f"&redirect_uri={urllib.parse.quote(REDIRECT_URI, safe='')}"
        f"&scope=threads_basic,threads_content_publish,threads_manage_replies"
        f"&response_type=code"
    )

    server = HTTPServer(("0.0.0.0", 8443), CallbackHandler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert_file, key_file)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    server._token_result = None

    print(f"\nLocal HTTPS callback server running on https://localhost:8443/callback")
    print(f"\nOpen this URL in your browser:\n")
    print(f"  {auth_url}\n")
    print("Waiting for callback...")

    while server._token_result is None:
        server.handle_request()

    print("Done! Server stopped.")
    server.server_close()

    # Clean up cert files
    os.unlink(cert_file)
    os.unlink(key_file)


def cmd_exchange(args):
    if not APP_SECRET:
        print("ERROR: Set THREADS_APP_SECRET in your environment first:")
        print(f'  export THREADS_APP_SECRET="your_secret_here"')
        sys.exit(1)

    result = exchange_code_for_token(args.code)
    if result:
        print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Threads OAuth Helper")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("serve", help="Start local HTTPS server and open auth flow")

    p = sub.add_parser("exchange", help="Exchange an auth code for tokens")
    p.add_argument("--code", required=True, help="Authorization code from callback")

    args = parser.parse_args()

    if args.command == "serve":
        cmd_serve(args)
    elif args.command == "exchange":
        cmd_exchange(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
