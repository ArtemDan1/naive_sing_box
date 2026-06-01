import json

from app.models import Client, Settings


def _seed_domain(db, domain="vpn.example.com"):
    db.add(Settings(domain=domain))
    db.commit()


def test_subscription_returns_profile(client, db_session):
    _seed_domain(db_session)
    db_session.add(
        Client(label="a", username="alice", password="pw1", sub_uuid="abc", enabled=True)
    )
    db_session.commit()
    r = client.get("/sub/abc")
    assert r.status_code == 200
    out = json.loads(r.text)["outbounds"][0]
    assert out["server"] == "vpn.example.com"
    assert out["username"] == "alice"


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
