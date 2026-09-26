"""playhead-import: events rebuilt from Claude Code transcript lines, in the
record shape real transcripts use (assistant tool_use blocks; user
tool_result blocks with a top-level toolUseResult)."""
from __future__ import annotations

import json
import pathlib

from playhead_hook.transcript import events_from_transcript, main, project_dir


def _use(uid, name, inputs, ts="2026-09-24T15:58:09.142Z"):
    return json.dumps({"type": "assistant", "timestamp": ts, "sessionId": "s1", "cwd": "/repo",
                       "message": {"role": "assistant", "content": [
                           {"type": "tool_use", "id": uid, "name": name, "input": inputs}]}})


def _result(uid, tur, is_error=False, ts="2026-09-24T15:58:10.642Z"):
    return json.dumps({"type": "user", "timestamp": ts, "sessionId": "s1", "cwd": "/repo",
                       "toolUseResult": tur,
                       "message": {"role": "user", "content": [
                           {"type": "tool_result", "tool_use_id": uid, "is_error": is_error,
                            "content": "ok"}]}})


LINES = [
    json.dumps({"type": "user", "message": {"role": "user", "content": "fix the bug"}}),
    _use("t1", "Edit", {"file_path": "/repo/a.py", "old_string": "x = 1", "new_string": "x = 2",
                        "replace_all": False}),
    _result("t1", {"filePath": "/repo/a.py", "originalFile": "x = 1\ny = 1\n", "structuredPatch": []}),
    _use("t2", "Write", {"file_path": "/repo/new.py", "content": "print('hi')\n"}),
    _result("t2", {"type": "create", "filePath": "/repo/new.py", "content": "print('hi')\n",
                   "originalFile": None}),
    _use("t3", "Bash", {"command": "pytest -q", "description": "run tests"}),
    _result("t3", {"stdout": "2 passed", "stderr": "", "interrupted": False, "isImage": False}),
    _use("t4", "Edit", {"file_path": "/repo/a.py", "old_string": "nope", "new_string": "z"}),
    _result("t4", "Error: String to replace not found in file.", is_error=True),
    _use("t5", "Read", {"file_path": "/repo/a.py"}),  # not a tool Playhead tracks
    _use("t6", "MultiEdit", {"file_path": "/repo/b.py", "edits": [
        {"old_string": "a", "new_string": "A"}, {"old_string": "b", "new_string": "B", "replace_all": True}]}),
    _result("t6", {"filePath": "/repo/b.py", "originalFile": "a b b\n"}),
    _use("t7", "Bash", {"command": "sleep 999"}),  # interrupted: no result ever came back
    "not json at all",
]


def test_every_tracked_call_becomes_an_event_in_order():
    events = events_from_transcript(LINES)
    assert [e["tool_use_id"] for e in events] == ["t1", "t2", "t3", "t4", "t6", "t7"]
    assert all(e["session_id"] == "s1" for e in events)


def test_edit_before_and_after_come_from_the_transcript():
    edit = events_from_transcript(LINES)[0]
    assert edit["before_content"] == "x = 1\ny = 1\n"
    assert edit["after_content"] == "x = 2\ny = 1\n"
    assert edit["ts_end"] - edit["ts_start"] == 1.5
    assert edit["tool_reported_success"] is True


def test_write_bash_failure_multiedit_and_interrupted():
    by_id = {e["tool_use_id"]: e for e in events_from_transcript(LINES)}
    assert by_id["t2"]["before_content"] is None and by_id["t2"]["after_content"] == "print('hi')\n"
    assert by_id["t3"]["bash_command"] == "pytest -q" and by_id["t3"]["bash_output"] == "2 passed"
    assert by_id["t4"]["tool_reported_success"] is False and by_id["t4"]["after_content"] is None
    assert by_id["t6"]["tool_name"] == "Edit" and by_id["t6"]["after_content"] == "A B B\n"
    assert by_id["t7"]["tool_reported_success"] is None


def test_project_dir_matches_claude_codes_naming():
    home = pathlib.Path("/h")
    assert project_dir(r"C:\Users\me\app", home) == home / ".claude" / "projects" / "C--Users-me-app"
    assert project_dir("/home/me/my.app", home) == home / ".claude" / "projects" / "-home-me-my-app"


def test_cli_spools_events_for_playhead_sync(tmp_path, monkeypatch, capsys):
    transcript = tmp_path / "session.jsonl"
    transcript.write_text("\n".join(LINES), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert main([str(transcript)]) == 0
    spooled = sorted(p.stem for p in (tmp_path / ".playhead" / "events").glob("*.json"))
    assert spooled == ["t1", "t2", "t3", "t4", "t6", "t7"]
    assert main([str(transcript)]) == 0  # importing twice overwrites, never duplicates
    assert len(list((tmp_path / ".playhead" / "events").glob("*.json"))) == 6
    assert "6 event(s) spooled" in capsys.readouterr().out
