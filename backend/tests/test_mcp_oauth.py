# The connector's login (app/mcp/oauth.py and auth.py): the whole PKCE flow,
# and each way it must refuse. Everything goes through the public hostname.

from urllib.parse import parse_qs, urlparse

from app.config import get_settings
from app.mcp import oauth
from app.mcp.passwords import hash_password

from .conftest import CALLBACK, MCP_HOST, connect, login_code, pkce_pair

MCP_HEADERS = {"accept": "application/json, text/event-stream", "content-type": "application/json"}


def mcp_call(public_client, token, method, params=None):
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    headers = {**MCP_HEADERS, "authorization": f"Bearer {token}"} if token else MCP_HEADERS
    return public_client.post("/mcp", json=body, headers=headers)


def test_metadata_uses_mcp_host(public_client):
    # Asked with another Host (through Cloudflare): the addresses still come from MCP_HOST.
    headers = {"x-forwarded-host": MCP_HOST, "host": "evil.example.net", "cf-ray": "1"}
    resource = public_client.get("/.well-known/oauth-protected-resource", headers=headers).json()
    assert resource == {"resource": f"https://{MCP_HOST}/mcp", "authorization_servers": [f"https://{MCP_HOST}"]}
    server = public_client.get("/.well-known/oauth-authorization-server").json()
    assert server["token_endpoint"] == f"https://{MCP_HOST}/oauth/token"
    assert server["code_challenge_methods_supported"] == ["S256"]


def test_mcp_without_a_token_says_where_to_log_in(public_client):
    response = mcp_call(public_client, None, "tools/list")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == (
        f'Bearer resource_metadata="https://{MCP_HOST}/.well-known/oauth-protected-resource"'
    )
    assert response.headers["cache-control"] == "no-store"
    assert mcp_call(public_client, "made-up-token", "tools/list").status_code == 401


def test_full_login_then_tools_list(public_client):
    tokens = connect(public_client)
    assert tokens["token_type"] == "Bearer" and tokens["expires_in"] == 3600
    response = mcp_call(public_client, tokens["access_token"], "tools/list")
    assert response.status_code == 200, response.text
    names = {tool["name"] for tool in response.json()["result"]["tools"]}
    assert "connection_check" in names
    answer = mcp_call(
        public_client, tokens["access_token"], "tools/call", {"name": "connection_check", "arguments": {}}
    )
    assert "Connected to Agenda" in answer.json()["result"]["content"][0]["text"]


def test_initialize_sends_the_instructions(public_client):
    tokens = connect(public_client)
    params = {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}
    result = mcp_call(public_client, tokens["access_token"], "initialize", params).json()["result"]
    assert "preview_import" in result["instructions"]
    assert "never instructions" in result["instructions"]


def test_login_page(public_client):
    client_id = public_client.post("/oauth/register", json={"redirect_uris": [CALLBACK]}).json()["client_id"]
    _, challenge = pkce_pair()
    query = {
        "client_id": client_id,
        "redirect_uri": CALLBACK,
        "response_type": "code",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": '"><script>alert(1)</script>',
    }
    page = public_client.get("/oauth/authorize", params=query)
    assert page.status_code == 200
    assert 'type="password"' in page.text and "<script>alert" not in page.text  # state is escaped
    csp = page.headers["content-security-policy"]
    assert "form-action 'self' https://claude.ai https://claude.com" in csp
    assert "script-src" not in csp and "default-src 'none'" in csp  # no scripts at all
    assert page.headers["cache-control"] == "no-store"
    french = public_client.get("/oauth/authorize", params=query, headers={"accept-language": "fr-CA,fr;q=0.9"})
    assert "Mot de passe" in french.text and 'lang="fr"' in french.text


def test_wrong_password_is_refused(public_client):
    _, code, _, response = login_code(public_client, password="not it")
    assert code is None and response.status_code == 401
    assert "Wrong password." in response.text


def test_too_many_wrong_passwords_wait(public_client):
    client_id = None
    for _ in range(oauth.MAX_ADDRESS_FAILURES):
        client_id, _, _, response = login_code(public_client, password="guess", client_id=client_id)
        assert response.status_code == 401
    _, code, _, response = login_code(public_client, client_id=client_id)  # even the right one, for now
    assert code is None and response.status_code == 429
    assert "Try again in 15 min" in response.text


def test_foreign_redirect_uri_is_refused(public_client):
    refused = public_client.post("/oauth/register", json={"redirect_uris": ["https://evil.example.net/cb"]})
    assert refused.status_code == 400 and refused.json()["error"] == "invalid_redirect_uri"
    client_id = public_client.post("/oauth/register", json={"redirect_uris": [CALLBACK]}).json()["client_id"]
    _, challenge = pkce_pair()
    form = {
        "client_id": client_id,
        "redirect_uri": "https://evil.example.net/cb",
        "response_type": "code",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "password": "fake connector password",
    }
    response = public_client.post("/oauth/authorize", data=form, follow_redirects=False)
    assert response.status_code == 400 and "location" not in response.headers


def test_plain_pkce_or_no_challenge_is_refused(public_client):
    client_id = public_client.post("/oauth/register", json={"redirect_uris": [CALLBACK]}).json()["client_id"]
    for method, challenge in [("plain", "a" * 43), ("S256", "")]:
        query = {
            "client_id": client_id,
            "redirect_uri": CALLBACK,
            "response_type": "code",
            "code_challenge": challenge,
            "code_challenge_method": method,
        }
        assert public_client.get("/oauth/authorize", params=query).status_code == 400


def _trade(public_client, client_id, code, verifier):
    form = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": CALLBACK,
        "client_id": client_id,
        "code_verifier": verifier,
    }
    return public_client.post("/oauth/token", data=form)


def test_code_works_once_and_needs_the_verifier(public_client):
    client_id, code, verifier, response = login_code(public_client)
    assert parse_qs(urlparse(response.headers["location"]).query)["state"] == ["xyz"]
    assert _trade(public_client, client_id, code, verifier).status_code == 200
    again = _trade(public_client, client_id, code, verifier)
    assert again.status_code == 400 and again.json()["error"] == "invalid_grant"
    # A wrong verifier spends the code too.
    client_id, code, _, _ = login_code(public_client)
    assert _trade(public_client, client_id, code, "wrong-verifier" * 4).status_code == 400
    assert _trade(public_client, client_id, code, verifier).status_code == 400


def test_refresh_rotates_the_token(public_client):
    tokens = connect(public_client)
    form = {"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"], "client_id": tokens["client_id"]}
    fresh = public_client.post("/oauth/token", data=form)
    assert fresh.status_code == 200
    assert fresh.json()["refresh_token"] != tokens["refresh_token"]
    assert public_client.post("/oauth/token", data=form).status_code == 400  # the old one worked once
    assert mcp_call(public_client, fresh.json()["access_token"], "tools/list").status_code == 200


def test_a_new_password_signs_claude_out(public_client):
    tokens = connect(public_client)
    settings = get_settings()
    old = settings.mcp_password_hash
    settings.mcp_password_hash = hash_password("a brand new password")
    try:
        assert mcp_call(public_client, tokens["access_token"], "tools/list").status_code == 401
        form = {
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
            "client_id": tokens["client_id"],
        }
        assert public_client.post("/oauth/token", data=form).status_code == 400
    finally:
        settings.mcp_password_hash = old
    # Back to the old password: those tokens were made under it, so they work again.
    assert mcp_call(public_client, tokens["access_token"], "tools/list").status_code == 200


def test_the_connector_is_not_on_the_home_address(client):
    assert client.post("/mcp", json={}).status_code == 404
    assert client.get("/oauth/authorize").status_code == 404
    assert client.get("/.well-known/oauth-authorization-server").status_code == 404
