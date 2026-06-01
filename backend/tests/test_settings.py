def test_get_default_domain_empty(client, auth_headers):
    r = client.get("/api/settings", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["domain"] == ""


def test_put_domain_applies_caddy(client, auth_headers, reloader):
    r = client.put(
        "/api/settings", json={"domain": "vpn.example.com"}, headers=auth_headers
    )
    assert r.status_code == 200
    assert r.json()["domain"] == "vpn.example.com"
    reloader.restart.assert_called_with("caddy")
    r2 = client.get("/api/settings", headers=auth_headers)
    assert r2.json()["domain"] == "vpn.example.com"
