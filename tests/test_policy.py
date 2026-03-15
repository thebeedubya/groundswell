#!/usr/bin/env python3
"""Policy-specific integration tests for Groundswell.

Tests run tools/policy.py as a subprocess and parse JSON output.
Since policy.py hardcodes its DB_PATH, we use the default database location
and back up / restore any existing DB around each test.
"""

import json
import os
import shutil
import sqlite3
import subprocess
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(REPO_ROOT, "tools")
DATA_DIR = os.path.join(REPO_ROOT, "data")
DEFAULT_DB = os.path.join(DATA_DIR, "groundswell.db")

DB_PY = os.path.join(TOOLS_DIR, "db.py")
POLICY_PY = os.path.join(TOOLS_DIR, "policy.py")


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


def run_db(subcmd_args):
    """Shorthand to run db.py with the default DB path."""
    return run_tool(["python3", DB_PY] + subcmd_args)


def run_policy(action, platform="x", text=None, target=None):
    """Run policy.py check with the given parameters."""
    cmd = ["python3", POLICY_PY, "check", "--action", action, "--platform", platform]
    if text is not None:
        cmd.extend(["--text", text])
    if target is not None:
        cmd.extend(["--target", target])
    return run_tool(cmd)


class PolicyTestBase(unittest.TestCase):
    """Base class that manages DB backup/restore around each test."""

    def setUp(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.backup = None
        if os.path.exists(DEFAULT_DB):
            self.backup = DEFAULT_DB + ".policy_test_backup"
            shutil.copy2(DEFAULT_DB, self.backup)
        # Initialize a fresh DB
        run_db(["init"])

    def tearDown(self):
        if self.backup and os.path.exists(self.backup):
            shutil.move(self.backup, DEFAULT_DB)
        elif self.backup is None and os.path.exists(DEFAULT_DB):
            os.unlink(DEFAULT_DB)


class TestGreenPostPhaseA(PolicyTestBase):
    """Test 1: GREEN + post + Phase A = ESCALATE.

    config.yaml has trust.current_phase = A and brand_safety defaults to GREEN.
    All posts in Phase A require approval (ESCALATE).
    """

    def test_green_post_phase_a_escalate(self):
        result = run_policy("post", text="Great insights on AI agents today")
        self.assertEqual(result["decision"], "ESCALATE")
        # Should mention trust phase A or post approval
        reasons_text = " ".join(result.get("reasons", []))
        self.assertIn("phase", reasons_text.lower())


class TestBlackBlocksAll(PolicyTestBase):
    """Test 2: BLACK = BLOCK for any action."""

    def test_black_blocks_post(self):
        run_db(["set-brand-safety", "--color", "BLACK", "--reason", "test"])
        result = run_policy("post", text="anything")
        self.assertEqual(result["decision"], "BLOCK")

    def test_black_blocks_reply(self):
        run_db(["set-brand-safety", "--color", "BLACK", "--reason", "test"])
        result = run_policy("reply", text="nice post", target="@someone")
        self.assertEqual(result["decision"], "BLOCK")

    def test_black_blocks_engage(self):
        run_db(["set-brand-safety", "--color", "BLACK", "--reason", "test"])
        result = run_policy("engage", target="@someone")
        self.assertEqual(result["decision"], "BLOCK")


class TestRedEscalatesAll(PolicyTestBase):
    """Test 3: RED = ESCALATE for any action."""

    def test_red_escalates_post(self):
        run_db(["set-brand-safety", "--color", "RED", "--reason", "test"])
        result = run_policy("post", text="AI automation rocks")
        self.assertEqual(result["decision"], "ESCALATE")

    def test_red_escalates_reply(self):
        run_db(["set-brand-safety", "--color", "RED", "--reason", "test"])
        result = run_policy("reply", text="agreed", target="@someone")
        self.assertEqual(result["decision"], "ESCALATE")

    def test_red_escalates_engage(self):
        run_db(["set-brand-safety", "--color", "RED", "--reason", "test"])
        result = run_policy("engage", target="@someone")
        self.assertEqual(result["decision"], "ESCALATE")


class TestCannabisNeverSay(PolicyTestBase):
    """Test 4: Cannabis "never say" phrases get BLOCK."""

    def test_replace_your_staff_blocked(self):
        """Test 5: 'replace your staff' blocked."""
        result = run_policy("post", text="AI can replace your staff easily")
        self.assertEqual(result["decision"], "BLOCK")
        reasons_text = " ".join(result.get("reasons", []))
        self.assertIn("never-say", reasons_text.lower())

    def test_fire_compliance_team_blocked(self):
        """Test 6: 'fire your compliance team' blocked."""
        result = run_policy("post", text="You should fire your compliance team")
        self.assertEqual(result["decision"], "BLOCK")
        reasons_text = " ".join(result.get("reasons", []))
        self.assertIn("never-say", reasons_text.lower())

    def test_cut_headcount_blocked(self):
        result = run_policy("post", text="Time to cut headcount with AI")
        self.assertEqual(result["decision"], "BLOCK")


class TestNormalTextPasses(PolicyTestBase):
    """Test 7: Normal text passes content filter.

    In Phase A posts still ESCALATE (trust gate), but the content filter
    itself should not add a BLOCK reason. For a reply action the trust gate
    is less restrictive, so we test a reply to ensure no content block.
    """

    def test_normal_text_no_content_block(self):
        result = run_policy(
            "reply",
            text="Great thread on AI-powered cannabis compliance workflows",
            target="@someone",
        )
        # Should not be BLOCK (content filter should pass)
        self.assertNotEqual(result["decision"], "BLOCK")
        # Check no content_blocked reasons
        for reason in result.get("reasons", []):
            self.assertNotIn("content_blocked", reason)


class TestTier1PhaseB(PolicyTestBase):
    """Test 8: Tier 1 target in Phase B = ESCALATE.

    We temporarily need Phase B. Since policy.py reads config.yaml directly,
    we modify config.yaml for this test and restore it after.
    """

    def setUp(self):
        super().setUp()
        self.config_path = os.path.join(REPO_ROOT, "config.yaml")
        with open(self.config_path, "r") as f:
            self.original_config = f.read()
        # Patch trust phase to B
        patched = self.original_config.replace(
            'current_phase: "A"', 'current_phase: "B"'
        )
        with open(self.config_path, "w") as f:
            f.write(patched)
        # Add a Tier 1 target
        run_db(["add-target", "--handle", "@kingmaker", "--tier", "1", "--platform", "x"])

    def tearDown(self):
        # Restore original config
        with open(self.config_path, "w") as f:
            f.write(self.original_config)
        super().tearDown()

    def test_tier1_phase_b_escalate(self):
        result = run_policy("reply", text="love your work", target="@kingmaker")
        self.assertEqual(result["decision"], "ESCALATE")
        reasons_text = " ".join(result.get("reasons", []))
        self.assertIn("tier", reasons_text.lower())


class TestTier3PhaseB(PolicyTestBase):
    """Test 9: Tier 3 target in Phase B = APPROVE.

    Phase B allows autonomous interaction with Tier 3+ targets.
    """

    def setUp(self):
        super().setUp()
        self.config_path = os.path.join(REPO_ROOT, "config.yaml")
        with open(self.config_path, "r") as f:
            self.original_config = f.read()
        # Patch trust phase to B
        patched = self.original_config.replace(
            'current_phase: "A"', 'current_phase: "B"'
        )
        with open(self.config_path, "w") as f:
            f.write(patched)
        # Add a Tier 3 target
        run_db(["add-target", "--handle", "@community_member", "--tier", "3", "--platform", "x"])

    def tearDown(self):
        with open(self.config_path, "w") as f:
            f.write(self.original_config)
        super().tearDown()

    def test_tier3_phase_b_approve(self):
        result = run_policy("reply", text="great insight", target="@community_member")
        self.assertEqual(result["decision"], "APPROVE")


class TestRateLimitWarning(PolicyTestBase):
    """Test 10: Rate limit warning at 90%.

    config.yaml sets max_actions_per_hour = 30, so at 27 actions we should
    see a warning about approaching rate limit.
    """

    def test_rate_limit_warning_at_90_percent(self):
        # Insert 27 events (90% of 30) with recent timestamps
        conn = sqlite3.connect(DEFAULT_DB)
        from datetime import datetime, timezone
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        for i in range(27):
            conn.execute(
                "INSERT INTO events (timestamp, agent, event_type, details) VALUES (?, ?, ?, ?)",
                (now_iso, "test", "action", f'{{"i": {i}}}'),
            )
        conn.commit()
        conn.close()

        result = run_policy("engage", target="@someone")
        # Should have a warning about approaching rate limit
        warnings_text = " ".join(result.get("warnings", []))
        self.assertIn("rate_limit", warnings_text.lower())


if __name__ == "__main__":
    unittest.main()
