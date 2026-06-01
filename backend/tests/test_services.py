from unittest.mock import MagicMock

from app import services
from app.models import Client, Settings


def test_apply_proxy_writes_caddyfile_with_users_and_restarts(tmp_path, monkeypatch):
    cf = tmp_path / "Caddyfile"
    monkeypatch.setattr(services.settings, "caddyfile_path", str(cf))
    monkeypatch.setattr(services.settings, "caddy_container", "caddy")

    db = MagicMock()
    db.query.return_value.first.return_value = Settings(domain="vpn.example.com")
    db.query.return_value.filter_by.return_value.all.return_value = [
        Client(label="a", username="alice", password="pw1", sub_uuid="x", enabled=True),
    ]
    reloader = MagicMock()

    services.apply_proxy(db, reloader)

    text = cf.read_text()
    assert "vpn.example.com {" in text
    assert "basic_auth alice pw1" in text
    reloader.restart.assert_called_once_with("caddy")


def test_apply_proxy_skips_when_no_domain(tmp_path, monkeypatch):
    cf = tmp_path / "Caddyfile"
    monkeypatch.setattr(services.settings, "caddyfile_path", str(cf))
    db = MagicMock()
    db.query.return_value.first.return_value = Settings(domain="")
    reloader = MagicMock()

    services.apply_proxy(db, reloader)

    assert not cf.exists()
    reloader.restart.assert_not_called()
