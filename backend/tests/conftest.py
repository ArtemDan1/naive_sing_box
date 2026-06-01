import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.deps import get_reloader
from app import models  # noqa: F401
from app.security import hash_password


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)
    db = TestSession()
    db.add(models.Admin(username="admin", password_hash=hash_password("admin")))
    db.commit()
    yield db
    db.close()


@pytest.fixture
def reloader():
    return MagicMock()


@pytest.fixture
def client(db_session, reloader, tmp_path, monkeypatch):
    # Redirect generated config paths into tmp so CRUD endpoints that call
    # apply_singbox/apply_caddy do not touch the real /data filesystem.
    monkeypatch.setattr(
        "app.services.settings.singbox_config_path", str(tmp_path / "config.json")
    )
    monkeypatch.setattr(
        "app.services.settings.caddyfile_path", str(tmp_path / "Caddyfile")
    )
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_reloader] = lambda: reloader
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    resp = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin"}
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
