def test_requires_token(client):
    assert client.get("/api/clients").status_code == 401


def test_create_list_update_delete(client, auth_headers, reloader):
    # domain must be set for apply_proxy to (re)generate the Caddyfile
    client.put("/api/settings", json={"domain": "vpn.example.com"}, headers=auth_headers)

    # create
    r = client.post("/api/clients", json={"label": "Phone"}, headers=auth_headers)
    assert r.status_code == 201
    c = r.json()
    assert c["label"] == "Phone"
    assert c["username"] and c["sub_uuid"] and c["enabled"] is True
    cid = c["id"]
    assert reloader.restart.called  # sing-box restarted

    # list
    r = client.get("/api/clients", headers=auth_headers)
    assert r.status_code == 200 and len(r.json()) == 1

    # disable
    r = client.patch(
        f"/api/clients/{cid}", json={"enabled": False}, headers=auth_headers
    )
    assert r.status_code == 200 and r.json()["enabled"] is False

    # delete
    r = client.delete(f"/api/clients/{cid}", headers=auth_headers)
    assert r.status_code == 204
    assert client.get("/api/clients", headers=auth_headers).json() == []
