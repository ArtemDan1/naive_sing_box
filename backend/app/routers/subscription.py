import base64
import re

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Client, Settings
from app.generators import subscription as gen_subscription
from app.generators import subscription_outbounds as gen_outbounds
from app.subpage import is_browser, detect_platform, render_sub_page, render_sub_404

router = APIRouter(tags=["subscription"])

def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")
    return cleaned or "profile"


def _negotiate(ua: str, domain: str, username: str, password: str) -> tuple[str, str]:
    """Pick the subscription body + media type for the requesting client.

    - Hiddify injects its own tun inbound + route, so an embedded inbound
      breaks it — it gets an outbounds-only fragment.
    - Everything else (sing-box CLI/app, Karing, curl) gets the full profile.
    """
    if "hiddify" in ua:
        return gen_outbounds(domain, username, password), "application/json"
    return gen_subscription(domain, username, password), "application/json"


@router.get("/sub/{sub_uuid}")
def get_subscription(sub_uuid: str, request: Request, db: Session = Depends(get_db)):
    ua = request.headers.get("user-agent", "")
    c = db.query(Client).filter_by(sub_uuid=sub_uuid, enabled=True).first()

    if is_browser(ua):
        if c is None:
            return Response(content=render_sub_404(), media_type="text/html", status_code=404)
        s = db.query(Settings).first()
        domain = s.domain if s else ""
        sub_url = f"https://{domain}/sub/{c.sub_uuid}"
        html = render_sub_page(
            label=c.label, sub_url=sub_url, platform=detect_platform(ua)
        )
        return Response(content=html, media_type="text/html")

    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    s = db.query(Settings).first()
    domain = s.domain if s else ""

    body, media_type = _negotiate(ua.lower(), domain, c.username, c.password)

    title = base64.b64encode(c.label.encode()).decode()
    headers = {
        "profile-title": f"base64:{title}",
        "profile-update-interval": "24",
        "content-disposition": f'attachment; filename="{_safe_filename(c.label)}.json"',
    }
    return Response(content=body, media_type=media_type, headers=headers)
