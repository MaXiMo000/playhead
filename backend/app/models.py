"""The `events` table -- one row per Edit/Write/Bash tool call, matching the
JSON schema playhead_hook.core builds and playhead-sync uploads verbatim."""
from __future__ import annotations

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Unique, not just indexed: playhead-sync retries a file that failed to
    # upload, so the same tool_use_id can arrive twice -- the API must be
    # safe to call again with the same event, not just fast the first time.
    tool_use_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    session_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    tool_name: Mapped[str] = mapped_column(String)
    ts_start: Mapped[float] = mapped_column(Float)
    ts_end: Mapped[float] = mapped_column(Float)
    cwd: Mapped[str | None] = mapped_column(String, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    before_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    bash_command: Mapped[str | None] = mapped_column(Text, nullable=True)
    bash_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_reported_success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    received_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
