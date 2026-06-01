import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_admin, get_reloader
from app.reloader import Reloader
from app.models import Client
from app.schemas import ClientCreate, ClientUpdate, ClientOut
from app.services import apply_proxy

router = APIRouter(tags=["clients"], dependencies=[Depends(get_current_admin)])


@router.get("/clients", response_model=list[ClientOut])
def list_clients(db: Session = Depends(get_db)):
    return db.query(Client).order_by(Client.id).all()


@router.post("/clients", response_model=ClientOut, status_code=201)
def create_client(
    body: ClientCreate,
    db: Session = Depends(get_db),
    reloader: Reloader = Depends(get_reloader),
):
    c = Client(
        label=body.label,
        username=secrets.token_hex(8),
        password=secrets.token_urlsafe(16),
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    apply_proxy(db, reloader)
    return c


@router.patch("/clients/{client_id}", response_model=ClientOut)
def update_client(
    client_id: int,
    body: ClientUpdate,
    db: Session = Depends(get_db),
    reloader: Reloader = Depends(get_reloader),
):
    c = db.get(Client, client_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    if body.label is not None:
        c.label = body.label
    if body.enabled is not None:
        c.enabled = body.enabled
    db.commit()
    db.refresh(c)
    apply_proxy(db, reloader)
    return c


@router.delete("/clients/{client_id}", status_code=204)
def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
    reloader: Reloader = Depends(get_reloader),
):
    c = db.get(Client, client_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    db.delete(c)
    db.commit()
    apply_proxy(db, reloader)
