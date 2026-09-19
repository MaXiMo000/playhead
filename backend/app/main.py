from __future__ import annotations

import os

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models, schemas
from .anomaly import is_out_of_scope
from .database import Base, engine, get_db
from .middleware import MaxBodySizeMiddleware, SecurityHeadersMiddleware
from .security import verify_api_key

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Playhead API")

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(MaxBodySizeMiddleware)

# Real origin allowlist, not "*" -- set ALLOWED_ORIGINS (comma-separated) for
# any deployment beyond default local dev ports.
_default_origins = "http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173"
allowed_origins = os.environ.get("ALLOWED_ORIGINS", _default_origins).split(",")
app.add_middleware(
    CORSMiddleware, allow_origins=allowed_origins, allow_methods=["*"], allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/events", response_model=schemas.EventOut, status_code=201, dependencies=[Depends(verify_api_key)])
@limiter.limit("60/minute")
def create_event(request: Request, event: schemas.EventIn, db: Session = Depends(get_db)):
    # playhead-sync retries a file that failed to upload, so the same
    # tool_use_id can arrive twice -- this must be safe to call again with
    # the same event, returning the existing row rather than erroring.
    existing = db.scalar(select(models.Event).where(models.Event.tool_use_id == event.tool_use_id))
    if existing is not None:
        return existing

    row = models.Event(
        **event.model_dump(),
        is_anomalous=is_out_of_scope(event.cwd, event.file_path, event.tool_name),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@app.get("/sessions", response_model=list[schemas.SessionSummary], dependencies=[Depends(verify_api_key)])
def list_sessions(db: Session = Depends(get_db)):
    rows = db.execute(
        select(
            models.Event.session_id,
            func.count(models.Event.id).label("event_count"),
            func.min(models.Event.ts_start).label("started_at"),
            func.max(models.Event.ts_end).label("ended_at"),
        )
        .where(models.Event.session_id.is_not(None))
        .group_by(models.Event.session_id)
        .order_by(func.min(models.Event.ts_start).desc())
    ).all()
    return [
        schemas.SessionSummary(
            session_id=r.session_id, event_count=r.event_count,
            started_at=r.started_at, ended_at=r.ended_at,
        )
        for r in rows
    ]


@app.get(
    "/sessions/{session_id}/events",
    response_model=list[schemas.EventOut],
    dependencies=[Depends(verify_api_key)],
)
def session_events(session_id: str, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(models.Event)
        .where(models.Event.session_id == session_id)
        .order_by(models.Event.ts_start)
    ).all()
    if not rows:
        raise HTTPException(status_code=404, detail="no events for this session_id")
    return rows
