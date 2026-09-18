"""The one dumb heuristic from the plan: a file touched outside the
session's own working directory is worth flagging. Pure string logic, not
os.path -- these paths describe the *client* machine's filesystem (whatever
OS the Claude Code session ran on), and the backend may run on a different
OS entirely, so os.path.abspath()/normpath() would silently reinterpret
them against the wrong filesystem context.
"""
from __future__ import annotations


def _normalize(path: str) -> str:
    # Case-folded because Windows paths are case-insensitive: matching
    # case-sensitively would produce false positives for a session that
    # happens to differ only in case from its own cwd. A false negative
    # (missing a real out-of-scope touch) is the safer direction for a
    # heuristic that must never guess -- see custody's own precedent for
    # preferring "unverified" over a confident wrong answer.
    return path.replace("\\", "/").rstrip("/").lower()


def is_out_of_scope(cwd: str | None, file_path: str | None, tool_name: str) -> bool:
    """Edit/Write only. Bash gets no declared scope at all -- the same
    floor custody uses for it -- so it is never flagged here: observed,
    not judged. Missing cwd or file_path means there's nothing to compare
    against, so this returns False (unflagged) rather than guessing."""
    if tool_name not in ("Edit", "Write"):
        return False
    if not cwd or not file_path:
        return False

    cwd_n = _normalize(cwd)
    file_n = _normalize(file_path)
    return not (file_n == cwd_n or file_n.startswith(cwd_n + "/"))
