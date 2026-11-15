# Who may call /mcp: a request with a valid access token, nothing else.
#
# BearerAuth wraps the MCP server (main.py). Without a valid token it answers
# 401 with a WWW-Authenticate header naming the metadata address: that header
# is how Claude finds the login page (oauth.py). There are no accounts, so a
# valid token simply means "the owner".
#
# Also here, because oauth.py needs the same answers: whether the connector is
# on, the public address, and how codes and tokens are hashed.

import datetime as dt
import hashlib
import logging

import anyio
from sqlalchemy import select
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ..config import get_settings
from ..database import SessionLocal
from ..models import McpToken

log = logging.getLogger("agenda.mcp")


def is_configured() -> bool:
    """Whether main.py mounts /mcp and the OAuth pages: on, and every setting it needs is right."""
    settings = get_settings()
    return settings.mcp_enabled and settings.mcp_problem() is None


def public_base() -> str:
    """ "https://agenda-mcp.graloop.com": always from MCP_HOST, never from the
    request's Host header, which the caller chooses."""
    return f"https://{get_settings().mcp_host}"


def now() -> dt.datetime:
    """Local time without a timezone, like every date the app stores."""
    return dt.datetime.now().replace(microsecond=0)


def expiry(**delta) -> dt.datetime:
    """A moment from now, for expires_at: expiry(minutes=5)."""
    return now() + dt.timedelta(**delta)


def token_hash(value: str) -> str:
    """What's stored instead of a code or token. They're long random strings, so a plain hash is enough."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def password_mark() -> str:
    """A short fingerprint of the current MCP_PASSWORD_HASH (not of the password).
    Stored with each code and token; a new password changes it, which signs Claude out."""
    return hashlib.sha256(get_settings().mcp_password_hash.encode("utf-8")).hexdigest()[:16]


def live_token(db, value: str, kind: str) -> McpToken | None:
    """The stored token if it still works: right kind, not expired or replaced,
    and made under the current password."""
    row = db.scalar(
        select(McpToken).where(
            McpToken.token_hash == token_hash(value),
            McpToken.kind == kind,
            McpToken.revoked_at.is_(None),
            McpToken.expires_at > now(),
        )
    )
    if row is None or row.password_mark != password_mark():
        return None
    return row


def _is_valid_access(token: str) -> bool:
    with SessionLocal() as db:
        return live_token(db, token, "access") is not None


def no_store(send: Send) -> Send:
    """Wraps `send` so every answer says "don't keep a copy" (tokens and calendar data)."""

    async def sending(message: Message) -> None:
        if message["type"] == "http.response.start":
            headers = [(k, v) for k, v in message.get("headers", []) if k.lower() != b"cache-control"]
            message = {**message, "headers": [*headers, (b"cache-control", b"no-store")]}
        await send(message)

    return sending


class BearerAuth:
    """ASGI wrapper around the MCP server: lets a request through only with a valid access token."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        send = no_store(send)
        request = Request(scope)
        # Some clients probe before logging in: answer without asking for a token.
        if request.method == "OPTIONS":
            await Response(status_code=204, headers={"Allow": "GET, POST, DELETE, OPTIONS"})(scope, receive, send)
            return
        if request.method == "HEAD":
            await Response(status_code=200)(scope, receive, send)
            return

        scheme, _, token = request.headers.get("authorization", "").partition(" ")
        valid = False
        if scheme.lower() == "bearer" and token.strip():
            valid = await anyio.to_thread.run_sync(_is_valid_access, token.strip())  # database work, off the event loop
        if not valid:
            metadata = f"{public_base()}/.well-known/oauth-protected-resource"
            response = JSONResponse(
                {"error": "invalid_token", "error_description": "Log in to Agenda to connect."},
                status_code=401,
                headers={"WWW-Authenticate": f'Bearer resource_metadata="{metadata}"'},
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
