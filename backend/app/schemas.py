"""Pydantic models mirroring playhead_hook.core's event shape exactly --
the hook and the API must agree on this schema without either importing
the other (the hook ships as a separate pip package with no FastAPI/DB
dependency)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EventIn(BaseModel):
    session_id: str | None = None
    tool_use_id: str
    tool_name: str
    ts_start: float
    ts_end: float
    cwd: str | None = None
    file_path: str | None = None
    before_content: str | None = None
    after_content: str | None = None
    bash_command: str | None = None
    bash_output: str | None = None
    tool_reported_success: bool | None = None


class EventOut(EventIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    received_at: datetime


class SessionSummary(BaseModel):
    session_id: str
    event_count: int
    started_at: float
    ended_at: float
