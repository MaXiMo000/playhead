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

# 127.0.0.1, not localhost: on Windows "localhost" tries IPv6 first and each
# new connection to an IPv4-only server waited ~2s (measured).
DEFAULT_API_URL = "http://127.0.0.1:8000"


def _events_dir(cwd: str) -> pathlib.Path:
    return pathlib.Path(cwd) / ".playhead" / "events"


def _sent_dir(cwd: str) -> pathlib.Path:
    return pathlib.Path(cwd) / ".playhead" / "sent"


# Under the backend's 5MB body cap and 100-event batch limit, with room to spare.
BATCH_EVENTS = 100
BATCH_BYTES = 4 * 1024 * 1024


def _batches(paths: list[pathlib.Path]):
    """(paths, payloads) groups that fit one /events/batch request. A single
    event bigger than the byte budget goes alone; the backend decides."""
    group, payloads, size = [], [], 0
    for path in paths:
        try:
            payload = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            print(f"playhead-sync: skipping unreadable {path.name}: {exc}", file=sys.stderr)
            continue
        n = len(json.dumps(payload))
        if group and (len(group) >= BATCH_EVENTS or size + n > BATCH_BYTES):
            yield group, payloads
            group, payloads, size = [], [], 0
        group.append(path)
        payloads.append(payload)
        size += n
    if group:
        yield group, payloads


def sync_once(cwd: str, api_url: str, api_key: str | None = None) -> tuple[int, int]:
    """Uploads every event file in `.playhead/events/`, moving each to
    `.playhead/sent/` once the backend has it. Returns (sent_count,
    failed_count). A file that fails to upload is left in place -- the next
    run retries it, rather than the event being silently dropped.

    Sends batches to /events/batch; against a backend that predates it
    (404), falls back to one POST /events per event."""
    events_dir = _events_dir(cwd)
    if not events_dir.exists():
        return 0, 0

    sent_dir = _sent_dir(cwd)
    sent, failed = 0, 0
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    batch_supported = True
    http = requests.Session()  # one connection for the whole upload

    def mark_sent(path: pathlib.Path) -> None:
        sent_dir.mkdir(parents=True, exist_ok=True)
        path.replace(sent_dir / path.name)

    for paths, payloads in _batches(sorted(events_dir.glob("*.json"))):
        if batch_supported:
            try:
                response = http.post(f"{api_url}/events/batch", json=payloads, headers=headers, timeout=30)
                if response.status_code == 404:
                    batch_supported = False
                else:
                    response.raise_for_status()
                    for path in paths:
                        mark_sent(path)
                    sent += len(paths)
                    continue
            except requests.RequestException as exc:
                print(f"playhead-sync: failed to send {len(paths)} event(s): {exc}", file=sys.stderr)
                failed += len(paths)
                continue
        for path, payload in zip(paths, payloads):
            try:
                response = http.post(f"{api_url}/events", json=payload, headers=headers, timeout=10)
                response.raise_for_status()
            except requests.RequestException as exc:
                print(f"playhead-sync: failed to send {path.name}: {exc}", file=sys.stderr)
                failed += 1
                continue
            mark_sent(path)
            sent += 1

    return sent, failed


def main() -> int:
    cwd = os.getcwd()
    api_url = os.environ.get("PLAYHEAD_API_URL", DEFAULT_API_URL)
    api_key = os.environ.get("PLAYHEAD_API_KEY")
    sent, failed = sync_once(cwd, api_url, api_key)
    print(f"playhead-sync: {sent} event(s) sent, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
