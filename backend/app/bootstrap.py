from sqlalchemy.orm import Session

from app.config import settings
from app.models import Admin, Settings
from app.security import hash_password
from app.reloader import Reloader
from app.services import apply_caddy, apply_singbox


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
    s = db.query(Settings).first()
    # Generate configs on startup. On the very first boot the sing-box/caddy
    # containers may not be reachable yet; that is acceptable (they restart).
    # Each apply is isolated so a failure to reload one container (e.g. docker
    # socket hiccup) never prevents the other config from being written.
    if s.domain:
        try:
            apply_caddy(s.domain, reloader)
        except Exception:
            pass
    try:
        apply_singbox(db, reloader)
    except Exception:
        pass
