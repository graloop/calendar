# The login Claude goes through to use /mcp: a small OAuth 2.1 server (PKCE,
# dynamic client registration), copied from the training app and simplified:
# there are no accounts, only the connector password (MCP_PASSWORD_HASH).
#
# What happens when the connector is added in claude.ai:
# 1. Claude calls /mcp, gets a 401 (auth.py) and reads the two /.well-known
#    documents below to learn where to log in.
# 2. POST /oauth/register: Claude registers itself and gets a client_id. Only
#    Claude's own callback addresses are accepted (ALLOWED_REDIRECT_URIS).
# 3. GET /oauth/authorize: the browser shows the password page.
#    POST /oauth/authorize: the right password -> back to Claude with a
#    one-time code (CODE_MINUTES).
# 4. POST /oauth/token: Claude trades the code for an access token
#    (ACCESS_MINUTES) and a refresh token (MCP_TOKEN_DAYS), and later each
#    refresh token for a new pair.
#
# Every address in the answers is built from MCP_HOST, never from the request.

import base64
import hashlib
import html
import ipaddress
import logging
import re
import secrets
import threading
import time
from dataclasses import dataclass
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..models import McpAuthCode, McpClient, McpToken
from .auth import expiry, live_token, now, password_mark, public_base, token_hash
from .passwords import verify_password

log = logging.getLogger("agenda.mcp")
router = APIRouter(tags=["mcp"], include_in_schema=False)

# Where a login may send its code: Claude's own callback, nothing else. So a
# made-up client can't have the code delivered to another site.
ALLOWED_REDIRECT_URIS = {
    "https://claude.ai/api/mcp/auth_callback",
    "https://claude.com/api/mcp/auth_callback",
}
CODE_MINUTES = 5  # a login code is traded for tokens right away
ACCESS_MINUTES = 60
# Registering needs no login, so only this many clients are kept: the oldest
# ones without a working token make room (a stranger can't fill the table).
MAX_CLIENTS = 50
_CHALLENGE = re.compile(r"[A-Za-z0-9._~-]{43,128}")  # RFC 7636: a base64url SHA-256 is 43 characters
STATE_MAX = 1024


def _json(body: dict, status_code: int = 200) -> JSONResponse:
    return JSONResponse(body, status_code=status_code, headers={"Cache-Control": "no-store"})


def _oauth_error(error: str, description: str, status_code: int = 400) -> JSONResponse:
    """An error the way OAuth clients read it (RFC 6749, 5.2)."""
    return _json({"error": error, "error_description": description}, status_code)


# --- Discovery ---


@router.get("/.well-known/oauth-protected-resource")
@router.get("/.well-known/oauth-protected-resource/mcp")
def protected_resource():
    """RFC 9728: /mcp is protected, and this same app is where to log in."""
    base = public_base()
    return _json({"resource": f"{base}/mcp", "authorization_servers": [base]})


@router.get("/.well-known/oauth-authorization-server")
@router.get("/.well-known/oauth-authorization-server/mcp")
def authorization_server():
    """RFC 8414: where each step of the login is."""
    base = public_base()
    return _json(
        {
            "issuer": base,
            "authorization_endpoint": f"{base}/oauth/authorize",
            "token_endpoint": f"{base}/oauth/token",
            "registration_endpoint": f"{base}/oauth/register",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none"],
        }
    )


# --- Registration ---


@router.post("/oauth/register")
async def register(request: Request, db: Session = Depends(get_db)):
    """RFC 7591: Claude registers itself. No secret is given: PKCE protects the login."""
    try:
        body = await request.json()
    except ValueError:
        body = None
    uris = body.get("redirect_uris") if isinstance(body, dict) else None
    if not isinstance(uris, list) or not uris or not all(uri in ALLOWED_REDIRECT_URIS for uri in uris):
        return _oauth_error("invalid_redirect_uri", "Only Claude's own callback addresses can be registered.")

    _make_room_for_a_client(db)
    client = McpClient(client_id=secrets.token_urlsafe(24), redirect_uris=sorted(set(uris)))
    db.add(client)
    db.commit()
    return _json(
        {
            "client_id": client.client_id,
            "redirect_uris": client.redirect_uris,
            "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
        },
        201,
    )


def _make_room_for_a_client(db: Session) -> None:
    """Keep the table under MAX_CLIENTS: drop the oldest clients no working token belongs to."""
    extra = db.scalar(select(func.count()).select_from(McpClient)) - MAX_CLIENTS + 1
    if extra <= 0:
        return
    in_use = select(McpToken.client_id).where(McpToken.revoked_at.is_(None), McpToken.expires_at > now())
    unused = db.scalars(
        select(McpClient)
        .where(McpClient.client_id.not_in(in_use))
        .order_by(McpClient.created_at, McpClient.id)
        .limit(extra)
    )
    for client in unused:
        db.delete(client)


# --- Too many wrong passwords ---
# In memory (one process): after MAX_ADDRESS_FAILURES wrong passwords from one
# address within WINDOW_SECONDS, that address waits. With one password for the
# whole app, someone could also try from many addresses: after MAX_FAILURES
# from anywhere, every login waits (the owner can wait 15 minutes too).

MAX_ADDRESS_FAILURES = 10
MAX_FAILURES = 30
WINDOW_SECONDS = 15 * 60
_failures: dict[str, list[float]] = {}
_lock = threading.Lock()
_EVERYONE = "*"


def _recent(key: str, moment: float) -> list[float]:
    times = [t for t in _failures.get(key, []) if moment - t < WINDOW_SECONDS]
    if times:
        _failures[key] = times
    else:
        _failures.pop(key, None)
    return times


def seconds_to_wait(address: str) -> int:
    moment = time.monotonic()
    with _lock:
        waits = [
            WINDOW_SECONDS - (moment - times[0])
            for key, limit in ((address, MAX_ADDRESS_FAILURES), (_EVERYONE, MAX_FAILURES))
            if len(times := _recent(key, moment)) >= limit
        ]
    return int(max(waits, default=0)) + (1 if waits else 0)


def record_failure(address: str) -> None:
    moment = time.monotonic()
    with _lock:
        for key in (address, _EVERYONE):
            times = _recent(key, moment)
            times.append(moment)
            _failures[key] = times
        if len(_failures) > 5000:  # many addresses guessing: forget the oldest ones
            for key in sorted(_failures, key=lambda k: _failures[k][-1])[:1000]:
                if key != _EVERYONE:
                    del _failures[key]
    log.warning("Wrong connector password from %s", address)


def forget_failures() -> None:
    """For the tests."""
    with _lock:
        _failures.clear()


def visitor_address(request: Request) -> str:
    """Who is logging in. Behind the tunnel every request comes from cloudflared on
    the Docker network, so the visitor's own address is in CF-Connecting-IP. It's
    only believed when the request comes from a private address (the tunnel), so
    nobody can make it up from outside."""
    peer = request.client.host if request.client else ""
    try:
        private = ipaddress.ip_address(peer).is_private
    except ValueError:
        private = peer == "testclient"
    if private:
        forwarded = request.headers.get("cf-connecting-ip", "").strip()
        if forwarded:
            return forwarded
    return peer or "unknown"


# --- The login page ---


@dataclass
class _LoginRequest:
    """What Claude asks for when it opens the login page; carried through the form as hidden fields."""

    client_id: str
    redirect_uri: str
    response_type: str
    code_challenge: str
    code_challenge_method: str
    state: str

    def problem(self, db: Session) -> str | None:
        """Why this request can't be answered, in words for the page. Nothing is
        ever redirected to an address that fails here."""
        client = db.scalar(select(McpClient).where(McpClient.client_id == self.client_id))
        if client is None:
            return "This connector isn't registered here. Remove it in Claude's settings and add it again."
        if self.redirect_uri not in client.redirect_uris or self.redirect_uri not in ALLOWED_REDIRECT_URIS:
            return "This login was not started by Claude."
        if self.response_type != "code":
            return "Unsupported login request (response_type must be code)."
        if self.code_challenge_method != "S256" or not _CHALLENGE.fullmatch(self.code_challenge):
            return "Unsupported login request (a PKCE S256 code challenge is required)."
        if len(self.state) > STATE_MAX:
            return "Unsupported login request (state is too long)."
        return None


# The page's words in French; English is the key, like js/core/fr.js.
FR = {
    "Connect Claude": "Connecter Claude",
    "Enter the connector password to let Claude read and fill your Agenda.": (
        "Entrez le mot de passe du connecteur pour que Claude puisse lire et remplir votre Agenda."
    ),
    "Password": "Mot de passe",
    "Connect": "Connecter",
    "Wrong password.": "Mot de passe incorrect.",
    "Too many wrong passwords. Try again in {n} min.": "Trop de mots de passe incorrects. Réessayez dans {n} min.",
    "This connector isn't registered here. Remove it in Claude's settings and add it again.": (
        "Ce connecteur n'est pas enregistré ici. Retirez-le dans les réglages de Claude et ajoutez-le de nouveau."
    ),
    "This login was not started by Claude.": "Cette connexion n'a pas été lancée par Claude.",
}


def _language(request: Request) -> str:
    """French when the browser asks for French before English."""
    first = request.headers.get("accept-language", "").split(",")[0].strip().lower()
    return "fr" if first.startswith("fr") else "en"


def _t(text: str, lang: str, **values) -> str:
    return (FR.get(text, text) if lang == "fr" else text).format(**values)


# The page carries its own style: the public hostname serves nothing but the
# connector's paths, not /css/. The colours are base.css's tokens, night mode
# follows the device. Allowed by the Content-Security-Policy through its hash.
_STYLE = """
:root { --bg: #fbf8f5; --card: #ffffff; --border: #ede3da; --text: #1f1a17; --muted: #6b7280;
  --accent: #ea580c; --accent-hover: #c2410c; --danger: #dc2626; --nav-bg: #431407; --field: #ffffff; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #17110e; --card: #221a16; --border: #3a2e27; --text: #f3ece6; --muted: #a8a29e;
    --accent: #f97316; --accent-hover: #fb923c; --danger: #f87171; --nav-bg: #2a0d04; --field: #1b1411; }
}
* { box-sizing: border-box; }
body { margin: 0; min-height: 100vh; background: var(--bg); color: var(--text);
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
.topbar { display: flex; align-items: center; gap: 10px; padding: 14px 24px; background: var(--nav-bg); color: #fff;
  font-weight: 700; font-size: 1.1rem; }
.logo { font-size: 1.15rem; font-weight: 700; letter-spacing: -0.045em; color: #f3f1ec; }
.logo svg { height: 0.5em; width: 0.97em; margin: 0 0.03em 0 0.01em; vertical-align: baseline; stroke: #fb923c; }
main { max-width: 420px; margin: 48px auto; padding: 0 16px; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 24px; }
h1 { margin: 0 0 8px; font-size: 1.35rem; }
p { color: var(--muted); line-height: 1.45; }
form { display: flex; flex-direction: column; gap: 10px; margin-top: 16px; }
label { font-weight: 600; font-size: 0.9rem; }
input { min-height: 44px; padding: 8px 12px; border: 1px solid var(--border); border-radius: 8px; font: inherit;
  background: var(--field); color: var(--text); }
input:focus { outline: 2px solid var(--accent); outline-offset: 1px; }
button { min-height: 44px; border: none; border-radius: 8px; background: var(--accent); color: #fff; font: inherit;
  font-weight: 600; cursor: pointer; }
button:hover { background: var(--accent-hover); }
.error { color: var(--danger); font-weight: 600; }
"""
_STYLE_HASH = base64.b64encode(hashlib.sha256(_STYLE.encode("utf-8")).digest()).decode("ascii")

# No scripts at all. form-action must allow going back to Claude: Chrome applies
# it to the redirect that follows the login form.
AUTHORIZE_CSP = (
    f"default-src 'none'; style-src 'sha256-{_STYLE_HASH}'; base-uri 'none'; frame-ancestors 'none'; "
    "form-action 'self' https://claude.ai https://claude.com"
)

_LOGO = (
    '<span class="logo" role="img" aria-label="graloop">gral<svg viewBox="-2 -2 116 60" fill="none" '
    'stroke-width="9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M56 28 '
    "C66 12 78 4 86 4 C99 4 108 15 108 28 C108 41 99 52 86 52 C78 52 66 44 56 28 C46 12 34 4 26 4 C13 4 4 15 "
    '4 28 C4 41 13 52 26 52 C34 52 46 44 56 28 Z"></path></svg>p</span>'
)

_PAGE = """<!doctype html>
<html lang="{lang}">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="robots" content="noindex" />
  <meta name="theme-color" content="#431407" />
  <title>{title} · Agenda</title>
  <style>{style}</style>
</head>
<body>
  <header class="topbar">{logo}<span>Agenda</span></header>
  <main><div class="card">
    <h1>{title}</h1>
{body}
  </div></main>
</body>
</html>
"""


def _page(lang: str, body: str, status_code: int) -> HTMLResponse:
    page = _PAGE.format(lang=lang, title=_t("Connect Claude", lang), style=_STYLE, logo=_LOGO, body=body)
    headers = {"Content-Security-Policy": AUTHORIZE_CSP, "Cache-Control": "no-store", "Referrer-Policy": "no-referrer"}
    return HTMLResponse(page, status_code=status_code, headers=headers)


def _problem_page(lang: str, message: str) -> HTMLResponse:
    return _page(lang, f'    <p class="error" role="alert">{html.escape(_t(message, lang))}</p>', 400)


def _login_page(lang: str, asked: _LoginRequest, error: str = "", status_code: int = 200) -> HTMLResponse:
    hidden = "\n".join(
        f'      <input type="hidden" name="{name}" value="{html.escape(value, quote=True)}" />'
        for name, value in vars(asked).items()
    )
    error_line = f'      <p class="error" role="alert">{html.escape(error)}</p>' if error else ""
    body = f"""    <p>{html.escape(_t("Enter the connector password to let Claude read and fill your Agenda.", lang))}</p>
    <form method="post" action="/oauth/authorize">
{hidden}
      <label for="password">{_t("Password", lang)}</label>
      <input type="password" id="password" name="password" required autofocus autocomplete="current-password" />
      <button type="submit">{_t("Connect", lang)}</button>
{error_line}
    </form>"""
    return _page(lang, body, status_code)


@router.get("/oauth/authorize")
def authorize_page(
    request: Request,
    client_id: str = "",
    redirect_uri: str = "",
    response_type: str = "",
    code_challenge: str = "",
    code_challenge_method: str = "",
    state: str = "",
    db: Session = Depends(get_db),
):
    """The password page Claude opens in the browser."""
    lang = _language(request)
    asked = _LoginRequest(client_id, redirect_uri, response_type, code_challenge, code_challenge_method, state)
    if problem := asked.problem(db):
        return _problem_page(lang, problem)
    return _login_page(lang, asked)


@router.post("/oauth/authorize")
def authorize(
    request: Request,
    client_id: str = Form(""),
    redirect_uri: str = Form(""),
    response_type: str = Form(""),
    code_challenge: str = Form(""),
    code_challenge_method: str = Form(""),
    state: str = Form(""),
    password: str = Form(""),
    db: Session = Depends(get_db),
):
    """Checks the password, then sends the browser back to Claude with a one-time code."""
    lang = _language(request)
    asked = _LoginRequest(client_id, redirect_uri, response_type, code_challenge, code_challenge_method, state)
    if problem := asked.problem(db):
        return _problem_page(lang, problem)

    address = visitor_address(request)
    if wait := seconds_to_wait(address):
        message = _t("Too many wrong passwords. Try again in {n} min.", lang, n=max(1, -(-wait // 60)))
        return _login_page(lang, asked, message, 429)
    if not verify_password(password, get_settings().mcp_password_hash):
        record_failure(address)
        return _login_page(lang, asked, _t("Wrong password.", lang), 401)

    code = secrets.token_urlsafe(32)
    db.add(
        McpAuthCode(
            code_hash=token_hash(code),
            client_id=asked.client_id,
            redirect_uri=asked.redirect_uri,
            code_challenge=asked.code_challenge,
            password_mark=password_mark(),
            expires_at=expiry(minutes=CODE_MINUTES),
        )
    )
    db.commit()
    log.info("Connector login from %s: code sent to Claude", address)
    answer = {"code": code, "state": asked.state} if asked.state else {"code": code}
    return RedirectResponse(
        f"{asked.redirect_uri}?{urlencode(answer)}", status_code=302, headers={"Cache-Control": "no-store"}
    )


# --- Tokens ---


@router.post("/oauth/token")
def token(
    grant_type: str = Form(""),
    code: str = Form(""),
    redirect_uri: str = Form(""),
    client_id: str = Form(""),
    code_verifier: str = Form(""),
    refresh_token: str = Form(""),
    db: Session = Depends(get_db),
):
    """A login code, or the last refresh token, for a new pair of tokens."""
    if grant_type == "authorization_code":
        if not _redeem_code(db, code, client_id, redirect_uri, code_verifier):
            db.commit()  # the code stays used, right or wrong
            return _oauth_error("invalid_grant", "The login code is wrong, expired or already used. Connect again.")
    elif grant_type == "refresh_token":
        old = live_token(db, refresh_token, "refresh")
        if old is None or old.client_id != client_id:
            return _oauth_error("invalid_grant", "The connection has expired. Connect again.")
        old.revoked_at = now()  # each refresh token works once
    else:
        return _oauth_error("unsupported_grant_type", "Use authorization_code or refresh_token.")

    access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    mark = password_mark()
    for value, kind, expires_at in (
        (access, "access", expiry(minutes=ACCESS_MINUTES)),
        (refresh, "refresh", expiry(days=get_settings().mcp_token_days)),
    ):
        db.add(
            McpToken(
                token_hash=token_hash(value),
                kind=kind,
                client_id=client_id,
                password_mark=mark,
                expires_at=expires_at,
            )
        )
    _forget_expired(db)
    db.commit()
    return _json(
        {"access_token": access, "token_type": "Bearer", "expires_in": ACCESS_MINUTES * 60, "refresh_token": refresh}
    )


def _redeem_code(db: Session, code: str, client_id: str, redirect_uri: str, code_verifier: str) -> bool:
    """Whether a login code is good. It's marked used at the first try, right or
    wrong. The caller commits."""
    row = db.scalar(
        select(McpAuthCode).where(
            McpAuthCode.code_hash == token_hash(code),
            McpAuthCode.used_at.is_(None),
            McpAuthCode.expires_at > now(),
        )
    )
    if row is None:
        return False
    row.used_at = now()
    # PKCE: only who started this login knows the verifier behind the challenge.
    digest = hashlib.sha256(code_verifier.encode("ascii", "ignore")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    if not secrets.compare_digest(challenge, row.code_challenge):
        return False
    if row.client_id != client_id or row.redirect_uri != redirect_uri:
        return False
    return row.password_mark == password_mark()  # the password changed since the login


def _forget_expired(db: Session) -> None:
    """Expired codes and tokens are of no use to anyone: don't keep them. The caller commits."""
    moment = now()
    db.execute(delete(McpAuthCode).where(McpAuthCode.expires_at < moment))
    db.execute(delete(McpToken).where(McpToken.expires_at < moment))
