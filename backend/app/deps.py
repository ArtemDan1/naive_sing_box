from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db import get_db
from app.security import decode_token
from app.models import Admin
from app.reloader import DockerReloader, Reloader

_bearer = HTTPBearer(auto_error=False)


def get_reloader() -> Reloader:
    return DockerReloader()


def get_current_admin(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Admin:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing token")
    username = decode_token(creds.credentials)
    if username is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")
    admin = db.query(Admin).filter_by(username=username).first()
    if admin is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unknown admin")
    return admin
