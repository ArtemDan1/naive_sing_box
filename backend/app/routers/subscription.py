import base64
import re

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Client, Settings
from app.generators import subscription as gen_subscription
from app.generators import subscription_outbounds as gen_outbounds

router = APIRouter(tags=["subscription"])

# "Managed" clients inject their own tun inbound + route/dns and choke on an
# embedded inbound, so they get an outbounds-only fragment. Everything else
# (sing-box CLI/app, Karing, curl) gets the full standalone profile.
_MANAGED_UA = ("hiddify", "happ")


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")
    return cleaned or "profile"


@router.get("/sub/{sub_uuid}")
def get_subscription(sub_uuid: str, request: Request, db: Session = Depends(get_db)):
    c = db.query(Client).filter_by(sub_uuid=sub_uuid, enabled=True).first()
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    s = db.query(Settings).first()
    domain = s.domain if s else ""

    ua = request.headers.get("user-agent", "").lower()
    if any(k in ua for k in _MANAGED_UA):
        body = gen_outbounds(domain, c.username, c.password)
    else:
        body = gen_subscription(domain, c.username, c.password)

    title = base64.b64encode(c.label.encode()).decode()
    headers = {
        "profile-title": f"base64:{title}",
        "profile-update-interval": "24",
        "content-disposition": f'attachment; filename="{_safe_filename(c.label)}.json"',
    }
    return Response(content=body, media_type="application/json", headers=headers)
