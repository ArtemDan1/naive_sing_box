import json

from app.generators import caddyfile, subscription


def test_caddyfile_contains_domain_and_routes():
    text = caddyfile("vpn.example.com", [])
    assert "debug" in text
    assert "protocols h1 h2" in text
    assert "vpn.example.com {" in text
    assert "forward_proxy {" in text
    assert "hide_ip" in text
    assert "handle /api/* {" in text
    assert "handle /sub/* {" in text
    assert "handle_path /admin/* {" in text
    assert "reverse_proxy fastapi:8000" in text
    assert "reverse_proxy frontend:80" in text
    assert "/srv/fallback" in text
    assert "file_server" in text


def test_caddyfile_embeds_user_basic_auth():
    users = [
        {"username": "alice", "password": "pw1"},
        {"username": "bob", "password": "pw2"},
    ]
    text = caddyfile("vpn.example.com", users)
    assert "basic_auth alice pw1" in text
    assert "basic_auth bob pw2" in text


def test_caddyfile_no_users_has_no_basic_auth():
    text = caddyfile("vpn.example.com", [])
    assert "basic_auth" not in text


def test_subscription_outbound():
    sub = json.loads(subscription("vpn.example.com", "alice", "pw1"))
    out = sub["outbounds"][0]
    assert out["type"] == "naive"
    assert out["server"] == "vpn.example.com"
    assert out["server_port"] == 443
    assert out["username"] == "alice"
    assert out["password"] == "pw1"
    assert out["tls"] == {"enabled": True, "server_name": "vpn.example.com"}
