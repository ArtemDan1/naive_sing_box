from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Client, Settings
from app.generators import subscription as gen_subscription

router = APIRouter(tags=["subscription"])


@router.get("/sub/{sub_uuid}")
def get_subscription(sub_uuid: str, db: Session = Depends(get_db)):
    c = db.query(Client).filter_by(sub_uuid=sub_uuid, enabled=True).first()
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    s = db.query(Settings).first()
    domain = s.domain if s else ""
    body = gen_subscription(domain, c.username, c.password)
    return Response(content=body, media_type="application/json")
