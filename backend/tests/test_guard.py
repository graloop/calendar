# The public-host guard (app/mcp/guard.py): on the connector's public hostname
# only the connector's paths answer; on the home address they're the ones that don't.

import pytest

from app.config import Settings, get_settings
from app.mcp.passwords import hash_password, verify_password

from .conftest import MCP_HOST as PUBLIC


@pytest.fixture
def public_host():
    assert get_settings().mcp_host == PUBLIC  # set by conftest.py
    return PUBLIC


@pytest.fixture
def settings_changed():
    """Lets a test change the settings; they're put back after it."""
    settings = get_settings()
    saved = settings.model_dump()
    yield settings
    for name, value in saved.items():
        setattr(settings, name, value)


def on(host):
    return {"host": host}


@pytest.mark.parametrize("path", ["/", "/upcoming", "/api/events", "/api/health", "/css/base.css", "/docs"])
def test_public_host_hides_the_app(client, public_host, path):
    response = client.get(path, headers=on(public_host))
    assert response.status_code == 404
    assert response.text == "Not found"


def test_public_host_hides_writes_too(client, public_host):
    for method, path in [("POST", "/api/import/apply"), ("POST", "/api/events"), ("DELETE", "/api/events/1")]:
        assert client.request(method, path, headers=on(public_host), json={}).status_code == 404


def test_public_host_is_matched_whatever_the_case_or_port(client, public_host):
    for host in ["Agenda-MCP.Example.com", f"{PUBLIC}:443"]:
        assert client.get("/api/events", headers=on(host)).status_code == 404


def test_forwarded_host_counts_as_public(client, public_host):
    # A tunnel that rewrites Host to the home one still says where it came from.
    headers = {"host": "agenda:8000", "x-forwarded-host": PUBLIC}
    assert client.get("/api/events", headers=headers).status_code == 404


def test_anything_through_cloudflare_counts_as_public(client, settings_changed):
    # Even with MCP_HOST not set: a request the tunnel brought in never reaches the app.
    settings_changed.mcp_host = ""
    for header in ["cf-ray", "cf-connecting-ip"]:
        assert client.get("/api/events", headers={"host": "agenda:8000", header: "x"}).status_code == 404


def test_public_host_lets_the_connector_paths_through(client, public_host):
    assert client.get("/.well-known/oauth-authorization-server", headers=on(public_host)).status_code == 200
    assert client.post("/mcp", headers=on(public_host), json={}).status_code == 401  # needs a token
    # And on the guard's own rule, for every path:
    from app.mcp.guard import allowed

    for path in [
        "/mcp",
        "/mcp/",
        "/oauth/authorize",
        "/oauth/token",
        "/oauth/register",
        "/.well-known/oauth-authorization-server",
        "/.well-known/oauth-protected-resource/mcp",
    ]:
        assert allowed({"path": path, "headers": [(b"host", PUBLIC.encode())]}, PUBLIC), path
    for path in ["/mcpx", "/oauth/other", "/.well-known/security.txt", "/mcp/../api/events"]:
        assert not allowed({"path": path, "headers": [(b"host", PUBLIC.encode())]}, PUBLIC), path


@pytest.mark.parametrize("path", ["/", "/upcoming", "/api/events", "/api/health"])
def test_home_address_is_untouched(client, public_host, path):
    assert client.get(path, headers=on("localhost")).status_code == 200
    assert client.get(path, headers=on("192.168.1.50:8030")).status_code == 200


@pytest.mark.parametrize("path", ["/mcp", "/mcp/", "/oauth/authorize", "/oauth/token", "/.well-known/oauth-x"])
def test_home_address_has_no_connector(client, public_host, path):
    response = client.get(path, headers=on("localhost"))
    assert response.status_code == 404
    assert response.text == "Not found"


def test_without_mcp_host_everything_is_home(client, settings_changed):
    settings_changed.mcp_host = ""
    assert client.get("/api/events", headers=on(PUBLIC)).status_code == 200
    assert client.get("/mcp", headers=on(PUBLIC)).status_code == 404


def test_settings_tidy_the_hostname():
    assert Settings(mcp_host=" https://Agenda-MCP.example.com/mcp ").mcp_host == PUBLIC
    assert Settings(mcp_host="agenda-mcp.example.com:443").mcp_host == PUBLIC


def test_settings_say_what_is_missing():
    assert Settings(mcp_enabled=False).mcp_problem() is None
    problem = Settings(mcp_enabled=True, mcp_host="", mcp_password_hash="").mcp_problem()
    assert "MCP_HOST and MCP_PASSWORD_HASH" in problem
    assert "isn't a hash" in Settings(mcp_enabled=True, mcp_host=PUBLIC, mcp_password_hash="hunter2").mcp_problem()
    assert Settings(mcp_enabled=True, mcp_host=PUBLIC, mcp_password_hash=hash_password("x")).mcp_problem() is None


def test_a_wrong_setting_does_not_crash_the_app(settings_changed, caplog):
    from fastapi.testclient import TestClient

    from app.main import app

    settings_changed.mcp_host = ""
    settings_changed.mcp_password_hash = ""
    with TestClient(app) as again:
        assert again.get("/api/health").status_code == 200
    assert "MCP_HOST and MCP_PASSWORD_HASH is empty" in caplog.text


def test_password_hash_round_trip():
    stored = hash_password("correct horse battery")
    assert stored.startswith("scrypt$16384$8$1$")
    assert verify_password("correct horse battery", stored)
    assert not verify_password("wrong", stored)
    assert not verify_password("anything", "")
    assert not verify_password("anything", "not-a-hash")
