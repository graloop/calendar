# Shared test setup: a throwaway data folder, a fresh database for each test,
# and a client that talks to the app without starting a server.
# Only fake courses here (ABC123, XYZ789...): never real ones.

import os
import tempfile

# Configure the app before it's imported: settings and the engine are read at
# module import time.
_TMP_DIR = tempfile.mkdtemp(prefix="agenda-tests-")
os.environ["DATA_DIR"] = _TMP_DIR

# Claude's connector is on in the tests, with a made-up hostname and password.
from app.mcp.passwords import hash_password  # noqa: E402  (needs nothing from the settings)

MCP_HOST = "agenda-mcp.example.com"
MCP_PASSWORD = "fake connector password"
os.environ["MCP_ENABLED"] = "true"
os.environ["MCP_HOST"] = MCP_HOST
os.environ["MCP_PASSWORD_HASH"] = hash_password(MCP_PASSWORD)

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def fresh_data():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def public_client():
    """A client that comes in through the connector's public hostname, over https."""
    from app.mcp import oauth

    oauth.forget_failures()
    with TestClient(app, base_url=f"https://{MCP_HOST}") as test_client:
        yield test_client


def add_event(client, **fields):
    """Adds an event (a lab on Tue Nov 24, 2026 unless told otherwise) and answers it."""
    body = {"title": "Lab 3", "type": "lab", "course": "ABC123", "date": "2026-11-24", **fields}
    response = client.post("/api/events", json=body)
    assert response.status_code == 201, response.text
    return response.json()


CALLBACK = "https://claude.ai/api/mcp/auth_callback"


def pkce_pair() -> tuple[str, str]:
    """(verifier, challenge), as Claude makes them for each login."""
    import base64
    import hashlib
    import secrets

    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def login_code(public_client, password=MCP_PASSWORD, client_id=None):
    """Registers (unless given a client_id) and logs in like claude.ai: (client_id, code, verifier, response)."""
    from urllib.parse import parse_qs, urlparse

    if client_id is None:
        client_id = public_client.post("/oauth/register", json={"redirect_uris": [CALLBACK]}).json()["client_id"]
    verifier, challenge = pkce_pair()
    form = {
        "client_id": client_id,
        "redirect_uri": CALLBACK,
        "response_type": "code",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": "xyz",
        "password": password,
    }
    response = public_client.post("/oauth/authorize", data=form, follow_redirects=False)
    code = None
    if response.status_code == 302:
        code = parse_qs(urlparse(response.headers["location"]).query)["code"][0]
    return client_id, code, verifier, response


def connect(public_client) -> dict:
    """The whole login, as claude.ai does it: the token answer, plus the client_id."""
    client_id, code, verifier, _ = login_code(public_client)
    form = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": CALLBACK,
        "client_id": client_id,
        "code_verifier": verifier,
    }
    tokens = public_client.post("/oauth/token", data=form).json()
    return {**tokens, "client_id": client_id}
