#!/usr/bin/env python3
"""Expose the Headroom monitoring dashboard on the requested LAN address."""
from aiohttp import ClientError, ClientSession, ClientTimeout, web

READ_PATHS = {"/dashboard", "/dashboard/", "/stats", "/stats-lifetime",
              "/stats-history", "/health", "/transformations/feed"}
STATIC_PATHS = {"/dashboard/static/alpine.min.js", "/dashboard/static/tailwind.min.js"}


async def session_context(app):
    async with ClientSession(timeout=ClientTimeout(total=30), trust_env=False) as session:
        app["upstream"] = session
        yield


async def dashboard(request):
    if request.method not in {"GET", "HEAD"}:
        raise web.HTTPMethodNotAllowed(request.method, ["GET", "HEAD"])
    if request.path == "/":
        raise web.HTTPFound("/dashboard")
    if request.path not in READ_PATHS | STATIC_PATHS:
        raise web.HTTPForbidden(text="This LAN endpoint provides the Headroom monitoring dashboard only.\n")
    url = "http://127.0.0.1:8787" + request.path_qs
    try:
        async with request.app["upstream"].get(url, allow_redirects=False) as response:
            body = await response.read()
            headers = {name: response.headers[name] for name in
                       ("Content-Type", "Cache-Control", "ETag", "Last-Modified")
                       if name in response.headers}
            headers["X-Content-Type-Options"] = "nosniff"
            headers["X-Frame-Options"] = "DENY"
            return web.Response(status=response.status, body=body, headers=headers)
    except (ClientError, OSError, TimeoutError) as exc:
        raise web.HTTPServiceUnavailable(text="Headroom is starting. Please retry shortly.\n") from exc


if __name__ == "__main__":
    app = web.Application()
    app.cleanup_ctx.append(session_context)
    app.router.add_route("*", "/{path:.*}", dashboard)
    web.run_app(app, host="172.30.10.101", port=8787)
