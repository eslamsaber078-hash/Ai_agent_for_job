"""Transport-level hardening: response headers, body limits and a write throttle.

All three are pure ASGI middleware. The function-based Starlette version spins up a
task group per request, which the load tests showed doubles the task count and starves
the thread pool — the same reason ``PrivateResponses`` in main.py is hand-written.
"""
from __future__ import annotations

import time
from collections import deque
from threading import Lock

from fastapi.responses import JSONResponse

from . import config

_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    # React writes width percentages through style attributes; style attributes are
    # governed by style-src, and the app has no inline <style> blocks beyond that.
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)
_HSTS = "max-age=31536000; includeSubDomains"

_STRIP_HEADERS = {b"server", b"x-powered-by"}
_SAFE_HEADERS = {
    b"x-content-type-options": b"nosniff",
    b"x-frame-options": b"DENY",
    b"referrer-policy": b"strict-origin-when-cross-origin",
    b"permissions-policy": b"camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    b"cross-origin-opener-policy": b"same-origin",
    b"cross-origin-resource-policy": b"same-origin",
    b"content-security-policy": _CSP.encode("latin-1"),
}


class SecurityHeaders:
    """Browser-side protections on every response, static assets included.

    Clickjacking (frame-ancestors + X-Frame-Options), MIME sniffing, referrer
    leakage, and feature access are all closed here. HSTS is added only when the
    request actually arrived over HTTPS, so local HTTP development still works.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = [(k, v) for k, v in message.get("headers", [])
                           if k.lower() not in _STRIP_HEADERS]
                have = {k.lower() for k, _ in headers}
                for name, value in _SAFE_HEADERS.items():
                    if name not in have:
                        headers.append((name, value))
                if scope.get("scheme") == "https" and b"strict-transport-security" not in have:
                    headers.append((b"strict-transport-security", _HSTS.encode("latin-1")))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)


class BodySizeLimit:
    """Reject an oversized request before its body is buffered in memory.

    Auth bodies already had their own 8 KB cap; every other JSON endpoint accepted
    whatever a client sent, so one large POST could balloon the worker's memory. A
    browser always sends Content-Length, and a request without one is refused rather
    than streamed unchecked — chunked uploads are not part of this API.
    """

    def __init__(self, app):
        self.app = app
        self.default = config.API_BODY_LIMIT_BYTES
        # The resume upload is the one legitimately large body: its own endpoint
        # enforces MAX_RESUME_SIZE_MB, and multipart framing needs a little room.
        self.overrides = {
            "/api/profile/resume": config.MAX_RESUME_SIZE_MB * 1024 * 1024 + 512 * 1024,
        }

    def _limit_for(self, path: str) -> int:
        for prefix, limit in self.overrides.items():
            if path == prefix or path.startswith(prefix + "/"):
                return limit
        return self.default

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        if not path.startswith("/api/"):
            await self.app(scope, receive, send)
            return

        limit = self._limit_for(path)
        length = None
        for key, value in scope.get("headers", []):
            if key.lower() == b"content-length":
                try:
                    length = int(value)
                except ValueError:
                    length = -1
                break

        if length is not None and length < 0:
            await _refuse(scope, receive, send, 400, "Invalid Content-Length")
            return
        if scope.get("method") in {"POST", "PUT", "PATCH"} and length is None:
            await _refuse(scope, receive, send, 411, "Content-Length is required")
            return
        if length is not None and length > limit:
            await _refuse(scope, receive, send, 413, "Request body is too large")
            return

        if length is None:
            # No advertised size (DELETE is the only body-bearing method left here):
            # count as the body streams and cut the connection at the limit, so the
            # worker still never buffers more than that.
            received = 0

            async def limited_receive():
                nonlocal received
                message = await receive()
                if message["type"] == "http.request":
                    received += len(message.get("body", b""))
                    if received > limit:
                        return {"type": "http.disconnect"}
                return message

            await self.app(scope, limited_receive, send)
            return

        await self.app(scope, receive, send)


class WriteThrottle:
    """A per-client ceiling on writes, so one session cannot flood the database.

    Reads are left alone: they are what the load tests and the page loads depend on.
    Login and registration keep their own stricter limiter. The bucket count is
    bounded, so a spoofed stream of client addresses cannot grow memory forever.
    """

    WINDOW_SECONDS = 60.0
    MAX_BUCKETS = 4096

    def __init__(self, app, limit: int | None = None):
        self.app = app
        self.limit = config.API_WRITE_LIMIT_PER_MINUTE if limit is None else limit
        self._lock = Lock()
        self._buckets: dict[str, deque[float]] = {}

    async def __call__(self, scope, receive, send):
        if (scope["type"] != "http" or self.limit <= 0
                or scope.get("method") not in {"POST", "PUT", "PATCH", "DELETE"}):
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        if not path.startswith("/api/") or path.startswith("/api/auth/"):
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        key = client[0] if client else "unknown"
        now = time.monotonic()
        cutoff = now - self.WINDOW_SECONDS
        with self._lock:
            for stale_key, attempts in list(self._buckets.items()):
                while attempts and attempts[0] <= cutoff:
                    attempts.popleft()
                if not attempts:
                    del self._buckets[stale_key]
            bucket = self._buckets.get(key)
            if bucket is None:
                if len(self._buckets) >= self.MAX_BUCKETS:
                    allowed, retry_after = False, 30
                else:
                    self._buckets[key] = deque([now])
                    allowed, retry_after = True, 0
            else:
                allowed = len(bucket) < self.limit
                if allowed:
                    bucket.append(now)
                    retry_after = 0
                else:
                    retry_after = max(1, int(bucket[0] + self.WINDOW_SECONDS - now) + 1)

        if not allowed:
            await _refuse(scope, receive, send, 429, "Too many requests. Wait a moment and try again.",
                          retry_after=retry_after)
            return
        await self.app(scope, receive, send)


async def _refuse(scope, receive, send, status: int, detail: str,
                  retry_after: int | None = None) -> None:
    headers = {"Retry-After": str(retry_after)} if retry_after is not None else None
    response = JSONResponse(status_code=status, content={"detail": detail}, headers=headers)
    await response(scope, receive, send)
