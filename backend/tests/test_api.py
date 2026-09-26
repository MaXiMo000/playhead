"""The events API through FastAPI's TestClient, against a throwaway SQLite
database (DATABASE_URL is read at import, so it's set first)."""
from __future__ import annotations

import os
import tempfile

_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_db.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_db.name}"
os.environ.pop("PLAYHEAD_API_KEY", None)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import MAX_BATCH, app  # noqa: E402

client = TestClient(app)


def _event(i: int, session: str = "s-api", **extra) -> dict:
    return {"session_id": session, "tool_use_id": f"{session}-{i}", "tool_name": "Edit",
            "ts_start": 1000.0 + i, "ts_end": 1001.0 + i, "cwd": "/repo",
            "file_path": "/repo/a.py", "before_content": "a", "after_content": "b",
            "tool_reported_success": True, **extra}


def test_single_event_is_idempotent():
    first = client.post("/events", json=_event(0, "s-single"))
    again = client.post("/events", json=_event(0, "s-single"))
    assert first.status_code == 201 and again.status_code == 201
    assert first.json()["id"] == again.json()["id"]


def test_batch_creates_skips_existing_and_in_batch_duplicates():
    events = [_event(i, "s-batch") for i in range(5)]
    assert client.post("/events/batch", json=events).json() == {"created": 5, "existing": 0}
    replay = events[:3] + [_event(9, "s-batch"), _event(9, "s-batch")]
    assert client.post("/events/batch", json=replay).json() == {"created": 1, "existing": 4}
    sessions = {s["session_id"]: s["event_count"] for s in client.get("/sessions").json()}
    assert sessions["s-batch"] == 6


def test_batch_flags_out_of_scope_files_like_the_single_endpoint():
    client.post("/events/batch", json=[_event(0, "s-scope", file_path="/home/me/.ssh/config")])
    events = client.get("/sessions/s-scope/events").json()
    assert events[0]["is_anomalous"] is True


def test_batch_size_is_capped():
    too_many = [_event(i, "s-big") for i in range(MAX_BATCH + 1)]
    assert client.post("/events/batch", json=too_many).status_code == 413
