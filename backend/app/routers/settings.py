from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_admin, get_reloader
from app.reloader import Reloader
from app.models import Settings
from app.schemas import SettingsIn, SettingsOut
from app.services import apply_proxy

router = APIRouter(tags=["settings"], dependencies=[Depends(get_current_admin)])


def _get_or_create(db: Session) -> Settings:
    s = db.query(Settings).first()
    if s is None:
        s = Settings(domain="")
        db.add(s)
        db.commit()
        db.refresh(s)
    return s


@router.get("/settings", response_model=SettingsOut)
def get_settings(db: Session = Depends(get_db)):
    return SettingsOut(domain=_get_or_create(db).domain)


@router.put("/settings", response_model=SettingsOut)
def put_settings(
    body: SettingsIn,
    db: Session = Depends(get_db),
    reloader: Reloader = Depends(get_reloader),
):
    s = _get_or_create(db)
    s.domain = body.domain
    db.commit()
    apply_proxy(db, reloader)
    return SettingsOut(domain=s.domain)
