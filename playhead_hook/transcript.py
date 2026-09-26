"""Rebuild Playhead events from a Claude Code session transcript.

The hook only records sessions that ran with it installed. Every Claude
Code session is also written to a transcript -- one JSON record per line
under ~/.claude/projects/<project>/<session-id>.jsonl -- and that has
what Playhead needs: each Edit/Write/Bash call as an assistant `tool_use`
block (its inputs, a timestamp), and its result as a later `tool_result`
record whose `toolUseResult` is the same payload the hook receives
(`originalFile` for Edit/Write, stdout/stderr for Bash). So a session
from last week can be replayed without having had the hook installed.

What a transcript can't give: the file's bytes on disk after the call.
The after-content here is what the tool reported writing (Write's
`content`, or Edit's replacement applied to `originalFile`), not a fresh
read -- the file has usually changed again since.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import pathlib
import re
import sys

from .core import MAX_CONTENT_BYTES

SHELLS = {"Bash", "PowerShell"}
TOOLS = {"Edit", "Write", "MultiEdit"} | SHELLS


def _ts(value) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _cap(text):
    if not isinstance(text, str) or len(text.encode("utf-8", errors="replace")) > MAX_CONTENT_BYTES:
        return None
    return text


def _apply_edits(original: str | None, edits: list) -> str | None:
    if not isinstance(original, str):
        return None
    text = original
    for e in edits:
        old, new = e.get("old_string"), e.get("new_string")
        if not isinstance(old, str) or not isinstance(new, str) or old not in text:
            return None  # can't reproduce what the tool did; don't pretend to
        text = text.replace(old, new, -1 if e.get("replace_all") else 1)
    return text


def events_from_transcript(lines) -> list[dict]:
    """Every Edit/Write/MultiEdit/Bash call in a transcript, as Playhead
    events, in the order they were made."""
    calls: dict[str, dict] = {}
    order: list[str] = []
    for line in lines:
        try:
            record = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue
        message = record.get("message") or {}
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use" and block.get("name") in TOOLS:
                calls[block["id"]] = {"use": block, "record": record, "result": None, "result_record": None}
                order.append(block["id"])
            elif block.get("type") == "tool_result" and block.get("tool_use_id") in calls:
                call = calls[block["tool_use_id"]]
                call["result"], call["result_record"] = block, record

    events = []
    for tool_use_id in order:
        call = calls[tool_use_id]
        use, record = call["use"], call["record"]
        name, inputs = use["name"], use.get("input") or {}
        result_record = call["result_record"] or {}
        tur = result_record.get("toolUseResult")
        tur = tur if isinstance(tur, dict) else {}
        start = _ts(record.get("timestamp"))
        end = _ts(result_record.get("timestamp")) or start
        if start is None:
            continue
        # The result block's is_error is the tool's own success claim. No
        # result at all (an interrupted session) is unknown, not success.
        success = None if call["result"] is None else not call["result"].get("is_error", False)
        event = {
            "session_id": record.get("sessionId"), "tool_use_id": tool_use_id,
            "tool_name": "Edit" if name == "MultiEdit" else name,
            "ts_start": start, "ts_end": end, "cwd": record.get("cwd"),
            "file_path": None, "before_content": None, "after_content": None,
            "bash_command": None, "bash_output": None, "tool_reported_success": success,
        }
        if name in SHELLS:
            event["bash_command"] = inputs.get("command")
            output = "\n".join(p for p in (tur.get("stdout"), tur.get("stderr")) if p) or None
            event["bash_output"] = _cap(output)
        else:
            original = tur.get("originalFile")
            event["file_path"] = inputs.get("file_path")
            event["before_content"] = _cap(original)
            if name == "Write":
                event["after_content"] = _cap(inputs.get("content"))
            elif success:
                edits = inputs.get("edits") if name == "MultiEdit" else [inputs]
                event["after_content"] = _cap(_apply_edits(original, edits or []))
        events.append(event)
    return events


def project_dir(cwd: str, home: pathlib.Path | None = None) -> pathlib.Path:
    """Where Claude Code keeps a project's transcripts: every character of
    the project path that isn't a letter or digit becomes '-'
    (C:\\Users\\me\\app -> C--Users-me-app, /home/me/app -> -home-me-app)."""
    home = home or pathlib.Path.home()
    return home / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", cwd)


def spool(events: list[dict], cwd: str) -> int:
    """Write events where the hook would have, for playhead-sync to upload.
    Keyed by tool_use_id, so importing a session twice doesn't duplicate it
    (and the backend is idempotent on tool_use_id too)."""
    out = pathlib.Path(cwd) / ".playhead" / "events"
    out.mkdir(parents=True, exist_ok=True)
    for event in events:
        (out / f"{event['tool_use_id']}.json").write_text(json.dumps(event), encoding="utf-8")
    return len(events)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="playhead-import",
        description="Rebuild Playhead events from Claude Code session transcripts.")
    parser.add_argument("transcripts", nargs="*", help="transcript .jsonl files")
    which = parser.add_mutually_exclusive_group()
    which.add_argument("--latest", action="store_true",
                       help="this project's most recent session")
    which.add_argument("--all", action="store_true", help="every session of this project")
    parser.add_argument("--sync", action="store_true",
                        help="upload right away (same as running playhead-sync after)")
    args = parser.parse_args(argv)

    cwd = os.getcwd()
    paths = [pathlib.Path(p) for p in args.transcripts]
    if args.latest or args.all:
        found = sorted(project_dir(cwd).glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
        if not found:
            print(f"playhead-import: no transcripts for this project in {project_dir(cwd)}",
                  file=sys.stderr)
            return 1
        paths = found[-1:] if args.latest else found
    if not paths:
        parser.error("give transcript files, --latest, or --all")

    total = 0
    for path in paths:
        try:
            with open(path, encoding="utf-8") as f:
                events = events_from_transcript(f)
        except OSError as exc:
            print(f"playhead-import: {path}: {exc}", file=sys.stderr)
            return 1
        total += spool(events, cwd)
        print(f"{path.name}: {len(events)} event(s)")
    print(f"playhead-import: {total} event(s) spooled to .playhead/events/")
    if args.sync:
        from .sync import DEFAULT_API_URL, sync_once
        sent, failed = sync_once(cwd, os.environ.get("PLAYHEAD_API_URL", DEFAULT_API_URL),
                                 os.environ.get("PLAYHEAD_API_KEY"))
        print(f"playhead-sync: {sent} event(s) sent, {failed} failed")
        return 1 if failed else 0
    print("run playhead-sync to upload them")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
