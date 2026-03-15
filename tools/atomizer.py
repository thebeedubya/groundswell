#!/usr/bin/env python3
"""
Groundswell Atomizer Tool — Split long-form content into platform-sized atoms.

Takes long content (voice memo transcripts, blog posts, etc.) and splits it
into platform-appropriate pieces. Real implementation will use voice scoring
and content DNA to optimize splits.

Usage:
    python3 tools/atomizer.py split --input "long content..." --platforms x,linkedin,threads
    python3 tools/atomizer.py from-file --path data/voice_memos/memo1.txt --platforms x,linkedin
"""

import argparse
import json
import os
import sys


def emit(data):
    json.dump(data, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    sys.exit(0)


# ---------------------------------------------------------------------------
# Platform limits for placeholder splits
# ---------------------------------------------------------------------------

PLATFORM_LIMITS = {
    "x": {"chars": 280, "label": "X (Twitter)"},
    "linkedin": {"chars": 3000, "label": "LinkedIn"},
    "threads": {"chars": 500, "label": "Threads"},
}


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def generate_placeholder_splits(text, platforms):
    """Generate placeholder split suggestions for each platform."""
    splits = {}
    word_count = len(text.split())

    for platform in platforms:
        limit = PLATFORM_LIMITS.get(platform)
        if not limit:
            continue

        char_limit = limit["chars"]
        label = limit["label"]

        if len(text) <= char_limit:
            splits[platform] = [{
                "index": 0,
                "text": f"[Would contain full text, {len(text)} chars]",
                "char_count": len(text),
                "within_limit": True,
            }]
        else:
            # Estimate number of posts needed
            estimated_posts = (len(text) // (char_limit - 20)) + 1
            splits[platform] = []
            for i in range(min(estimated_posts, 10)):  # Cap at 10 for readability
                splits[platform].append({
                    "index": i,
                    "text": f"[{label} atom {i + 1}/{estimated_posts} — placeholder]",
                    "estimated_chars": min(char_limit, len(text) - (i * char_limit)),
                    "within_limit": True,
                })

    return splits


def cmd_split(args):
    text = args.input
    if not text:
        emit({"ok": False, "error": "missing_input", "message": "--input is required"})

    platforms = [p.strip() for p in args.platforms.split(",")]
    invalid = [p for p in platforms if p not in PLATFORM_LIMITS]
    if invalid:
        emit({
            "ok": False,
            "error": "invalid_platform",
            "message": f"Unknown platforms: {', '.join(invalid)}. Valid: x, linkedin, threads",
        })

    splits = generate_placeholder_splits(text, platforms)

    emit({
        "ok": True,
        "dry_run": True,
        "input_length": len(text),
        "input_word_count": len(text.split()),
        "platforms": platforms,
        "splits": splits,
        "total_atoms": sum(len(v) for v in splits.values()),
        "message": "Stub splits — real implementation will use voice scoring and content DNA to optimize",
    })


def cmd_from_file(args):
    file_path = args.path

    if not os.path.exists(file_path):
        emit({
            "ok": False,
            "error": "file_not_found",
            "message": f"File not found: {file_path}",
        })

    try:
        with open(file_path, "r") as f:
            text = f.read()
    except Exception as e:
        emit({"ok": False, "error": "read_error", "message": f"Could not read file: {e}"})

    platforms = [p.strip() for p in args.platforms.split(",")]
    invalid = [p for p in platforms if p not in PLATFORM_LIMITS]
    if invalid:
        emit({
            "ok": False,
            "error": "invalid_platform",
            "message": f"Unknown platforms: {', '.join(invalid)}. Valid: x, linkedin, threads",
        })

    splits = generate_placeholder_splits(text, platforms)

    emit({
        "ok": True,
        "dry_run": True,
        "source_file": file_path,
        "input_length": len(text),
        "input_word_count": len(text.split()),
        "platforms": platforms,
        "splits": splits,
        "total_atoms": sum(len(v) for v in splits.values()),
        "message": "Stub splits — real implementation will use voice scoring and content DNA to optimize",
    })


# ---------------------------------------------------------------------------
# CLI parser
# ---------------------------------------------------------------------------


def build_parser():
    parser = argparse.ArgumentParser(
        description="Groundswell Atomizer Tool — Split long-form content into platform-sized atoms",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    # split
    p = sub.add_parser("split", help="Split inline text into platform atoms")
    p.add_argument("--input", required=True, help="Long-form text to split")
    p.add_argument("--platforms", required=True, help="Comma-separated platforms (x,linkedin,threads)")

    # from-file
    p = sub.add_parser("from-file", help="Split content from a file into platform atoms")
    p.add_argument("--path", required=True, help="Path to text file to split")
    p.add_argument("--platforms", required=True, help="Comma-separated platforms (x,linkedin,threads)")

    return parser


COMMANDS = {
    "split": cmd_split,
    "from-file": cmd_from_file,
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
