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

def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")
    return cleaned or "profile"


def _negotiate(ua: str, domain: str, username: str, password: str) -> tuple[str, str]:
    """Pick the subscription body + media type for the requesting client.

    - Happ defaults to the Xray core and can't parse sing-box; the
      `#custom-tunnel-config:` directive makes Happ Desktop use the sing-box
      core with our full profile (one line).
    - Hiddify injects its own tun inbound + route, so an embedded inbound
      breaks it — it gets an outbounds-only fragment.
    - Everything else (sing-box CLI/app, Karing, curl) gets the full profile.
    """
    if "happ" in ua:
        profile = gen_subscription(domain, username, password, compact=True)
        return f"#custom-tunnel-config: {profile}", "text/plain; charset=utf-8"
    if "hiddify" in ua:
        return gen_outbounds(domain, username, password), "application/json"
    return gen_subscription(domain, username, password), "application/json"


@router.get("/sub/{sub_uuid}")
def get_subscription(sub_uuid: str, request: Request, db: Session = Depends(get_db)):
    c = db.query(Client).filter_by(sub_uuid=sub_uuid, enabled=True).first()
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    s = db.query(Settings).first()
    domain = s.domain if s else ""

    ua = request.headers.get("user-agent", "").lower()
    body, media_type = _negotiate(ua, domain, c.username, c.password)

    title = base64.b64encode(c.label.encode()).decode()
    headers = {
        "profile-title": f"base64:{title}",
        "profile-update-interval": "24",
        "content-disposition": f'attachment; filename="{_safe_filename(c.label)}.json"',
    }
    return Response(content=body, media_type=media_type, headers=headers)
