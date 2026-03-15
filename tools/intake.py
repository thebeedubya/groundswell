#!/usr/bin/env python3
"""
Groundswell Intake Tool — Process voice memos and raw content inputs.

Handles audio transcription and content ingestion pipeline.
Requires external transcription service configuration.

Usage:
    python3 tools/intake.py process --audio PATH
    python3 tools/intake.py list-pending
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
# Subcommand handlers
# ---------------------------------------------------------------------------


def cmd_process(args):
    audio_path = args.audio

    if not os.path.exists(audio_path):
        emit({
            "ok": False,
            "error": "file_not_found",
            "message": f"Audio file not found: {audio_path}",
        })

    file_size = os.path.getsize(audio_path)
    _, ext = os.path.splitext(audio_path)

    emit({
        "ok": False,
        "error": "not_configured",
        "message": "Audio transcription not yet implemented. Will use Whisper or similar service to transcribe voice memos.",
        "dry_run": True,
        "audio_path": audio_path,
        "file_size_bytes": file_size,
        "file_extension": ext,
        "transcript": None,
        "content_atoms": [],
    })


def cmd_list_pending(args):
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    intake_dir = os.path.join(repo_root, "data", "voice_memos")

    pending = []
    if os.path.isdir(intake_dir):
        for f in sorted(os.listdir(intake_dir)):
            fpath = os.path.join(intake_dir, f)
            if os.path.isfile(fpath):
                pending.append({
                    "filename": f,
                    "path": fpath,
                    "size_bytes": os.path.getsize(fpath),
                    "status": "pending",
                })

    emit({
        "ok": True,
        "dry_run": True,
        "pending": pending,
        "count": len(pending),
        "intake_dir": intake_dir,
        "message": "Listing files in intake directory. Processing not yet implemented.",
    })


# ---------------------------------------------------------------------------
# CLI parser
# ---------------------------------------------------------------------------


def build_parser():
    parser = argparse.ArgumentParser(
        description="Groundswell Intake Tool — Process voice memos and raw content inputs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    # process
    p = sub.add_parser("process", help="Process an audio file (transcribe and extract content atoms)")
    p.add_argument("--audio", required=True, help="Path to audio file (mp3, m4a, wav)")

    # list-pending
    sub.add_parser("list-pending", help="List unprocessed files in the intake directory")

    return parser


COMMANDS = {
    "process": cmd_process,
    "list-pending": cmd_list_pending,
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
