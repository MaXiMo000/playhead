"""Run: python tests/test_core.py

core.py is pure aside from read_file_text()'s single filesystem read -- no
stdin/stdout. test_hook.py covers the stdin/stdout glue and real pending
files.
"""
from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from playhead_hook import core


class TestReadFileText(unittest.TestCase):
    def test_missing_file_reads_as_none(self):
        self.assertIsNone(core.read_file_text("/no/such/path/on/disk"))

    def test_real_file_reads_its_text(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("hello world")
            path = f.name
        try:
            self.assertEqual(core.read_file_text(path), "hello world")
        finally:
            pathlib.Path(path).unlink()

    def test_binary_file_reads_as_none(self):
        with tempfile.NamedTemporaryFile("wb", suffix=".bin", delete=False) as f:
            f.write(bytes(range(256)))
            path = f.name
        try:
            self.assertIsNone(core.read_file_text(path))
        finally:
            pathlib.Path(path).unlink()

    def test_oversized_file_reads_as_none(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("x" * (core.MAX_CONTENT_BYTES + 1))
            path = f.name
        try:
            self.assertIsNone(core.read_file_text(path))
        finally:
            pathlib.Path(path).unlink()


class TestBuildEditEvent(unittest.TestCase):
    def test_captures_before_and_reads_after_fresh(self):
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write("after")
            path = f.name
        try:
            event = core.build_edit_event(
                file_path=path, before_content="before", tool_name="Edit",
                tool_use_id="toolu_1", session_id="sess_1", cwd="/repo",
                ts_start=1.0, ts_end=2.0, tool_response={"success": True},
            )
            self.assertEqual(event["before_content"], "before")
            self.assertEqual(event["after_content"], "after")
            self.assertEqual(event["tool_reported_success"], True)
            self.assertIsNone(event["bash_command"])
        finally:
            pathlib.Path(path).unlink()

    def test_write_creating_a_new_file_has_no_before_content(self):
        # A Write call can create a file that had nothing to read before it
        # ran -- before_content is None, not an error.
        event = core.build_edit_event(
            file_path="/no/such/path", before_content=None, tool_name="Write",
            tool_use_id="toolu_2", session_id="sess_1", cwd="/repo",
            ts_start=1.0, ts_end=2.0, tool_response={"success": True},
        )
        self.assertIsNone(event["before_content"])
        self.assertIsNone(event["after_content"])  # file still doesn't exist in this test

    def test_missing_tool_response_is_none_not_a_crash(self):
        event = core.build_edit_event(
            file_path="/no/such/path", before_content=None, tool_name="Edit",
            tool_use_id="toolu_3", session_id=None, cwd="/repo",
            ts_start=1.0, ts_end=2.0, tool_response=None,
        )
        self.assertIsNone(event["tool_reported_success"])


class TestBuildBashEvent(unittest.TestCase):
    def test_joins_stdout_and_stderr_into_one_output(self):
        event = core.build_bash_event(
            command="echo hi", tool_use_id="toolu_4", session_id="sess_1",
            cwd="/repo", ts_start=1.0, ts_end=1.5,
            tool_response={"stdout": "hi\n", "stderr": "", "interrupted": False, "isImage": False},
        )
        self.assertEqual(event["bash_command"], "echo hi")
        self.assertEqual(event["bash_output"], "hi\n")
        self.assertIsNone(event["file_path"])

    def test_success_is_always_none_bash_has_no_such_field(self):
        # Bash's own Output object has no `success` field at all -- confirmed
        # in custody's README, not guessed -- so this must never invent one.
        event = core.build_bash_event(
            command="rm -rf /tmp/x", tool_use_id="toolu_5", session_id="sess_1",
            cwd="/repo", ts_start=1.0, ts_end=1.5, tool_response={"stdout": "", "stderr": ""},
        )
        self.assertIsNone(event["tool_reported_success"])

    def test_no_output_is_none_not_empty_string(self):
        event = core.build_bash_event(
            command="true", tool_use_id="toolu_6", session_id="sess_1",
            cwd="/repo", ts_start=1.0, ts_end=1.5, tool_response=None,
        )
        self.assertIsNone(event["bash_output"])


if __name__ == "__main__":
    unittest.main()
