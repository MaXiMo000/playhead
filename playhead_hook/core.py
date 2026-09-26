"""Pure event-shaping logic for one tool-call event.

No stdin/stdout -- hook.py does that glue. This module only turns
already-gathered before/after facts into the JSON event Playhead's backend
expects, so it can be tested with plain strings and dicts, the same split
custody's core.py uses.
"""
from __future__ import annotations

import pathlib

# A generated file or a huge log dump isn't something the diff-theater UI
# needs verbatim -- past this size the content is dropped, not truncated
# silently mid-line, so the frontend can render an explicit "too large to
# display" state instead of a corrupted diff.
MAX_CONTENT_BYTES = 2_000_000


def read_file_text(path: str) -> str | None:
    """The file's text content, or None if it doesn't exist, is binary, or
    exceeds MAX_CONTENT_BYTES. A `Write` call can create a file that had
    nothing to read before it ran, so None is a normal, expected result,
    not an error."""
    p = pathlib.Path(path)
    if not p.exists():
        return None
    try:
        data = p.read_bytes()
    except OSError:
        return None
    if len(data) > MAX_CONTENT_BYTES:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def build_edit_event(*, file_path: str, before_content: str | None, tool_name: str,
                      tool_use_id: str, session_id: str | None, cwd: str,
                      ts_start: float, ts_end: float, tool_response) -> dict:
    """Edit/Write: the after-content is read fresh here (post-call), the
    before-content was captured by hook.py's PreToolUse handler before the
    call ran -- that's the one fact that can't be reconstructed later."""
    after_content = read_file_text(file_path)
    # Claude Code only sends PostToolUse after a tool succeeded (failures are
    # PostToolUseFailure), and real Edit/Write responses carry no `success`
    # field -- measured live. Reading .get("success") left every event None.
    tool_success = tool_response.get("success", True) if isinstance(tool_response, dict) else None
    return {
        "session_id": session_id, "tool_use_id": tool_use_id, "tool_name": tool_name,
        "ts_start": ts_start, "ts_end": ts_end, "cwd": cwd, "file_path": file_path,
        "before_content": before_content, "after_content": after_content,
        "bash_command": None, "bash_output": None,
        "tool_reported_success": tool_success,
    }


def build_bash_event(*, command: str | None, tool_use_id: str, session_id: str | None,
                     tool_name: str = "Bash",
                      cwd: str, ts_start: float, ts_end: float, tool_response) -> dict:
    """Bash's own Output object has no `success` field at all -- it's
    {stdout, stderr, interrupted, isImage} (the same shape custody's README
    documents) -- so tool_reported_success is always None here, by design,
    not a gap."""
    if isinstance(tool_response, dict):
        stdout = tool_response.get("stdout")
        stderr = tool_response.get("stderr")
    else:
        stdout = stderr = None
    output = "\n".join(part for part in (stdout, stderr) if part) or None
    return {
        "session_id": session_id, "tool_use_id": tool_use_id, "tool_name": tool_name,
        "ts_start": ts_start, "ts_end": ts_end, "cwd": cwd, "file_path": None,
        "before_content": None, "after_content": None,
        "bash_command": command, "bash_output": output,
        "tool_reported_success": None,
    }
