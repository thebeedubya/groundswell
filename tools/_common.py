"""
Shared utilities for Groundswell CLI tools.

Extracted from tools/db.py, tools/policy.py, tools/learning.py,
tools/content_filter.py, and tools/replenish.py to eliminate duplication.
"""

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

try:
    import yaml as _yaml
except ImportError:
    _yaml = None


# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(REPO_ROOT, "data", "groundswell.db")
CONFIG_PATH = os.path.join(REPO_ROOT, "config.yaml")
DATA_DIR = os.path.join(REPO_ROOT, "data")


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def emit(data):
    """JSON output to stdout, then exit 0."""
    json.dump(data, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    sys.exit(0)


def fail(msg):
    """Error to stderr and exit 1."""
    print(msg, file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Time
# ---------------------------------------------------------------------------

def now_iso():
    """UTC ISO timestamp with Z suffix."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def get_db(path=None):
    """SQLite connection with WAL mode and Row factory.

    Args:
        path: database file path.  Defaults to DB_PATH.
    """
    path = path or DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def rows_to_list(rows):
    """Convert sqlite3.Row results to a list of plain dicts."""
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config():
    """Load config.yaml and return the parsed dict."""
    if _yaml is None:
        fail("PyYAML is required: pip install pyyaml")
    try:
        with open(CONFIG_PATH, "r") as f:
            return _yaml.safe_load(f)
    except FileNotFoundError:
        fail(f"config.yaml not found at {CONFIG_PATH}")
    except _yaml.YAMLError as exc:
        fail(f"Invalid config.yaml: {exc}")
