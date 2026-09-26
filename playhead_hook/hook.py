"""stdin/stdout glue for Claude Code's PreToolUse/PostToolUse hooks.

Reads the JSON Claude Code sends on stdin (see
https://docs.claude.com/en/docs/claude-code/hooks), captures the before/after
state of the tool's declared file (Edit, Write) or command (Bash), and writes
one event JSON per tool call to `.playhead/events/` -- purely local, no
network. A separate `playhead sync` command uploads these later; this hook
never makes a network call itself, since it runs synchronously inside the
agent's turn and must never add latency to it.

Never blocks a tool call and always exits 0 -- the same non-blocking, never-
crashes-the-session posture as custody's hook.
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

from . import core

# PowerShell is Claude Code's other shell tool, same input and output as
# Bash; 147 of the calls in one Windows machine's transcripts.
SHELLS = {"Bash", "PowerShell"}
WATCHED_TOOLS = {"Edit", "Write"} | SHELLS


def _state_dir(cwd: str) -> pathlib.Path:
    return pathlib.Path(cwd) / ".playhead" / "pending"


def _events_dir(cwd: str) -> pathlib.Path:
    return pathlib.Path(cwd) / ".playhead" / "events"


def pre_tool_use(event: dict) -> None:
    tool_name = event.get("tool_name")
    if tool_name not in WATCHED_TOOLS:
        return
    tool_use_id = event["tool_use_id"]
    cwd = event.get("cwd", ".")
    session_id = event.get("session_id")
    ts_start = time.time()

    if tool_name in ("Edit", "Write"):
        file_path = event["tool_input"]["file_path"]
        state = {
            "tool_name": tool_name, "file_path": file_path,
            "before_content": core.read_file_text(file_path),
            "session_id": session_id, "cwd": cwd, "ts_start": ts_start,
        }
    else:  # a shell
        command = event.get("tool_input", {}).get("command")
        state = {
            "tool_name": tool_name, "command": command,
            "session_id": session_id, "cwd": cwd, "ts_start": ts_start,
        }

    state_dir = _state_dir(cwd)
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / f"{tool_use_id}.json").write_text(json.dumps(state))


def post_tool_use(event: dict) -> None:
    tool_name = event.get("tool_name")
    if tool_name not in WATCHED_TOOLS:
        return
    tool_use_id = event["tool_use_id"]
    cwd = event.get("cwd", ".")
    state_path = _state_dir(cwd) / f"{tool_use_id}.json"

    if not state_path.exists():
        # A crash between the two hooks, or the hook being added mid-session
        # -- there's no before-state to pair with, and unlike custody (which
        # can still emit an "unverified" receipt from a hash alone) Playhead
        # has nothing meaningful to show on a timeline without a start point,
        # so this tool call is silently skipped rather than recorded half-empty.
        return

    state = json.loads(state_path.read_text())
    ts_end = time.time()
    tool_response = event.get("tool_response")

    if state["tool_name"] in ("Edit", "Write"):
        result = core.build_edit_event(
            file_path=state["file_path"], before_content=state["before_content"],
            tool_name=state["tool_name"], tool_use_id=tool_use_id,
            session_id=state["session_id"], cwd=state["cwd"],
            ts_start=state["ts_start"], ts_end=ts_end, tool_response=tool_response,
        )
    else:  # a shell
        result = core.build_bash_event(
            command=state["command"], tool_use_id=tool_use_id, tool_name=state["tool_name"],
            session_id=state["session_id"], cwd=state["cwd"],
            ts_start=state["ts_start"], ts_end=ts_end, tool_response=tool_response,
        )

    state_path.unlink(missing_ok=True)

    events_dir = _events_dir(cwd)
    events_dir.mkdir(parents=True, exist_ok=True)
    (events_dir / f"{tool_use_id}.json").write_text(json.dumps(result, indent=2))


_HANDLERS = {"PreToolUse": pre_tool_use, "PostToolUse": post_tool_use}


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"playhead-hook: could not parse hook input as JSON: {exc}\n")
        return 0
    handler = _HANDLERS.get(event.get("hook_event_name"))
    if handler:
        try:
            handler(event)
        except Exception as exc:  # noqa: BLE001 -- a hook that crashes must never break the agent's turn
            sys.stderr.write(f"playhead-hook: {type(exc).__name__}: {exc}\n")
    return 0  # never blocks: this is a witness, not a gate


if __name__ == "__main__":
    sys.exit(main())
