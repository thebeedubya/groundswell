#!/usr/bin/env python3
"""
Groundswell Video Tool — Record terminal sessions and package video content.

Uses asciinema for terminal recording and ffmpeg for video packaging.
Records agent tool calls as terminal screencasts for social proof content.

Usage:
    python3 tools/video.py record --command "python3 tools/db.py state" --output data/videos/demo.cast
    python3 tools/video.py package --input data/videos/demo.cast --output data/videos/demo.mp4
    python3 tools/video.py list
"""

import argparse
import json
import os
import sys


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEOS_DIR = os.path.join(REPO_ROOT, "data", "videos")


def emit(data):
    json.dump(data, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    sys.exit(0)


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def cmd_record(args):
    command = args.command
    output = args.output

    emit({
        "ok": False,
        "error": "not_configured",
        "message": "Terminal recording not yet implemented. Requires asciinema. Will record the given command as a .cast file.",
        "dry_run": True,
        "command": command,
        "output": output,
    })


def cmd_package(args):
    input_path = args.input
    output_path = args.output

    if not os.path.exists(input_path):
        emit({
            "ok": False,
            "error": "file_not_found",
            "message": f"Input file not found: {input_path}",
        })

    emit({
        "ok": False,
        "error": "not_configured",
        "message": "Video packaging not yet implemented. Requires ffmpeg and agg/svg-term. Will convert .cast to .mp4/.gif.",
        "dry_run": True,
        "input": input_path,
        "output": output_path,
    })


def cmd_list(args):
    videos = []
    if os.path.isdir(VIDEOS_DIR):
        for f in sorted(os.listdir(VIDEOS_DIR)):
            fpath = os.path.join(VIDEOS_DIR, f)
            if os.path.isfile(fpath):
                _, ext = os.path.splitext(f)
                videos.append({
                    "filename": f,
                    "path": fpath,
                    "size_bytes": os.path.getsize(fpath),
                    "type": ext.lstrip("."),
                })

    emit({
        "ok": True,
        "dry_run": True,
        "videos": videos,
        "count": len(videos),
        "videos_dir": VIDEOS_DIR,
        "message": "Listing files in videos directory.",
    })


# ---------------------------------------------------------------------------
# CLI parser
# ---------------------------------------------------------------------------


def build_parser():
    parser = argparse.ArgumentParser(
        description="Groundswell Video Tool — Record terminal sessions and package video content",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    # record
    p = sub.add_parser("record", help="Record a terminal command as an asciinema .cast file")
    p.add_argument("--command", required=True, help="Shell command to record")
    p.add_argument("--output", required=True, help="Output path for .cast file")

    # package
    p = sub.add_parser("package", help="Convert a .cast recording to .mp4 or .gif")
    p.add_argument("--input", required=True, help="Input .cast file path")
    p.add_argument("--output", required=True, help="Output .mp4 or .gif path")

    # list
    sub.add_parser("list", help="List all video files in data/videos/")

    return parser


COMMANDS = {
    "record": cmd_record,
    "package": cmd_package,
    "list": cmd_list,
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
