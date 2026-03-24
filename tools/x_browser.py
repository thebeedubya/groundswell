#!/usr/bin/env python3
"""
Groundswell X Browser Poster — Playwright fallback for cold account replies.

When the X API returns 403 on replies/QTs to cold accounts, this tool
posts directly via browser automation. Uses a persistent browser profile
so Brad only logs in once.

Usage:
    python3 tools/x_browser.py setup           # First-time: opens browser for manual login
    python3 tools/x_browser.py reply --url URL --text "reply text"
    python3 tools/x_browser.py post --text "tweet text"
    python3 tools/x_browser.py quote --url URL --text "quote text"
    python3 tools/x_browser.py status          # Check if session is valid
"""

import argparse
import asyncio
import json
import os
import random
import sys
import time
from pathlib import Path

from _common import emit, fail, now_iso, get_db, DB_PATH

PROFILE_DIR = Path.home() / ".groundswell" / "x_browser_profile"
PROFILE_DIR.mkdir(parents=True, exist_ok=True)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
)


# ---------------------------------------------------------------------------
# Browser management
# ---------------------------------------------------------------------------

def _launch_args():
    """Common launch arguments for the persistent context."""
    return {
        "user_data_dir": str(PROFILE_DIR),
        "headless": False,
        "viewport": {"width": 1280, "height": random.randint(850, 950)},
        "user_agent": USER_AGENT,
        "locale": "en-US",
        "timezone_id": "America/Chicago",
        "args": ["--disable-blink-features=AutomationControlled"],
    }


async def _apply_stealth(page):
    """Apply stealth patches to avoid detection."""
    try:
        from playwright_stealth import stealth_async
        await stealth_async(page)
    except ImportError:
        pass  # stealth is optional but recommended


async def _check_errors(page):
    """Check for common X error states."""
    checks = [
        ("text='This post is from an account that no longer exists'", "tweet_deleted"),
        ("text=\"Hmm...this page doesn't exist\"", "page_not_found"),
        ("text='Something went wrong. Try reloading.'", "page_error"),
        ("text='Rate limit exceeded'", "rate_limited"),
        ("text='Try again later'", "rate_limited"),
    ]
    for selector, error in checks:
        try:
            if await page.locator(selector).count() > 0:
                return error
        except Exception:
            pass

    if page.url.startswith("https://x.com/i/flow/login"):
        return "session_expired"

    return None


def _random_delay(low_ms=2000, high_ms=5000):
    """Random delay in milliseconds for human-like behavior."""
    return random.randint(low_ms, high_ms)


def _log_action(action_type, target_url, text, success, error=None):
    """Log browser action to events table."""
    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO events (timestamp, agent, event_type, details) VALUES (?, ?, ?, ?)",
            (
                now_iso(),
                "x_browser",
                f"browser_{action_type}",
                json.dumps({
                    "url": target_url,
                    "text": text[:100] if text else "",
                    "success": success,
                    "error": error,
                    "method": "playwright",
                }),
            ),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Core actions
# ---------------------------------------------------------------------------

async def do_reply(tweet_url, reply_text):
    """Navigate to a tweet and post a reply via browser."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(**_launch_args())
        page = context.pages[0] if context.pages else await context.new_page()
        await _apply_stealth(page)

        try:
            # Navigate to the tweet
            await page.goto(tweet_url)
            await page.wait_for_timeout(_random_delay(3000, 6000))

            # Check for errors
            error = await _check_errors(page)
            if error:
                _log_action("reply", tweet_url, reply_text, False, error)
                await context.close()
                return {"success": False, "error": error}

            # Wait for tweet to render
            await page.wait_for_selector('[data-testid="tweet"]', timeout=15000)

            # Click the reply button
            reply_btn = page.locator('[data-testid="reply"]').first
            await reply_btn.click()
            await page.wait_for_timeout(_random_delay(2000, 4000))

            # Find the reply compose box inside the modal dialog
            # (the reply button opens a modal; there may also be an
            # offscreen inline textarea, so we scope to the dialog)
            modal = page.locator('[role="dialog"]')
            if await modal.count() > 0:
                reply_box = modal.locator('[data-testid="tweetTextarea_0"]').first
            else:
                reply_box = page.locator('[data-testid="tweetTextarea_0"]').first
            await reply_box.click()
            await page.wait_for_timeout(_random_delay(500, 1500))

            # Type with human-like delay
            await reply_box.type(reply_text, delay=random.randint(30, 80))
            await page.wait_for_timeout(_random_delay(1500, 3000))

            # Submit — try modal button first, then inline fallback
            modal = page.locator('[role="dialog"]')
            if await modal.count() > 0:
                submit = modal.locator('[data-testid="tweetButton"]')
                if await submit.count() == 0:
                    submit = modal.locator('[data-testid="tweetButtonInline"]')
            else:
                submit = page.locator('[data-testid="tweetButtonInline"]')
            await submit.click()
            await page.wait_for_timeout(_random_delay(3000, 6000))

            # Verify — modal should close after successful reply
            try:
                await page.wait_for_selector(
                    '[role="dialog"]', state="hidden", timeout=10000
                )
                _log_action("reply", tweet_url, reply_text, True)
                await context.close()
                return {"success": True, "error": None, "method": "playwright"}
            except Exception:
                # Modal might not have existed; check if textarea count dropped
                remaining = await page.locator('[data-testid="tweetTextarea_0"]').count()
                if remaining <= 1:
                    _log_action("reply", tweet_url, reply_text, True)
                    await context.close()
                    return {"success": True, "error": None, "method": "playwright"}
                _log_action("reply", tweet_url, reply_text, False, "compose_still_visible")
                await context.close()
                return {"success": False, "error": "compose_still_visible"}

        except Exception as e:
            _log_action("reply", tweet_url, reply_text, False, str(e))
            await context.close()
            return {"success": False, "error": str(e)}


async def do_post(tweet_text):
    """Post a new tweet via browser."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(**_launch_args())
        page = context.pages[0] if context.pages else await context.new_page()
        await _apply_stealth(page)

        try:
            await page.goto("https://x.com/compose/post")
            await page.wait_for_timeout(_random_delay(3000, 5000))

            error = await _check_errors(page)
            if error:
                _log_action("post", "https://x.com/compose/post", tweet_text, False, error)
                await context.close()
                return {"success": False, "error": error}

            # Type in compose box — scope to dialog/modal to avoid
            # ambiguity when the home timeline compose is also present
            modal = page.locator('[role="dialog"]')
            if await modal.count() > 0:
                compose_box = modal.locator('[data-testid="tweetTextarea_0"]').first
            else:
                compose_box = page.locator('[data-testid="tweetTextarea_0"]').first
            await compose_box.click()
            await page.wait_for_timeout(_random_delay(500, 1500))
            await compose_box.type(tweet_text, delay=random.randint(30, 80))
            await page.wait_for_timeout(_random_delay(1500, 3000))

            # Submit — prefer modal button, fall back to inline
            if await modal.count() > 0:
                submit = modal.locator('[data-testid="tweetButton"]').first
            else:
                submit = page.locator('[data-testid="tweetButton"]').first
            await submit.click()
            await page.wait_for_timeout(_random_delay(3000, 6000))

            _log_action("post", "https://x.com/compose/post", tweet_text, True)
            await context.close()
            return {"success": True, "error": None, "method": "playwright"}

        except Exception as e:
            _log_action("post", "https://x.com/compose/post", tweet_text, False, str(e))
            await context.close()
            return {"success": False, "error": str(e)}


async def do_quote(tweet_url, quote_text):
    """Quote tweet via browser."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(**_launch_args())
        page = context.pages[0] if context.pages else await context.new_page()
        await _apply_stealth(page)

        try:
            await page.goto(tweet_url)
            await page.wait_for_timeout(_random_delay(3000, 6000))

            error = await _check_errors(page)
            if error:
                _log_action("quote", tweet_url, quote_text, False, error)
                await context.close()
                return {"success": False, "error": error}

            await page.wait_for_selector('[data-testid="tweet"]', timeout=15000)

            # Click retweet button to get QT option
            retweet_btn = page.locator('[data-testid="retweet"]').first
            await retweet_btn.click()
            await page.wait_for_timeout(_random_delay(1000, 2000))

            # Click "Quote" from the dropdown
            quote_option = page.locator('[data-testid="Dropdown"] >> text=Quote')
            if await quote_option.count() == 0:
                # Fallback selector
                quote_option = page.locator('text="Quote"').first
            await quote_option.click()
            await page.wait_for_timeout(_random_delay(2000, 4000))

            # Type in compose box
            compose_box = page.locator('[data-testid="tweetTextarea_0"]')
            await compose_box.click()
            await page.wait_for_timeout(_random_delay(500, 1500))
            await compose_box.type(quote_text, delay=random.randint(30, 80))
            await page.wait_for_timeout(_random_delay(1500, 3000))

            # Submit
            submit = page.locator('[data-testid="tweetButton"]')
            await submit.click()
            await page.wait_for_timeout(_random_delay(3000, 6000))

            _log_action("quote", tweet_url, quote_text, True)
            await context.close()
            return {"success": True, "error": None, "method": "playwright"}

        except Exception as e:
            _log_action("quote", tweet_url, quote_text, False, str(e))
            await context.close()
            return {"success": False, "error": str(e)}


async def do_status():
    """Check if browser session is valid."""
    from playwright.async_api import async_playwright

    if not PROFILE_DIR.exists() or not any(PROFILE_DIR.iterdir()):
        return {"logged_in": False, "error": "no_profile", "message": "Run 'setup' first"}

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(**_launch_args())
        page = context.pages[0] if context.pages else await context.new_page()
        await _apply_stealth(page)

        try:
            await page.goto("https://x.com/home")
            await page.wait_for_timeout(5000)

            error = await _check_errors(page)
            if error == "session_expired":
                await context.close()
                return {"logged_in": False, "error": "session_expired", "message": "Run 'setup' to re-login"}

            # Check for the compose button as proof of login
            compose = page.locator('a[href="/compose/post"]')
            if await compose.count() > 0:
                await context.close()
                return {"logged_in": True, "error": None, "profile_dir": str(PROFILE_DIR)}

            await context.close()
            return {"logged_in": False, "error": "unknown", "message": "Could not verify login"}

        except Exception as e:
            await context.close()
            return {"logged_in": False, "error": str(e)}


def do_setup():
    """Open browser for manual login. Session persists to profile dir."""
    from playwright.sync_api import sync_playwright

    print(f"Opening browser for X login...")
    print(f"Profile directory: {PROFILE_DIR}")
    print()
    print("1. Log in to X with your account")
    print("2. Complete any 2FA if prompted")
    print("3. Once you see your home timeline, press Enter here")
    print()

    p = sync_playwright().start()
    context = p.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        headless=False,
        viewport={"width": 1280, "height": 900},
        user_agent=USER_AGENT,
        locale="en-US",
        timezone_id="America/Chicago",
        args=["--disable-blink-features=AutomationControlled"],
    )
    page = context.pages[0] if context.pages else context.new_page()

    try:
        from playwright_stealth import stealth_sync
        stealth_sync(page)
    except ImportError:
        pass

    page.goto("https://x.com/login")

    input("Press Enter after you've logged in successfully...")

    context.close()
    p.stop()

    print()
    print(f"Session saved to {PROFILE_DIR}")
    print("You can now use 'reply', 'post', and 'quote' commands.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        description="Groundswell X Browser Poster — Playwright fallback for cold accounts",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("setup", help="First-time browser login setup")

    p = sub.add_parser("reply", help="Reply to a tweet via browser")
    p.add_argument("--url", required=True, help="Tweet URL to reply to")
    p.add_argument("--text", required=True, help="Reply text")

    p = sub.add_parser("post", help="Post a new tweet via browser")
    p.add_argument("--text", required=True, help="Tweet text")

    p = sub.add_parser("quote", help="Quote tweet via browser")
    p.add_argument("--url", required=True, help="Tweet URL to quote")
    p.add_argument("--text", required=True, help="Quote text")

    sub.add_parser("status", help="Check if browser session is valid")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help(sys.stderr)
        sys.exit(1)

    if args.command == "setup":
        do_setup()
    elif args.command == "reply":
        result = asyncio.run(do_reply(args.url, args.text))
        emit(result)
    elif args.command == "post":
        result = asyncio.run(do_post(args.text))
        emit(result)
    elif args.command == "quote":
        result = asyncio.run(do_quote(args.url, args.text))
        emit(result)
    elif args.command == "status":
        result = asyncio.run(do_status())
        emit(result)
    else:
        fail(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
