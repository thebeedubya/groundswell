#!/usr/bin/env python3
"""Integration tests for Groundswell core tools.

Each test runs the CLI tools as subprocesses, parses JSON output, and asserts
on fields. Temporary databases are used where possible (db.py and learning.py
support --db). For schedule.py (which hardcodes its DB path), we initialize the
default DB via db.py init first and clean up after.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(REPO_ROOT, "tools")
DATA_DIR = os.path.join(REPO_ROOT, "data")
DEFAULT_DB = os.path.join(DATA_DIR, "groundswell.db")

DB_PY = os.path.join(TOOLS_DIR, "db.py")
SCHEDULE_PY = os.path.join(TOOLS_DIR, "schedule.py")
LEARNING_PY = os.path.join(TOOLS_DIR, "learning.py")


def run_tool(cmd, expect_success=True):
    """Run a tool command and return parsed JSON (or raw stdout)."""
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    if expect_success and result.returncode != 0:
        raise AssertionError(
            f"Command failed (rc={result.returncode}): {' '.join(cmd)}\n"
            f"stderr: {result.stderr}\nstdout: {result.stdout}"
        )
    stdout = result.stdout.strip()
    if not stdout:
        return {"_raw": "", "_rc": result.returncode, "_stderr": result.stderr}
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return {"_raw": stdout, "_rc": result.returncode, "_stderr": result.stderr}


class TestDbInit(unittest.TestCase):
    """Test 1: db.py init creates all tables."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()

    def tearDown(self):
        os.unlink(self.db_path)

    def test_init_creates_tables(self):
        result = run_tool(["python3", DB_PY, "--db", self.db_path, "init"])
        self.assertTrue(result.get("ok"))

        # Verify tables exist by querying sqlite_master
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        ]
        conn.close()

        expected_tables = [
            "agent_heartbeats",
            "audience_graph",
            "content_genome",
            "edit_signals",
            "engagement_conversions",
            "events",
            "learned_models",
            "pattern_effectiveness",
            "pending_actions",
            "platform_cooldowns",
            "proof_stack",
            "schedule",
            "signals",
            "strategy_state",
            "tier_targets",
            "touchpoint_chain",
        ]
        for t in expected_tables:
            self.assertIn(t, tables, f"Table '{t}' not found after init")


class TestDbLogEventAndState(unittest.TestCase):
    """Test 2: db.py log-event and verify via db.py state."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        run_tool(["python3", DB_PY, "--db", self.db_path, "init"])

    def tearDown(self):
        os.unlink(self.db_path)

    def test_log_event_and_state(self):
        result = run_tool([
            "python3", DB_PY, "--db", self.db_path, "log-event",
            "--agent", "test-agent",
            "--type", "test-event",
            "--details", '{"foo": "bar"}',
        ])
        self.assertTrue(result.get("ok"))
        self.assertIn("event_id", result)
        self.assertIn("timestamp", result)

        state = run_tool(["python3", DB_PY, "--db", self.db_path, "state"])
        self.assertIn("recent_events", state)
        self.assertGreater(len(state["recent_events"]), 0)
        found = any(
            e["agent"] == "test-agent" and e["event_type"] == "test-event"
            for e in state["recent_events"]
        )
        self.assertTrue(found, "Logged event not found in state")


class TestDbSignalLifecycle(unittest.TestCase):
    """Test 3: db.py write-signal / read-signals / consume-signal lifecycle."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        run_tool(["python3", DB_PY, "--db", self.db_path, "init"])

    def tearDown(self):
        os.unlink(self.db_path)

    def test_signal_lifecycle(self):
        # Write a signal
        write_result = run_tool([
            "python3", DB_PY, "--db", self.db_path, "write-signal",
            "--type", "HOT_TARGET",
            "--source", "outbound",
            "--data", '{"handle": "@testuser"}',
        ])
        self.assertTrue(write_result.get("ok"))
        signal_id = write_result["signal_id"]

        # Read signals — should find 1
        read_result = run_tool([
            "python3", DB_PY, "--db", self.db_path, "read-signals",
        ])
        self.assertEqual(read_result["count"], 1)
        self.assertEqual(read_result["signals"][0]["type"], "HOT_TARGET")

        # Consume the signal
        consume_result = run_tool([
            "python3", DB_PY, "--db", self.db_path, "consume-signal",
            "--id", str(signal_id),
            "--by", "test-consumer",
        ])
        self.assertTrue(consume_result.get("ok"))

        # Read again — should be empty
        read_result2 = run_tool([
            "python3", DB_PY, "--db", self.db_path, "read-signals",
        ])
        self.assertEqual(read_result2["count"], 0)


class TestDbBrandSafetyDefault(unittest.TestCase):
    """Test 4: db.py brand-safety defaults to GREEN."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        run_tool(["python3", DB_PY, "--db", self.db_path, "init"])

    def tearDown(self):
        os.unlink(self.db_path)

    def test_brand_safety_default_green(self):
        result = run_tool([
            "python3", DB_PY, "--db", self.db_path, "brand-safety",
        ])
        self.assertEqual(result["color"], "GREEN")


class TestDbBrandSafetyBlack(unittest.TestCase):
    """Test 5: db.py set-brand-safety --color BLACK (kill switch)."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        run_tool(["python3", DB_PY, "--db", self.db_path, "init"])

    def tearDown(self):
        os.unlink(self.db_path)

    def test_set_brand_safety_black(self):
        run_tool([
            "python3", DB_PY, "--db", self.db_path, "set-brand-safety",
            "--color", "BLACK",
            "--reason", "emergency kill switch test",
        ])
        result = run_tool([
            "python3", DB_PY, "--db", self.db_path, "brand-safety",
        ])
        self.assertEqual(result["color"], "BLACK")


class TestDbTargets(unittest.TestCase):
    """Test 6: db.py add-target / tier-targets."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        run_tool(["python3", DB_PY, "--db", self.db_path, "init"])

    def tearDown(self):
        os.unlink(self.db_path)

    def test_add_and_list_targets(self):
        run_tool([
            "python3", DB_PY, "--db", self.db_path, "add-target",
            "--handle", "@kimrivers",
            "--tier", "1",
            "--platform", "x",
        ])
        run_tool([
            "python3", DB_PY, "--db", self.db_path, "add-target",
            "--handle", "@testuser",
            "--tier", "3",
            "--platform", "x",
        ])

        result = run_tool([
            "python3", DB_PY, "--db", self.db_path, "tier-targets",
        ])
        self.assertEqual(result["count"], 2)
        handles = [t["handle"] for t in result["targets"]]
        self.assertIn("kimrivers", handles)
        self.assertIn("testuser", handles)

        # Verify tier ordering (tier 1 before tier 3)
        tiers = [t["tier"] for t in result["targets"]]
        self.assertEqual(tiers, sorted(tiers))


class TestDbActions(unittest.TestCase):
    """Test 7: db.py add-action / update-action / pending-actions."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        run_tool(["python3", DB_PY, "--db", self.db_path, "init"])

    def tearDown(self):
        os.unlink(self.db_path)

    def test_action_lifecycle(self):
        # Add an action
        add_result = run_tool([
            "python3", DB_PY, "--db", self.db_path, "add-action",
            "--key", "reply:x:123",
            "--agent", "outbound",
            "--type", "reply",
            "--payload", '{"text": "great point"}',
        ])
        self.assertTrue(add_result.get("ok"))
        self.assertEqual(add_result["status"], "pending")

        # Check pending
        pending = run_tool([
            "python3", DB_PY, "--db", self.db_path, "pending-actions",
        ])
        self.assertEqual(pending["count"], 1)
        self.assertEqual(pending["actions"][0]["idempotency_key"], "reply:x:123")

        # Update to verified
        update_result = run_tool([
            "python3", DB_PY, "--db", self.db_path, "update-action",
            "--key", "reply:x:123",
            "--status", "verified",
        ])
        self.assertTrue(update_result.get("ok"))

        # Pending should still show (verified != completed)
        pending2 = run_tool([
            "python3", DB_PY, "--db", self.db_path, "pending-actions",
        ])
        # pending-actions filters on status='pending', so verified won't appear
        self.assertEqual(pending2["count"], 0)


class TestScheduleInit(unittest.TestCase):
    """Test 8: schedule.py init seeds tasks from config.yaml.

    schedule.py hardcodes DB_PATH so we must use the default location.
    We back up any existing DB and restore it after the test.
    """

    def setUp(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.backup = None
        if os.path.exists(DEFAULT_DB):
            self.backup = DEFAULT_DB + ".test_backup"
            shutil.copy2(DEFAULT_DB, self.backup)
        # Initialize a fresh DB
        run_tool(["python3", DB_PY, "init"])

    def tearDown(self):
        if self.backup and os.path.exists(self.backup):
            shutil.move(self.backup, DEFAULT_DB)
        elif self.backup is None and os.path.exists(DEFAULT_DB):
            os.unlink(DEFAULT_DB)

    def test_schedule_init_seeds_tasks(self):
        result = run_tool(["python3", SCHEDULE_PY, "init"])
        self.assertTrue(result.get("ok"))
        self.assertGreater(result["tasks_seeded"], 0)


class TestScheduleDue(unittest.TestCase):
    """Test 9: schedule.py due returns tasks when they're due.

    We seed the schedule and then manually set next_due in the past so
    tasks appear as due.
    """

    def setUp(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.backup = None
        if os.path.exists(DEFAULT_DB):
            self.backup = DEFAULT_DB + ".test_backup"
            shutil.copy2(DEFAULT_DB, self.backup)
        run_tool(["python3", DB_PY, "init"])
        run_tool(["python3", SCHEDULE_PY, "init"])

        # Set all tasks to be due in the past
        import sqlite3
        conn = sqlite3.connect(DEFAULT_DB)
        conn.execute("UPDATE schedule SET next_due = '2020-01-01T00:00:00+00:00'")
        conn.commit()
        conn.close()

    def tearDown(self):
        if self.backup and os.path.exists(self.backup):
            shutil.move(self.backup, DEFAULT_DB)
        elif self.backup is None and os.path.exists(DEFAULT_DB):
            os.unlink(DEFAULT_DB)

    def test_due_returns_tasks(self):
        result = run_tool(["python3", SCHEDULE_PY, "due"])
        self.assertIn("due", result)
        self.assertGreater(len(result["due"]), 0)
        # Each due task should have 'task' and 'agent' keys
        for task in result["due"]:
            self.assertIn("task", task)
            self.assertIn("agent", task)


class TestScheduleNextSleep(unittest.TestCase):
    """Test 10: schedule.py next-sleep returns an integer."""

    def setUp(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.backup = None
        if os.path.exists(DEFAULT_DB):
            self.backup = DEFAULT_DB + ".test_backup"
            shutil.copy2(DEFAULT_DB, self.backup)
        run_tool(["python3", DB_PY, "init"])
        run_tool(["python3", SCHEDULE_PY, "init"])

    def tearDown(self):
        if self.backup and os.path.exists(self.backup):
            shutil.move(self.backup, DEFAULT_DB)
        elif self.backup is None and os.path.exists(DEFAULT_DB):
            os.unlink(DEFAULT_DB)

    def test_next_sleep_returns_integer(self):
        proc = subprocess.run(
            ["python3", SCHEDULE_PY, "next-sleep"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        self.assertEqual(proc.returncode, 0)
        value = int(proc.stdout.strip())
        self.assertGreaterEqual(value, 10)


class TestScheduleComplete(unittest.TestCase):
    """Test 11: schedule.py complete updates next_due."""

    def setUp(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.backup = None
        if os.path.exists(DEFAULT_DB):
            self.backup = DEFAULT_DB + ".test_backup"
            shutil.copy2(DEFAULT_DB, self.backup)
        run_tool(["python3", DB_PY, "init"])
        run_tool(["python3", SCHEDULE_PY, "init"])

    def tearDown(self):
        if self.backup and os.path.exists(self.backup):
            shutil.move(self.backup, DEFAULT_DB)
        elif self.backup is None and os.path.exists(DEFAULT_DB):
            os.unlink(DEFAULT_DB)

    def test_complete_updates_next_due(self):
        # Get a task name from the schedule
        import sqlite3
        conn = sqlite3.connect(DEFAULT_DB)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT task, next_due FROM schedule LIMIT 1").fetchone()
        task_name = row["task"]
        old_next_due = row["next_due"]
        conn.close()

        result = run_tool([
            "python3", SCHEDULE_PY, "complete", "--task", task_name,
        ])
        self.assertTrue(result.get("ok"))
        self.assertIn("next_due", result)
        # next_due should have changed (it's recomputed)
        self.assertNotEqual(result["next_due"], old_next_due)


class TestLearningStatus(unittest.TestCase):
    """Test 12: learning.py status returns valid JSON."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        run_tool(["python3", DB_PY, "--db", self.db_path, "init"])

    def tearDown(self):
        os.unlink(self.db_path)

    def test_status_returns_json(self):
        result = run_tool([
            "python3", LEARNING_PY, "--db", self.db_path, "status",
        ])
        # Should have learning-related keys
        self.assertIn("learning_phase", result)
        self.assertIn("exploration_ratio", result)


class TestLearningGetWeights(unittest.TestCase):
    """Test 13: learning.py get-weights --platform x returns default weights."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        run_tool(["python3", DB_PY, "--db", self.db_path, "init"])

    def tearDown(self):
        os.unlink(self.db_path)

    def test_get_weights_defaults(self):
        result = run_tool([
            "python3", LEARNING_PY, "--db", self.db_path, "get-weights",
            "--platform", "x",
        ])
        self.assertIn("platform", result)
        self.assertEqual(result["platform"], "x")
        # Should have weight-related keys
        self.assertIn("content_weights", result)
        self.assertIn("exploration_ratio", result)


class TestLearningLogEdit(unittest.TestCase):
    """Test 14: learning.py log-edit computes edit magnitude."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        run_tool(["python3", DB_PY, "--db", self.db_path, "init"])

    def tearDown(self):
        os.unlink(self.db_path)

    def test_log_edit_computes_magnitude(self):
        result = run_tool([
            "python3", LEARNING_PY, "--db", self.db_path, "log-edit",
            "--draft", "hello world this is a test post about AI",
            "--final", "hey world this is a revised post about AI agents",
        ])
        self.assertTrue(result.get("ok"))
        self.assertIn("magnitude", result)
        # Magnitude should be > 0 since the texts differ
        self.assertGreater(result["magnitude"], 0.0)


if __name__ == "__main__":
    unittest.main()
