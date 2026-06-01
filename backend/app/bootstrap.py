from sqlalchemy.orm import Session

from app.config import settings
from app.models import Admin, Settings
from app.security import hash_password
from app.reloader import Reloader
from app.services import apply_proxy


def run(db: Session, reloader: Reloader) -> None:
    if db.query(Admin).count() == 0:
        db.add(
            Admin(
                username=settings.admin_username,
                password_hash=hash_password(settings.admin_password),
            )
        )
        db.commit()
    if db.query(Settings).first() is None:
        db.add(Settings(domain=settings.domain))
        db.commit()
    # Generate the Caddyfile on startup. On the very first boot the caddy
    # container may not be reachable yet for the reload; that is acceptable
    # (it starts after fastapi is healthy and reads the file then).
    try:
        apply_proxy(db, reloader)
    except Exception:
        pass
