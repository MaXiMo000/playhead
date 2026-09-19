"""API-key auth, in proportion to what this project actually is: a
single-user personal tool, not a multi-tenant product. A shared bearer
token is the right amount of security for that threat model -- it stops
an opportunistic scanner or bot from reading or writing your session data
if this ever ends up reachable from the network. It is NOT a defense
against a targeted attacker who can read the frontend bundle (the key
ships in it, necessarily, since there is no login system) -- a real
multi-user product would need actual authentication, which is out of
scope for what this project is.

Fails open, loudly, only when PLAYHEAD_API_KEY is unset -- that's the
localhost-demo case, and it's better to run open-with-a-warning than to
force every local `npm run dev` to first go set up a key it doesn't need.
The moment the key is set, every non-health endpoint enforces it.
"""
from __future__ import annotations

import os
import sys

from fastapi import Header, HTTPException, status

API_KEY = os.environ.get("PLAYHEAD_API_KEY")

if not API_KEY:
    print(
        "playhead: WARNING -- PLAYHEAD_API_KEY is not set. Every endpoint is "
        "open to anyone who can reach this server. Fine for a localhost demo, "
        "never for anything reachable over a network. Set PLAYHEAD_API_KEY "
        "(and the same value as PLAYHEAD_API_KEY for playhead-sync, and "
        "VITE_API_KEY for the frontend) to lock this down.",
        file=sys.stderr,
    )


async def verify_api_key(authorization: str | None = Header(default=None)) -> None:
    if not API_KEY:
        return  # explicitly unlocked -- warned loudly at import time above
    if authorization != f"Bearer {API_KEY}":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or missing API key")
