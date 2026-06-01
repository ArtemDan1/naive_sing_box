import os

from sqlalchemy.orm import Session

from app.config import settings
from app.generators import singbox_config, caddyfile
from app.models import Client
from app.reloader import Reloader


def _write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def apply_singbox(db: Session, reloader: Reloader) -> None:
    clients = db.query(Client).filter_by(enabled=True).all()
    users = [{"username": c.username, "password": c.password} for c in clients]
    _write(settings.singbox_config_path, singbox_config(users))
    reloader.restart(settings.singbox_container)


def apply_caddy(domain: str, reloader: Reloader) -> None:
    _write(settings.caddyfile_path, caddyfile(domain))
    reloader.restart(settings.caddy_container)
