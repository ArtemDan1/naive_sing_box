import json

from app.generators import singbox_config, caddyfile, subscription


def test_singbox_config_includes_only_given_users():
    users = [
        {"username": "alice", "password": "pw1"},
        {"username": "bob", "password": "pw2"},
    ]
    cfg = json.loads(singbox_config(users))
    inbound = cfg["inbounds"][0]
    assert inbound["type"] == "naive"
    assert inbound["listen"] == "0.0.0.0"
    assert inbound["listen_port"] == 1080
    assert inbound["users"] == users
    assert cfg["outbounds"] == [{"type": "direct"}]


def test_singbox_config_empty_users_omits_inbound():
    cfg = json.loads(singbox_config([]))
    assert cfg["inbounds"] == []
    assert cfg["outbounds"] == [{"type": "direct"}]


def test_caddyfile_contains_domain_and_routes():
    text = caddyfile("vpn.example.com")
    assert "vpn.example.com {" in text
    assert "@naive method CONNECT" in text
    assert "reverse_proxy h2c://singbox:1080" in text
    assert "header_up Proxy-Authorization {header.Proxy-Authorization}" in text
    assert "flush_interval -1" in text
    assert "handle /api/* {" in text
    assert "handle /sub/* {" in text
    assert "handle_path /admin/* {" in text
    assert "reverse_proxy fastapi:8000" in text
    assert "reverse_proxy frontend:80" in text
    assert "/srv/fallback" in text
    assert "file_server" in text


def test_subscription_outbound():
    sub = json.loads(subscription("vpn.example.com", "alice", "pw1"))
    out = sub["outbounds"][0]
    assert out["type"] == "naive"
    assert out["server"] == "vpn.example.com"
    assert out["server_port"] == 443
    assert out["username"] == "alice"
    assert out["password"] == "pw1"
    assert out["tls"] == {"enabled": True, "server_name": "vpn.example.com"}
