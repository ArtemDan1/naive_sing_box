import json

from app.models import Client, Settings


def _seed_domain(db, domain="vpn.example.com"):
    db.add(Settings(domain=domain))
    db.commit()


def test_subscription_returns_full_profile_by_default(client, db_session):
    _seed_domain(db_session)
    db_session.add(
        Client(label="My Phone", username="alice", password="pw1", sub_uuid="abc", enabled=True)
    )
    db_session.commit()
    r = client.get("/sub/abc")
    assert r.status_code == 200
    prof = json.loads(r.text)
    assert prof["inbounds"][0]["type"] == "mixed"
    out = prof["outbounds"][0]
    assert out["type"] == "naive"
    assert out["server"] == "vpn.example.com"
    assert out["username"] == "alice"
    assert prof["route"]["final"] == "proxy"


def test_subscription_outbounds_only_for_hiddify(client, db_session):
    # Hiddify injects its own inbound+route; an embedded inbound breaks it, so
    # it must receive an outbounds-only fragment (matched by UA).
    _seed_domain(db_session)
    db_session.add(
        Client(label="My Phone", username="alice", password="pw1", sub_uuid="abc", enabled=True)
    )
    db_session.commit()
    frag = json.loads(client.get("/sub/abc", headers={"user-agent": "HiddifyNext/2.0.0"}).text)
    assert "inbounds" not in frag
    assert "route" not in frag
    assert frag["outbounds"][0]["type"] == "naive"


def test_subscription_headers(client, db_session):
    import base64
    _seed_domain(db_session)
    db_session.add(
        Client(label="My Phone", username="alice", password="pw1", sub_uuid="abc", enabled=True)
    )
    db_session.commit()
    r = client.get("/sub/abc")
    assert r.headers["profile-title"] == "base64:" + base64.b64encode("My Phone".encode()).decode()
    assert r.headers["profile-update-interval"] == "24"
    assert r.headers["content-disposition"] == 'attachment; filename="My_Phone.json"'


def test_subscription_filename_sanitized(client, db_session):
    _seed_domain(db_session)
    db_session.add(
        Client(label="My/Phone v2!", username="alice", password="pw1", sub_uuid="abc", enabled=True)
    )
    db_session.commit()
    r = client.get("/sub/abc")
    assert r.headers["content-disposition"] == 'attachment; filename="My_Phone_v2.json"'


def test_subscription_unknown_uuid_404(client, db_session):
    _seed_domain(db_session)
    assert client.get("/sub/nope").status_code == 404


def test_subscription_disabled_404(client, db_session):
    _seed_domain(db_session)
    db_session.add(
        Client(label="a", username="alice", password="pw1", sub_uuid="abc", enabled=False)
    )
    db_session.commit()
    assert client.get("/sub/abc").status_code == 404


_BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605.1.15"


def test_subscription_browser_gets_html_page(client, db_session):
    _seed_domain(db_session)
    db_session.add(
        Client(label="My Phone", username="alice", password="pw1", sub_uuid="abc", enabled=True)
    )
    db_session.commit()
    r = client.get("/sub/abc", headers={"user-agent": _BROWSER_UA})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "window.__SUB__" in r.text
    assert "My Phone" in r.text
    assert "vpn.example.com/sub/abc" in r.text
    assert '"platform": "desktop"' in r.text


def test_subscription_client_still_gets_json(client, db_session):
    # Regression: non-browser UA must keep returning the JSON profile.
    _seed_domain(db_session)
    db_session.add(
        Client(label="My Phone", username="alice", password="pw1", sub_uuid="abc", enabled=True)
    )
    db_session.commit()
    r = client.get("/sub/abc", headers={"user-agent": "sing-box/1.8.0"})
    assert r.headers["content-type"].startswith("application/json")
    json.loads(r.text)  # parses


def test_subscription_browser_404_is_html(client, db_session):
    _seed_domain(db_session)
    r = client.get("/sub/nope", headers={"user-agent": _BROWSER_UA})
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("text/html")
    assert "не найдена" in r.text.lower()
