#!/usr/bin/env python3
"""
Groundswell Blog Publisher — Publish long-form content to dbradwood.com.

Takes backlog items with platform="blog" and writes them as MDX files
to the dbradwood.com repo, commits, and pushes for Vercel auto-deploy.

Usage:
    python3 tools/blog.py publish --data '{"title": "...", "summary": "...", "body": "...", "tags": [...]}'
    python3 tools/blog.py publish --data '{"title": "...", ...}' --status draft
    python3 tools/blog.py list
    python3 tools/blog.py check --slug "post-slug"
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLOG_REPO = os.path.expanduser("~/Projects/dbradwood.com")
WRITING_DIR = os.path.join(BLOG_REPO, "content", "writing")


def emit(data):
    json.dump(data, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    sys.exit(0)


def fail(msg):
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def slugify(title):
    """Convert title to URL-safe slug."""
    slug = title.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    slug = slug.strip('-')
    return slug[:80]


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_publish(args):
    """Publish a blog post to dbradwood.com."""
    if not os.path.isdir(BLOG_REPO):
        fail(f"Blog repo not found at {BLOG_REPO}")

    try:
        data = json.loads(args.data)
    except json.JSONDecodeError as e:
        fail(f"Invalid JSON: {e}")

    title = data.get("title", "").strip()
    summary = data.get("summary", "").strip()
    body = data.get("body", "").strip()
    tags = data.get("tags", [])
    status = args.status or "published"

    if not title:
        fail("title is required")
    if not summary:
        fail("summary is required")
    if not body:
        fail("body is required")

    slug = slugify(title)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Check for duplicate slug
    mdx_path = os.path.join(WRITING_DIR, f"{slug}.mdx")
    if os.path.exists(mdx_path):
        slug = f"{slug}-{datetime.now(timezone.utc).strftime('%H%M')}"
        mdx_path = os.path.join(WRITING_DIR, f"{slug}.mdx")

    # Build frontmatter
    tag_yaml = "\n".join(f"  - {t}" for t in tags) if tags else ""
    escaped_title = title.replace('"', "'")
    escaped_summary = summary.replace('"', "'")
    lines = [
        "---",
        "type: writing",
        f'title: "{escaped_title}"',
        f'summary: "{escaped_summary}"',
        f"status: {status}",
        f"publishedAt: {today}",
    ]
    if tag_yaml:
        lines.append("tags:")
        lines.append(tag_yaml)
    lines.append("---")
    frontmatter = "\n".join(lines) + "\n"

    # Write MDX file
    os.makedirs(WRITING_DIR, exist_ok=True)
    with open(mdx_path, "w") as f:
        f.write(frontmatter)
        f.write("\n")
        f.write(body)
        f.write("\n")

    # Git commit and push
    try:
        subprocess.run(["git", "add", mdx_path],
                       cwd=BLOG_REPO, capture_output=True, timeout=10)
        subprocess.run(["git", "commit", "-m", f"blog: {title[:60]}"],
                       cwd=BLOG_REPO, capture_output=True, timeout=10)
        subprocess.run(["git", "push", "origin", "main"],
                       cwd=BLOG_REPO, capture_output=True, timeout=30)
    except Exception:
        pass  # Deploy failure shouldn't block

    # Notify Google of the new URL via sitemap resubmission
    try:
        subprocess.run(
            ["python3", os.path.join(REPO_ROOT, "tools", "seo.py"), "submit-urls"],
            capture_output=True, timeout=60,
        )
    except Exception:
        pass

    emit({
        "ok": True,
        "slug": slug,
        "title": title,
        "status": status,
        "path": mdx_path,
        "url": f"https://dbradwood.com/writing/{slug}",
    })


def cmd_list(args):
    """List existing blog posts."""
    if not os.path.isdir(WRITING_DIR):
        emit({"posts": [], "count": 0})
        return

    posts = []
    for fname in sorted(os.listdir(WRITING_DIR)):
        if not fname.endswith(".mdx"):
            continue
        fpath = os.path.join(WRITING_DIR, fname)
        with open(fpath) as f:
            content = f.read()

        # Parse frontmatter
        if content.startswith("---"):
            end = content.index("---", 3)
            fm_text = content[3:end].strip()
            post = {"slug": fname.replace(".mdx", "")}
            for line in fm_text.split("\n"):
                if ":" in line and not line.startswith(" "):
                    k, _, v = line.partition(":")
                    post[k.strip()] = v.strip().strip('"')
            posts.append(post)

    emit({"posts": posts, "count": len(posts)})


def cmd_check(args):
    """Check if a post exists."""
    slug = args.slug
    mdx_path = os.path.join(WRITING_DIR, f"{slug}.mdx")
    exists = os.path.exists(mdx_path)
    emit({"slug": slug, "exists": exists, "path": mdx_path if exists else None})


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        description="Groundswell Blog Publisher — dbradwood.com",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("publish", help="Publish a blog post")
    p.add_argument("--data", required=True, help="JSON with title, summary, body, tags")
    p.add_argument("--status", default="published", choices=["draft", "published"],
                   help="Post status (default: published)")

    sub.add_parser("list", help="List existing blog posts")

    p = sub.add_parser("check", help="Check if a post exists")
    p.add_argument("--slug", required=True, help="Post slug to check")

    return parser


COMMANDS = {
    "publish": cmd_publish,
    "list": cmd_list,
    "check": cmd_check,
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
    except SystemExit:
        raise
    except Exception as e:
        fail(str(e))


if __name__ == "__main__":
    main()
