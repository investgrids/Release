"""
Keep crawlers off the API host.

The backend is an API: nothing under /api/ is meant to be indexed, and crawlers that find it (Bingbot was seen walking /api/events/* and /api/intelligence/event/*) cost real egress and CPU on uncached
detail endpoints. Two layers, both cheap:
  * GET /robots.txt  -> Disallow everything except /api/media/
  * X-Robots-Tag: noindex, nofollow on every response except /api/media/

/api/media/ is exempt on purpose: article hero images live there and are referenced by the site's pages and og:image tags, so search image indexing and social previews must keep working.
The header is added by a pure ASGI wrapper (not BaseHTTPMiddleware) so streaming responses (the SSE endpoints) are passed through untouched.
"""
from __future__ import annotations

ROBOTS_TXT = "User-agent: *\nAllow: /api/media/\nDisallow: /\n"
_EXEMPT_PREFIXES = ("/api/media/",)
_HEADER = (b"x-robots-tag", b"noindex, nofollow, noarchive")


class RobotsHeaderMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path", "").startswith(_EXEMPT_PREFIXES):
            return await self.app(scope, receive, send)

        async def send_with_header(message):
            if message["type"] == "http.response.start":
                headers = [h for h in message.get("headers", []) if h[0].lower() != _HEADER[0]]
                headers.append(_HEADER)
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_header)
