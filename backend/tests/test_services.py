from unittest.mock import MagicMock
import json

from app import services
from app.models import Client


def test_apply_singbox_writes_enabled_users_and_restarts(tmp_path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    monkeypatch.setattr(services.settings, "singbox_config_path", str(cfg_file))
    monkeypatch.setattr(services.settings, "singbox_container", "singbox")

    db = MagicMock()
    db.query.return_value.filter_by.return_value.all.return_value = [
        Client(label="a", username="alice", password="pw1", sub_uuid="x", enabled=True),
    ]
    reloader = MagicMock()

    services.apply_singbox(db, reloader)

    written = json.loads(cfg_file.read_text())
    assert written["inbounds"][0]["users"] == [{"username": "alice", "password": "pw1"}]
    reloader.restart.assert_called_once_with("singbox")


def test_apply_caddy_writes_file_and_restarts(tmp_path, monkeypatch):
    cf = tmp_path / "Caddyfile"
    monkeypatch.setattr(services.settings, "caddyfile_path", str(cf))
    monkeypatch.setattr(services.settings, "caddy_container", "caddy")
    reloader = MagicMock()

    services.apply_caddy("vpn.example.com", reloader)

    assert "vpn.example.com {" in cf.read_text()
    reloader.restart.assert_called_once_with("caddy")
