# The public-host guard: the one thing that makes the connector's public hostname
# safe. It runs before everything else (main.py) and decides from the address
# alone, before any route or file is looked at:
# - on the public hostname (MCP_HOST), only the connector's paths get through;
#   the page, /api/* and everything else is a bare 404;
# - on the home address, the connector's paths are a 404, so there's one way in.
# It holds even if the Cloudflare tunnel is set up wrong, and even with the
# connector turned off.

import re

from starlette.types import ASGIApp, Receive, Scope, Send

from ..config import get_settings

# The only paths the public hostname may reach.
PUBLIC_PATHS = re.compile(r"^/(mcp/?|oauth/(authorize|token|register)|\.well-known/oauth-[\w-]+(/.*)?)$")

# What the home address never answers: the connector lives on the public hostname only.
CONNECTOR_PATHS = re.compile(r"^/(mcp(/.*)?|oauth(/.*)?|\.well-known(/.*)?)$")

# Headers Cloudflare's tunnel adds to every request it brings in. Requests from
# the home network don't have them, so seeing one means "came from the internet",
# even if the tunnel was told to rewrite the Host header to the home one.
_FROM_CLOUDFLARE = (b"cf-ray", b"cf-connecting-ip")


def _hostname(value: bytes) -> str:
    """ "Agenda-MCP.graloop.com:443" -> "agenda-mcp.graloop.com"."""
    host = value.decode("latin-1").strip().lower()
    if host.startswith("["):  # an IPv6 address: [::1]:8000
        return host.split("]")[0] + "]"
    return host.split(":")[0]


def is_public(scope: Scope, mcp_host: str) -> bool:
    """Whether this request came in through the public hostname."""
    headers = dict(scope.get("headers") or [])
    if any(name in headers for name in _FROM_CLOUDFLARE):
        return True
    if not mcp_host:
        return False
    hosts = [headers.get(b"host", b""), headers.get(b"x-forwarded-host", b"")]
    return any(_hostname(h.split(b",")[0]) == mcp_host for h in hosts if h)


def allowed(scope: Scope, mcp_host: str) -> bool:
    path = scope.get("path", "")
    if is_public(scope, mcp_host):
        return bool(PUBLIC_PATHS.match(path))
    return not CONNECTOR_PATHS.match(path)


class PublicHostGuard:
    """ASGI middleware: answers a bare 404 to anything `allowed` refuses."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket") and not allowed(scope, get_settings().mcp_host):
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
                return
            # Nothing that says what's here or why: the same answer as an unknown address.
            await send(
                {
                    "type": "http.response.start",
                    "status": 404,
                    "headers": [(b"content-type", b"text/plain"), (b"content-length", b"9")],
                }
            )
            await send({"type": "http.response.body", "body": b"Not found"})
            return
        await self.app(scope, receive, send)
