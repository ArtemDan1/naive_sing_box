import os

from sqlalchemy.orm import Session

from app.config import settings
from app.generators import caddyfile
from app.models import Client, Settings
from app.reloader import Reloader


def _write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def apply_proxy(db: Session, reloader: Reloader) -> None:
    """Regenerate the Caddyfile from the current domain + enabled clients and
    reload Caddy (the naive server via forward_proxy)."""
    s = db.query(Settings).first()
    domain = s.domain if s else ""
    if not domain:
        return
    clients = db.query(Client).filter_by(enabled=True).all()
    users = [{"username": c.username, "password": c.password} for c in clients]
    _write(settings.caddyfile_path, caddyfile(domain, users))
    reloader.restart(settings.caddy_container)
