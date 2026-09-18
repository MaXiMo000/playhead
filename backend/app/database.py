"""Engine/session setup.

Defaults to a local SQLite file so the API runs with zero setup while
building the frontend against it. Set DATABASE_URL to a real Postgres DSN
(e.g. postgresql+psycopg2://user:pass@localhost/playhead) for anything past
solo local development -- the schema in models.py is plain SQLAlchemy, no
SQLite-only or Postgres-only types, so the switch is just the env var.
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./playhead.db")

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
