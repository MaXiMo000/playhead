"""Run: python tests/test_hook.py

Real temp files, real pending-state files under a real cwd -- the same
level custody's test_hook.py operates at, one level up from a real
subprocess/stdin pipe (which needs the package actually installed).
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from playhead_hook import hook


class TestEditRoundTrip(unittest.TestCase):
    def test_pre_then_post_writes_one_event_with_before_and_after(self):
        with tempfile.TemporaryDirectory() as cwd:
            file_path = str(pathlib.Path(cwd) / "auth.py")
            pathlib.Path(file_path).write_text("old content")

            hook.pre_tool_use({
                "hook_event_name": "PreToolUse", "tool_name": "Edit",
                "tool_use_id": "toolu_1", "session_id": "sess_1", "cwd": cwd,
                "tool_input": {"file_path": file_path},
            })

            # Simulate the edit actually happening between the two hooks.
            pathlib.Path(file_path).write_text("new content")

            hook.post_tool_use({
                "hook_event_name": "PostToolUse", "tool_name": "Edit",
                "tool_use_id": "toolu_1", "session_id": "sess_1", "cwd": cwd,
                "tool_response": {"success": True},
            })

            events = list((pathlib.Path(cwd) / ".playhead" / "events").glob("*.json"))
            self.assertEqual(len(events), 1)
            event = json.loads(events[0].read_text())
            self.assertEqual(event["before_content"], "old content")
            self.assertEqual(event["after_content"], "new content")
            self.assertEqual(event["tool_reported_success"], True)

            # The pending state must be cleaned up after finalizing.
            pending = list((pathlib.Path(cwd) / ".playhead" / "pending").glob("*.json"))
            self.assertEqual(pending, [])

    def test_post_without_matching_pre_is_skipped_not_a_half_event(self):
        with tempfile.TemporaryDirectory() as cwd:
            hook.post_tool_use({
                "hook_event_name": "PostToolUse", "tool_name": "Edit",
                "tool_use_id": "toolu_orphan", "session_id": "sess_1", "cwd": cwd,
                "tool_response": {"success": True},
            })
            events_dir = pathlib.Path(cwd) / ".playhead" / "events"
            self.assertFalse(events_dir.exists() and any(events_dir.iterdir()))


class TestBashRoundTrip(unittest.TestCase):
    def test_pre_then_post_writes_a_bash_event(self):
        with tempfile.TemporaryDirectory() as cwd:
            hook.pre_tool_use({
                "hook_event_name": "PreToolUse", "tool_name": "Bash",
                "tool_use_id": "toolu_2", "session_id": "sess_1", "cwd": cwd,
                "tool_input": {"command": "pytest -q"},
            })
            hook.post_tool_use({
                "hook_event_name": "PostToolUse", "tool_name": "Bash",
                "tool_use_id": "toolu_2", "session_id": "sess_1", "cwd": cwd,
                "tool_response": {"stdout": "3 passed\n", "stderr": ""},
            })
            events = list((pathlib.Path(cwd) / ".playhead" / "events").glob("*.json"))
            self.assertEqual(len(events), 1)
            event = json.loads(events[0].read_text())
            self.assertEqual(event["bash_command"], "pytest -q")
            self.assertEqual(event["bash_output"], "3 passed\n")


class TestUnwatchedToolsAreIgnored(unittest.TestCase):
    def test_read_tool_writes_nothing(self):
        with tempfile.TemporaryDirectory() as cwd:
            hook.pre_tool_use({
                "hook_event_name": "PreToolUse", "tool_name": "Read",
                "tool_use_id": "toolu_3", "session_id": "sess_1", "cwd": cwd,
                "tool_input": {"file_path": "whatever.py"},
            })
            self.assertFalse((pathlib.Path(cwd) / ".playhead").exists())


class TestMainNeverRaises(unittest.TestCase):
    def test_malformed_stdin_returns_zero(self):
        import io
        old_stdin = sys.stdin
        sys.stdin = io.StringIO("not json")
        try:
            self.assertEqual(hook.main(), 0)
        finally:
            sys.stdin = old_stdin

    def test_unknown_event_name_returns_zero(self):
        import io
        old_stdin = sys.stdin
        sys.stdin = io.StringIO(json.dumps({"hook_event_name": "SomethingElse"}))
        try:
            self.assertEqual(hook.main(), 0)
        finally:
            sys.stdin = old_stdin


if __name__ == "__main__":
    unittest.main()
