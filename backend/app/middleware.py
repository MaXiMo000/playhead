"""Two small, deliberately dumb middlewares -- neither needs a library.

MAX_BODY_BYTES exists because an /events POST carries a tool call's full
before/after file content: the hook already caps that at 2MB on its own
side (playhead_hook.core.MAX_CONTENT_BYTES), but the API must not trust a
client-side cap it doesn't control -- anyone can POST directly. Checked via
Content-Length, which every normal HTTP client sends; it will not catch a
chunked-transfer request with no declared length, but combined with rate
limiting that's a narrow, low-value gap, not the main threat this closes.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

MAX_BODY_BYTES = 5 * 1024 * 1024  # 5MB -- generous for one event's before/after content


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_BODY_BYTES:
            return JSONResponse(status_code=413, content={"detail": "request body too large"})
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response
