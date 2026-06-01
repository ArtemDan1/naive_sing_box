from unittest.mock import MagicMock

from app import bootstrap
from app.models import Admin, Settings


def test_bootstrap_creates_admin_and_settings(db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(bootstrap.settings, "admin_username", "root")
    monkeypatch.setattr(bootstrap.settings, "admin_password", "rootpw")
    monkeypatch.setattr(bootstrap.settings, "domain", "vpn.example.com")
    monkeypatch.setattr(
        "app.services.settings.caddyfile_path", str(tmp_path / "Caddyfile")
    )
    db_session.query(Admin).delete()
    db_session.commit()

    bootstrap.run(db_session, reloader=MagicMock())

    assert db_session.query(Admin).filter_by(username="root").first() is not None
    assert db_session.query(Settings).first().domain == "vpn.example.com"


def test_bootstrap_idempotent(db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(bootstrap.settings, "domain", "")
    monkeypatch.setattr(
        "app.services.settings.caddyfile_path", str(tmp_path / "Caddyfile")
    )
    bootstrap.run(db_session, reloader=MagicMock())
    bootstrap.run(db_session, reloader=MagicMock())
    assert db_session.query(Admin).count() == 1
