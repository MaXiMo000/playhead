"""Uploads spooled events from `.playhead/events/` to the Playhead backend.

Deliberately separate from hook.py: the hook must never make a network call
(it runs synchronously inside the agent's turn), so uploading happens later,
on demand, run by a human or a scheduled task -- not by the hook itself.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

import requests

DEFAULT_API_URL = "http://localhost:8000"


def _events_dir(cwd: str) -> pathlib.Path:
    return pathlib.Path(cwd) / ".playhead" / "events"


def _sent_dir(cwd: str) -> pathlib.Path:
    return pathlib.Path(cwd) / ".playhead" / "sent"


def sync_once(cwd: str, api_url: str) -> tuple[int, int]:
    """Uploads every event file in `.playhead/events/`, moving each to
    `.playhead/sent/` on a 2xx response. Returns (sent_count, failed_count).
    A file that fails to upload is left in place -- the next run retries it,
    rather than the event being silently dropped."""
    events_dir = _events_dir(cwd)
    if not events_dir.exists():
        return 0, 0

    sent_dir = _sent_dir(cwd)
    sent, failed = 0, 0

    for event_path in sorted(events_dir.glob("*.json")):
        try:
            payload = json.loads(event_path.read_text())
            response = requests.post(f"{api_url}/events", json=payload, timeout=10)
            response.raise_for_status()
        except (requests.RequestException, json.JSONDecodeError) as exc:
            sys.stderr.write(f"playhead-sync: failed to send {event_path.name}: {exc}\n")
            failed += 1
            continue

        sent_dir.mkdir(parents=True, exist_ok=True)
        event_path.rename(sent_dir / event_path.name)
        sent += 1

    return sent, failed


def main() -> int:
    cwd = os.getcwd()
    api_url = os.environ.get("PLAYHEAD_API_URL", DEFAULT_API_URL)
    sent, failed = sync_once(cwd, api_url)
    print(f"playhead-sync: {sent} event(s) sent, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
