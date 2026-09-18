"""Run: python -m pytest backend/tests  (or python tests/test_anomaly.py from backend/)

Pure string logic, no filesystem, no DB -- mirrors the pure/impure split
used throughout this project's other test suites.
"""
from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from app.anomaly import is_out_of_scope


class TestIsOutOfScope(unittest.TestCase):
    def test_file_inside_cwd_is_in_scope(self):
        self.assertFalse(is_out_of_scope("/repo", "/repo/src/auth.py", "Edit"))

    def test_file_outside_cwd_is_out_of_scope(self):
        self.assertTrue(is_out_of_scope("/repo", "/etc/passwd", "Edit"))

    def test_sibling_directory_with_shared_prefix_is_out_of_scope(self):
        # "/repo-old" starts with "/repo" as a raw string, but it is not
        # actually inside "/repo" -- the trailing-slash check exists
        # specifically to avoid this false negative.
        self.assertTrue(is_out_of_scope("/repo", "/repo-old/auth.py", "Edit"))

    def test_cwd_itself_is_in_scope(self):
        self.assertFalse(is_out_of_scope("/repo", "/repo", "Write"))

    def test_windows_paths_with_mixed_separators(self):
        self.assertFalse(is_out_of_scope("C:\\repo", "C:\\repo\\src\\auth.py", "Edit"))
        self.assertTrue(is_out_of_scope("C:\\repo", "C:\\Windows\\System32\\config.sys", "Edit"))

    def test_case_insensitive_on_windows_style_paths(self):
        self.assertFalse(is_out_of_scope("C:\\Repo", "c:\\repo\\auth.py", "Edit"))

    def test_bash_is_never_flagged_no_declared_scope_exists(self):
        self.assertFalse(is_out_of_scope("/repo", "/etc/passwd", "Bash"))

    def test_missing_cwd_or_file_path_is_not_guessed_as_anomalous(self):
        self.assertFalse(is_out_of_scope(None, "/etc/passwd", "Edit"))
        self.assertFalse(is_out_of_scope("/repo", None, "Edit"))


if __name__ == "__main__":
    unittest.main()
