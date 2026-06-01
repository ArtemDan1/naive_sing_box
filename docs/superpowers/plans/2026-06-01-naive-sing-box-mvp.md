# Naive + sing-box MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Панель управления naiveproxy на ядре sing-box: CRUD клиентов, выдача sing-box JSON-подписок по ссылке с uuid, Caddy на 443 с маскировкой и заглушкой, всё в Docker Compose.

**Architecture:** Caddy терминирует TLS (ACME) и маршрутизирует: CONNECT → sing-box (h2c), `/api` и `/sub` → FastAPI, остальное → статичная заглушка. FastAPI хранит данные в Postgres, генерирует `config.json` для sing-box и `Caddyfile`, и перезапускает контейнеры sing-box/caddy через docker socket при изменениях.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, asyncpg/psycopg, python-jose (JWT), passlib[bcrypt], docker SDK, pytest + httpx, Vue 3 + Vite, Caddy 2, sing-box, PostgreSQL 16, Docker Compose.

---

## File Structure

```
backend/
  app/
    __init__.py
    config.py            # Settings из env (pydantic-settings)
    db.py                # engine, SessionLocal, Base, get_db
    models.py            # Admin, Client, Settings (ORM)
    security.py          # hash/verify password, create/decode JWT
    deps.py              # get_current_admin зависимость
    generators.py        # чистые функции: singbox_config, caddyfile, subscription
    reloader.py          # интерфейс перезапуска контейнеров (docker)
    services.py          # бизнес-логика: применить изменения клиентов/домена
    bootstrap.py         # создание админа и settings из env при старте
    main.py              # FastAPI app, роутеры
    routers/
      __init__.py
      auth.py
      clients.py
      settings.py
      subscription.py
    schemas.py           # pydantic-схемы запросов/ответов
  tests/
    conftest.py
    test_generators.py
    test_security.py
    test_auth.py
    test_clients.py
    test_settings.py
    test_subscription.py
  alembic/               # миграции
  alembic.ini
  pyproject.toml
  Dockerfile
frontend/
  src/
    main.js
    api.js
    router.js
    views/Login.vue
    views/Clients.vue
    views/SettingsView.vue
  index.html
  package.json
  vite.config.js
  Dockerfile
caddy/
  Caddyfile.tmpl         # шаблон (генерируется fastapi в runtime в shared volume)
  fallback/index.html    # заглушка
docker-compose.yml
.env.example
```

Деление: `generators.py` — чистые функции (легко тестировать без БД и docker); `reloader.py` — единственное место, знающее про docker (мокается в тестах); роутеры тонкие, логика в `services.py`.

---

## Phase 0 — Scaffold проекта

### Task 0.1: Backend-скелет и зависимости

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py` (пустой)
- Create: `backend/tests/__init__.py` (пустой)

- [ ] **Step 1: Создать `backend/pyproject.toml`**

```toml
[project]
name = "naive-singbox-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "sqlalchemy>=2.0",
  "psycopg[binary]>=3.2",
  "alembic>=1.13",
  "pydantic-settings>=2.4",
  "python-jose[cryptography]>=3.3",
  "passlib[bcrypt]>=1.7",
  "docker>=7.1",
]

[project.optional-dependencies]
dev = ["pytest>=8.3", "httpx>=0.27", "pytest-asyncio>=0.24"]

[tool.pytest.ini_options]
pythonpath = ["."]
asyncio_mode = "auto"
```

- [ ] **Step 2: Создать пустые `backend/app/__init__.py` и `backend/tests/__init__.py`**

```bash
mkdir -p backend/app backend/tests
touch backend/app/__init__.py backend/tests/__init__.py
```

- [ ] **Step 3: Установить зависимости**

Run: `cd backend && python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"`
Expected: установка без ошибок.

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml backend/app backend/tests
git commit -m "chore: backend scaffold and dependencies"
```

---

## Phase 1 — Генераторы конфигов (чистые функции, TDD)

### Task 1.1: Генератор sing-box config.json

**Files:**
- Create: `backend/app/generators.py`
- Test: `backend/tests/test_generators.py`

- [ ] **Step 1: Написать падающий тест**

```python
# backend/tests/test_generators.py
import json
from app.generators import singbox_config

def test_singbox_config_includes_only_given_users():
    users = [
        {"username": "alice", "password": "pw1"},
        {"username": "bob", "password": "pw2"},
    ]
    cfg = json.loads(singbox_config(users))
    inbound = cfg["inbounds"][0]
    assert inbound["type"] == "naive"
    assert inbound["listen"] == "0.0.0.0"
    assert inbound["listen_port"] == 1080
    assert inbound["users"] == users
    assert cfg["outbounds"] == [{"type": "direct"}]

def test_singbox_config_empty_users():
    cfg = json.loads(singbox_config([]))
    assert cfg["inbounds"][0]["users"] == []
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `cd backend && pytest tests/test_generators.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.generators'`.

- [ ] **Step 3: Реализовать**

```python
# backend/app/generators.py
import json

def singbox_config(users: list[dict]) -> str:
    cfg = {
        "log": {"level": "warn"},
        "inbounds": [{
            "type": "naive",
            "tag": "naive-in",
            "listen": "0.0.0.0",
            "listen_port": 1080,
            "network": "tcp",
            "users": users,
        }],
        "outbounds": [{"type": "direct"}],
    }
    return json.dumps(cfg, indent=2)
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `cd backend && pytest tests/test_generators.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/generators.py backend/tests/test_generators.py
git commit -m "feat: sing-box config generator"
```

### Task 1.2: Генератор Caddyfile

**Files:**
- Modify: `backend/app/generators.py`
- Test: `backend/tests/test_generators.py`

- [ ] **Step 1: Добавить падающий тест**

```python
# backend/tests/test_generators.py — добавить
from app.generators import caddyfile

def test_caddyfile_contains_domain_and_routes():
    text = caddyfile("vpn.example.com")
    assert "vpn.example.com {" in text
    assert "@naive method CONNECT" in text
    assert "reverse_proxy h2c://singbox:1080" in text
    assert "handle /api/* { reverse_proxy fastapi:8000 }" in text
    assert "handle /sub/* { reverse_proxy fastapi:8000 }" in text
    assert "/srv/fallback" in text
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `cd backend && pytest tests/test_generators.py::test_caddyfile_contains_domain_and_routes -v`
Expected: FAIL — `ImportError: cannot import name 'caddyfile'`.

- [ ] **Step 3: Реализовать**

```python
# backend/app/generators.py — добавить
def caddyfile(domain: str) -> str:
    return f"""{domain} {{
  @naive method CONNECT
  handle @naive {{ reverse_proxy h2c://singbox:1080 }}
  handle /api/* {{ reverse_proxy fastapi:8000 }}
  handle /sub/* {{ reverse_proxy fastapi:8000 }}
  handle {{ root * /srv/fallback; file_server }}
}}
"""
```

- [ ] **Step 4: Запустить — PASS**

Run: `cd backend && pytest tests/test_generators.py -v`
Expected: PASS (все тесты).

- [ ] **Step 5: Commit**

```bash
git add backend/app/generators.py backend/tests/test_generators.py
git commit -m "feat: Caddyfile generator"
```

### Task 1.3: Генератор подписки sing-box JSON

**Files:**
- Modify: `backend/app/generators.py`
- Test: `backend/tests/test_generators.py`

- [ ] **Step 1: Добавить падающий тест**

```python
# backend/tests/test_generators.py — добавить
from app.generators import subscription

def test_subscription_outbound():
    sub = json.loads(subscription("vpn.example.com", "alice", "pw1"))
    out = sub["outbounds"][0]
    assert out["type"] == "naive"
    assert out["server"] == "vpn.example.com"
    assert out["server_port"] == 443
    assert out["username"] == "alice"
    assert out["password"] == "pw1"
    assert out["tls"] == {"enabled": True, "server_name": "vpn.example.com"}
```

- [ ] **Step 2: Запустить — FAIL**

Run: `cd backend && pytest tests/test_generators.py::test_subscription_outbound -v`
Expected: FAIL — `ImportError: cannot import name 'subscription'`.

- [ ] **Step 3: Реализовать**

```python
# backend/app/generators.py — добавить
def subscription(domain: str, username: str, password: str) -> str:
    cfg = {
        "outbounds": [{
            "type": "naive",
            "tag": "proxy",
            "server": domain,
            "server_port": 443,
            "username": username,
            "password": password,
            "tls": {"enabled": True, "server_name": domain},
        }]
    }
    return json.dumps(cfg, indent=2)
```

- [ ] **Step 4: Запустить — PASS**

Run: `cd backend && pytest tests/test_generators.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/generators.py backend/tests/test_generators.py
git commit -m "feat: subscription generator"
```

---

## Phase 2 — Конфиг, БД, модели

### Task 2.1: Settings из env

**Files:**
- Create: `backend/app/config.py`

- [ ] **Step 1: Реализовать (без теста — тонкая обёртка pydantic-settings)**

```python
# backend/app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://naive:naive@postgres:5432/naive"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 720
    admin_username: str = "admin"
    admin_password: str = "admin"
    domain: str = ""
    singbox_config_path: str = "/data/singbox/config.json"
    caddyfile_path: str = "/data/caddy/Caddyfile"
    singbox_container: str = "singbox"
    caddy_container: str = "caddy"

settings = AppSettings()
```

- [ ] **Step 2: Проверить импорт**

Run: `cd backend && python -c "from app.config import settings; print(settings.jwt_algorithm)"`
Expected: `HS256`.

- [ ] **Step 3: Commit**

```bash
git add backend/app/config.py
git commit -m "feat: app settings from env"
```

### Task 2.2: БД и базовые модели

**Files:**
- Create: `backend/app/db.py`
- Create: `backend/app/models.py`

- [ ] **Step 1: Создать `db.py`**

```python
# backend/app/db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings

class Base(DeclarativeBase):
    pass

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 2: Создать `models.py`**

```python
# backend/app/models.py
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base

def _now() -> datetime:
    return datetime.now(timezone.utc)

class Admin(Base):
    __tablename__ = "admins"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

class Client(Base):
    __tablename__ = "clients"
    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    password: Mapped[str] = mapped_column(String)
    sub_uuid: Mapped[str] = mapped_column(String, unique=True, index=True,
                                          default=lambda: uuid.uuid4().hex)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

class Settings(Base):
    __tablename__ = "settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    domain: Mapped[str] = mapped_column(String, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=_now, onupdate=_now)
```

- [ ] **Step 3: Проверить импорт**

Run: `cd backend && python -c "from app.models import Admin, Client, Settings; print('ok')"`
Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/db.py backend/app/models.py
git commit -m "feat: db engine and ORM models"
```

### Task 2.3: Alembic-миграция начальной схемы

**Files:**
- Create: `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/versions/0001_init.py`

- [ ] **Step 1: Инициализировать alembic**

Run: `cd backend && alembic init alembic`
Expected: созданы `alembic.ini` и `alembic/`.

- [ ] **Step 2: Настроить `alembic/env.py` на наши модели**

Заменить в `alembic/env.py` секцию target_metadata:

```python
# alembic/env.py — около начала, после импортов
from app.db import Base
from app import models  # noqa: F401  регистрирует таблицы
from app.config import settings as app_settings
target_metadata = Base.metadata
config.set_main_option("sqlalchemy.url", app_settings.database_url)
```

- [ ] **Step 3: Сгенерировать миграцию**

Run: `cd backend && alembic revision --autogenerate -m "init"`
Expected: файл в `alembic/versions/` с тремя таблицами. Переименовать в `0001_init.py` при желании.

- [ ] **Step 4: Commit**

```bash
git add backend/alembic.ini backend/alembic
git commit -m "feat: initial alembic migration"
```

---

## Phase 3 — Безопасность (TDD)

### Task 3.1: Хеширование паролей и JWT

**Files:**
- Create: `backend/app/security.py`
- Test: `backend/tests/test_security.py`

- [ ] **Step 1: Написать падающий тест**

```python
# backend/tests/test_security.py
from app.security import hash_password, verify_password, create_token, decode_token

def test_password_roundtrip():
    h = hash_password("secret")
    assert h != "secret"
    assert verify_password("secret", h)
    assert not verify_password("wrong", h)

def test_jwt_roundtrip():
    token = create_token("admin")
    assert decode_token(token) == "admin"

def test_decode_invalid_returns_none():
    assert decode_token("garbage") is None
```

- [ ] **Step 2: Запустить — FAIL**

Run: `cd backend && pytest tests/test_security.py -v`
Expected: FAIL — модуль не найден.

- [ ] **Step 3: Реализовать**

```python
# backend/app/security.py
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.config import settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(p: str) -> str:
    return _pwd.hash(p)

def verify_password(p: str, h: str) -> bool:
    return _pwd.verify(p, h)

def create_token(username: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": username, "exp": exp}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

def decode_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload.get("sub")
    except JWTError:
        return None
```

- [ ] **Step 4: Запустить — PASS**

Run: `cd backend && pytest tests/test_security.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/security.py backend/tests/test_security.py
git commit -m "feat: password hashing and JWT helpers"
```

---

## Phase 4 — Reloader и сервисный слой

### Task 4.1: Reloader (интерфейс перезапуска контейнеров)

**Files:**
- Create: `backend/app/reloader.py`
- Test: `backend/tests/test_reloader.py`

- [ ] **Step 1: Написать падающий тест (с моком docker)**

```python
# backend/tests/test_reloader.py
from unittest.mock import MagicMock
from app.reloader import DockerReloader

def test_restart_calls_docker_container_restart():
    fake_client = MagicMock()
    r = DockerReloader(client=fake_client)
    r.restart("singbox")
    fake_client.containers.get.assert_called_once_with("singbox")
    fake_client.containers.get.return_value.restart.assert_called_once()
```

- [ ] **Step 2: Запустить — FAIL**

Run: `cd backend && pytest tests/test_reloader.py -v`
Expected: FAIL — модуль не найден.

- [ ] **Step 3: Реализовать**

```python
# backend/app/reloader.py
from typing import Protocol

class Reloader(Protocol):
    def restart(self, container: str) -> None: ...

class DockerReloader:
    def __init__(self, client=None):
        if client is None:
            import docker
            client = docker.from_env()
        self._client = client

    def restart(self, container: str) -> None:
        self._client.containers.get(container).restart()
```

- [ ] **Step 4: Запустить — PASS**

Run: `cd backend && pytest tests/test_reloader.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/reloader.py backend/tests/test_reloader.py
git commit -m "feat: docker container reloader"
```

### Task 4.2: Сервисы применения конфигов

**Files:**
- Create: `backend/app/services.py`
- Test: `backend/tests/test_services.py`

`apply_singbox` берёт активных клиентов из БД, пишет config.json, рестартит sing-box. `apply_caddy` пишет Caddyfile из домена, рестартит caddy. Запись файла и reloader инжектятся для тестируемости.

- [ ] **Step 1: Написать падающий тест**

```python
# backend/tests/test_services.py
from unittest.mock import MagicMock
import json
from app import services
from app.models import Client, Settings

def test_apply_singbox_writes_enabled_users_and_restarts(tmp_path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    monkeypatch.setattr(services.settings, "singbox_config_path", str(cfg_file))
    monkeypatch.setattr(services.settings, "singbox_container", "singbox")

    db = MagicMock()
    db.query.return_value.filter_by.return_value.all.return_value = [
        Client(label="a", username="alice", password="pw1", sub_uuid="x", enabled=True),
    ]
    reloader = MagicMock()

    services.apply_singbox(db, reloader)

    written = json.loads(cfg_file.read_text())
    assert written["inbounds"][0]["users"] == [{"username": "alice", "password": "pw1"}]
    reloader.restart.assert_called_once_with("singbox")

def test_apply_caddy_writes_file_and_restarts(tmp_path, monkeypatch):
    cf = tmp_path / "Caddyfile"
    monkeypatch.setattr(services.settings, "caddyfile_path", str(cf))
    monkeypatch.setattr(services.settings, "caddy_container", "caddy")
    reloader = MagicMock()

    services.apply_caddy("vpn.example.com", reloader)

    assert "vpn.example.com {" in cf.read_text()
    reloader.restart.assert_called_once_with("caddy")
```

- [ ] **Step 2: Запустить — FAIL**

Run: `cd backend && pytest tests/test_services.py -v`
Expected: FAIL — модуль не найден.

- [ ] **Step 3: Реализовать**

```python
# backend/app/services.py
import os
from sqlalchemy.orm import Session
from app.config import settings
from app.generators import singbox_config, caddyfile
from app.models import Client
from app.reloader import Reloader

def _write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)

def apply_singbox(db: Session, reloader: Reloader) -> None:
    clients = db.query(Client).filter_by(enabled=True).all()
    users = [{"username": c.username, "password": c.password} for c in clients]
    _write(settings.singbox_config_path, singbox_config(users))
    reloader.restart(settings.singbox_container)

def apply_caddy(domain: str, reloader: Reloader) -> None:
    _write(settings.caddyfile_path, caddyfile(domain))
    reloader.restart(settings.caddy_container)
```

- [ ] **Step 4: Запустить — PASS**

Run: `cd backend && pytest tests/test_services.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services.py backend/tests/test_services.py
git commit -m "feat: services to apply sing-box and caddy configs"
```

---

## Phase 5 — API: схемы, зависимости, роутеры

### Task 5.1: Pydantic-схемы и зависимость авторизации

**Files:**
- Create: `backend/app/schemas.py`
- Create: `backend/app/deps.py`

- [ ] **Step 1: Создать `schemas.py`**

```python
# backend/app/schemas.py
from datetime import datetime
from pydantic import BaseModel

class LoginIn(BaseModel):
    username: str
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

class ClientCreate(BaseModel):
    label: str

class ClientUpdate(BaseModel):
    label: str | None = None
    enabled: bool | None = None

class ClientOut(BaseModel):
    id: int
    label: str
    username: str
    sub_uuid: str
    enabled: bool
    created_at: datetime
    class Config:
        from_attributes = True

class SettingsIn(BaseModel):
    domain: str

class SettingsOut(BaseModel):
    domain: str
```

- [ ] **Step 2: Создать `deps.py`**

```python
# backend/app/deps.py
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
```

- [ ] **Step 3: Проверить импорт**

Run: `cd backend && python -c "from app import schemas, deps; print('ok')"`
Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas.py backend/app/deps.py
git commit -m "feat: pydantic schemas and auth dependency"
```

### Task 5.2: conftest с тестовой БД и app-фабрикой

**Files:**
- Create: `backend/app/main.py` (app-фабрика)
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: Создать `main.py` с фабрикой (роутеры подключим в следующих задачах)**

```python
# backend/app/main.py
from fastapi import FastAPI

def create_app() -> FastAPI:
    app = FastAPI(title="naive-singbox")
    from app.routers import auth, clients, settings as settings_router, subscription
    app.include_router(auth.router, prefix="/api")
    app.include_router(clients.router, prefix="/api")
    app.include_router(settings_router.router, prefix="/api")
    app.include_router(subscription.router)
    return app

app = create_app()
```

- [ ] **Step 2: Создать `conftest.py` (SQLite in-memory, переопределение зависимостей)**

```python
# backend/tests/conftest.py
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.deps import get_reloader
from app import models  # noqa
from app.security import hash_password

@pytest.fixture
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)
    db = TestSession()
    # стартовый админ
    db.add(models.Admin(username="admin", password_hash=hash_password("admin")))
    db.commit()
    yield db
    db.close()

@pytest.fixture
def reloader():
    return MagicMock()

@pytest.fixture
def client(db_session, reloader, monkeypatch):
    # сервисы пишут файлы — направим в tmp через monkeypatch в самих тестах при надобности
    from app.main import create_app
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_reloader] = lambda: reloader
    return TestClient(app)

@pytest.fixture
def auth_headers(client):
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
```

- [ ] **Step 3: Commit (тесты пока не запускаем — роутеров нет)**

```bash
git add backend/app/main.py backend/tests/conftest.py
git commit -m "test: app factory and test fixtures"
```

### Task 5.3: Роутер auth (TDD)

**Files:**
- Create: `backend/app/routers/__init__.py` (пустой)
- Create: `backend/app/routers/auth.py`
- Test: `backend/tests/test_auth.py`

- [ ] **Step 1: Написать падающий тест**

```python
# backend/tests/test_auth.py
def test_login_success(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 200
    assert r.json()["access_token"]

def test_login_wrong_password(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "nope"})
    assert r.status_code == 401

def test_protected_requires_token(client):
    r = client.get("/api/clients")
    assert r.status_code == 401
```

- [ ] **Step 2: Запустить — FAIL**

Run: `cd backend && pytest tests/test_auth.py -v`
Expected: FAIL — нет роутера/эндпоинтов (ImportError при сборке app).

- [ ] **Step 3: Реализовать**

```python
# backend/app/routers/__init__.py  (пустой файл)
```

```python
# backend/app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Admin
from app.schemas import LoginIn, TokenOut
from app.security import verify_password, create_token

router = APIRouter(tags=["auth"])

@router.post("/auth/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    admin = db.query(Admin).filter_by(username=body.username).first()
    if admin is None or not verify_password(body.password, admin.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad credentials")
    return TokenOut(access_token=create_token(admin.username))
```

- [ ] **Step 4: Запустить — PASS** (`test_protected_requires_token` пройдёт, т.к. clients-роутер с зависимостью добавим в 5.4; временно он отсутствует → эндпоинт `/api/clients` вернёт 404, не 401)

> Примечание: чтобы `test_protected_requires_token` был валиден, эту проверку перенести в `test_clients.py` после Task 5.4. Здесь оставить только два теста login. Обновить `test_auth.py`, удалив `test_protected_requires_token`.

Run: `cd backend && pytest tests/test_auth.py -v`
Expected: PASS (2 теста login).

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/__init__.py backend/app/routers/auth.py backend/tests/test_auth.py
git commit -m "feat: auth login endpoint"
```

### Task 5.4: Роутер clients (TDD)

**Files:**
- Create: `backend/app/routers/clients.py`
- Test: `backend/tests/test_clients.py`

- [ ] **Step 1: Написать падающий тест**

```python
# backend/tests/test_clients.py
def test_requires_token(client):
    assert client.get("/api/clients").status_code == 401

def test_create_list_update_delete(client, auth_headers, reloader):
    # create
    r = client.post("/api/clients", json={"label": "Phone"}, headers=auth_headers)
    assert r.status_code == 201
    c = r.json()
    assert c["label"] == "Phone"
    assert c["username"] and c["sub_uuid"] and c["enabled"] is True
    cid = c["id"]
    assert reloader.restart.called  # sing-box перезапущен

    # list
    r = client.get("/api/clients", headers=auth_headers)
    assert r.status_code == 200 and len(r.json()) == 1

    # disable
    r = client.patch(f"/api/clients/{cid}", json={"enabled": False}, headers=auth_headers)
    assert r.status_code == 200 and r.json()["enabled"] is False

    # delete
    r = client.delete(f"/api/clients/{cid}", headers=auth_headers)
    assert r.status_code == 204
    assert client.get("/api/clients", headers=auth_headers).json() == []
```

- [ ] **Step 2: Запустить — FAIL**

Run: `cd backend && pytest tests/test_clients.py -v`
Expected: FAIL — нет роутера clients.

- [ ] **Step 3: Реализовать**

```python
# backend/app/routers/clients.py
import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db import get_db
from app.deps import get_current_admin, get_reloader
from app.reloader import Reloader
from app.models import Client
from app.schemas import ClientCreate, ClientUpdate, ClientOut
from app.services import apply_singbox

router = APIRouter(tags=["clients"], dependencies=[Depends(get_current_admin)])

@router.get("/clients", response_model=list[ClientOut])
def list_clients(db: Session = Depends(get_db)):
    return db.query(Client).order_by(Client.id).all()

@router.post("/clients", response_model=ClientOut, status_code=201)
def create_client(body: ClientCreate, db: Session = Depends(get_db),
                  reloader: Reloader = Depends(get_reloader)):
    c = Client(label=body.label,
               username=secrets.token_hex(8),
               password=secrets.token_urlsafe(16))
    db.add(c)
    db.commit()
    db.refresh(c)
    apply_singbox(db, reloader)
    return c

@router.patch("/clients/{client_id}", response_model=ClientOut)
def update_client(client_id: int, body: ClientUpdate, db: Session = Depends(get_db),
                  reloader: Reloader = Depends(get_reloader)):
    c = db.get(Client, client_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    if body.label is not None:
        c.label = body.label
    if body.enabled is not None:
        c.enabled = body.enabled
    db.commit()
    db.refresh(c)
    apply_singbox(db, reloader)
    return c

@router.delete("/clients/{client_id}", status_code=204)
def delete_client(client_id: int, db: Session = Depends(get_db),
                  reloader: Reloader = Depends(get_reloader)):
    c = db.get(Client, client_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    db.delete(c)
    db.commit()
    apply_singbox(db, reloader)
```

> `apply_singbox` пишет файл по `settings.singbox_config_path`. В тестах задать его в tmp: добавить в `conftest.py` `client`-фикстуру `monkeypatch.setattr` на временный путь, либо в `test_clients.py` использовать `monkeypatch` для `app.services.settings.singbox_config_path`. Добавить в начало `test_create_list_update_delete` фикстуру `tmp_path`/`monkeypatch`, установив `monkeypatch.setattr("app.services.settings.singbox_config_path", str(tmp_path/"c.json"))`.

- [ ] **Step 4: Запустить — PASS**

Run: `cd backend && pytest tests/test_clients.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/clients.py backend/tests/test_clients.py
git commit -m "feat: clients CRUD endpoints"
```

### Task 5.5: Роутер settings (TDD)

**Files:**
- Create: `backend/app/routers/settings.py`
- Test: `backend/tests/test_settings.py`

- [ ] **Step 1: Написать падающий тест**

```python
# backend/tests/test_settings.py
def test_get_default_domain_empty(client, auth_headers):
    r = client.get("/api/settings", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["domain"] == ""

def test_put_domain_applies_caddy(client, auth_headers, reloader, monkeypatch, tmp_path):
    monkeypatch.setattr("app.services.settings.caddyfile_path", str(tmp_path / "Caddyfile"))
    r = client.put("/api/settings", json={"domain": "vpn.example.com"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["domain"] == "vpn.example.com"
    reloader.restart.assert_called_with("caddy")
    r2 = client.get("/api/settings", headers=auth_headers)
    assert r2.json()["domain"] == "vpn.example.com"
```

- [ ] **Step 2: Запустить — FAIL**

Run: `cd backend && pytest tests/test_settings.py -v`
Expected: FAIL — нет роутера settings.

- [ ] **Step 3: Реализовать**

```python
# backend/app/routers/settings.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.deps import get_current_admin, get_reloader
from app.reloader import Reloader
from app.models import Settings
from app.schemas import SettingsIn, SettingsOut
from app.services import apply_caddy

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
def put_settings(body: SettingsIn, db: Session = Depends(get_db),
                 reloader: Reloader = Depends(get_reloader)):
    s = _get_or_create(db)
    s.domain = body.domain
    db.commit()
    apply_caddy(body.domain, reloader)
    return SettingsOut(domain=s.domain)
```

- [ ] **Step 4: Запустить — PASS**

Run: `cd backend && pytest tests/test_settings.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/settings.py backend/tests/test_settings.py
git commit -m "feat: settings (domain) endpoints"
```

### Task 5.6: Роутер subscription (TDD)

**Files:**
- Create: `backend/app/routers/subscription.py`
- Test: `backend/tests/test_subscription.py`

- [ ] **Step 1: Написать падающий тест**

```python
# backend/tests/test_subscription.py
import json
from app.models import Client, Settings

def _seed_domain(db, domain="vpn.example.com"):
    db.add(Settings(domain=domain)); db.commit()

def test_subscription_returns_profile(client, db_session):
    _seed_domain(db_session)
    db_session.add(Client(label="a", username="alice", password="pw1",
                          sub_uuid="abc", enabled=True))
    db_session.commit()
    r = client.get("/sub/abc")
    assert r.status_code == 200
    out = json.loads(r.text)["outbounds"][0]
    assert out["server"] == "vpn.example.com"
    assert out["username"] == "alice"

def test_subscription_unknown_uuid_404(client, db_session):
    _seed_domain(db_session)
    assert client.get("/sub/nope").status_code == 404

def test_subscription_disabled_404(client, db_session):
    _seed_domain(db_session)
    db_session.add(Client(label="a", username="alice", password="pw1",
                          sub_uuid="abc", enabled=False))
    db_session.commit()
    assert client.get("/sub/abc").status_code == 404
```

- [ ] **Step 2: Запустить — FAIL**

Run: `cd backend && pytest tests/test_subscription.py -v`
Expected: FAIL — нет роутера subscription.

- [ ] **Step 3: Реализовать**

```python
# backend/app/routers/subscription.py
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
```

- [ ] **Step 4: Запустить — PASS (весь backend)**

Run: `cd backend && pytest -v`
Expected: PASS (все тесты).

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/subscription.py backend/tests/test_subscription.py
git commit -m "feat: subscription endpoint"
```

---

## Phase 6 — Bootstrap при старте

### Task 6.1: Создание админа и settings из env

**Files:**
- Create: `backend/app/bootstrap.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_bootstrap.py`

- [ ] **Step 1: Написать падающий тест**

```python
# backend/tests/test_bootstrap.py
from unittest.mock import MagicMock
from app import bootstrap
from app.models import Admin, Settings

def test_bootstrap_creates_admin_and_settings(db_session, monkeypatch):
    monkeypatch.setattr(bootstrap.settings, "admin_username", "root")
    monkeypatch.setattr(bootstrap.settings, "admin_password", "rootpw")
    monkeypatch.setattr(bootstrap.settings, "domain", "vpn.example.com")
    # удалить стартового админа из фикстуры
    db_session.query(Admin).delete(); db_session.commit()

    bootstrap.run(db_session, reloader=MagicMock())

    assert db_session.query(Admin).filter_by(username="root").first() is not None
    assert db_session.query(Settings).first().domain == "vpn.example.com"

def test_bootstrap_idempotent(db_session, monkeypatch):
    monkeypatch.setattr(bootstrap.settings, "domain", "")
    bootstrap.run(db_session, reloader=MagicMock())
    bootstrap.run(db_session, reloader=MagicMock())
    assert db_session.query(Admin).count() == 1
```

- [ ] **Step 2: Запустить — FAIL**

Run: `cd backend && pytest tests/test_bootstrap.py -v`
Expected: FAIL — модуль не найден.

- [ ] **Step 3: Реализовать**

```python
# backend/app/bootstrap.py
from sqlalchemy.orm import Session
from app.config import settings
from app.models import Admin, Settings
from app.security import hash_password
from app.reloader import Reloader
from app.services import apply_caddy, apply_singbox

def run(db: Session, reloader: Reloader) -> None:
    if db.query(Admin).count() == 0:
        db.add(Admin(username=settings.admin_username,
                     password_hash=hash_password(settings.admin_password)))
        db.commit()
    if db.query(Settings).first() is None:
        db.add(Settings(domain=settings.domain))
        db.commit()
    s = db.query(Settings).first()
    # сгенерировать конфиги на старте (без рестарта, если контейнеры ещё не подняты — допустимо)
    try:
        if s.domain:
            apply_caddy(s.domain, reloader)
        apply_singbox(db, reloader)
    except Exception:
        pass  # на самом первом старте контейнеры могут быть недоступны
```

```python
# backend/app/main.py — добавить startup-хук
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    from app.db import SessionLocal
    from app.bootstrap import run
    from app.reloader import DockerReloader
    db = SessionLocal()
    try:
        run(db, DockerReloader())
    finally:
        db.close()
    yield

def create_app() -> FastAPI:
    app = FastAPI(title="naive-singbox", lifespan=lifespan)
    ...
```

- [ ] **Step 4: Запустить — PASS**

Run: `cd backend && pytest tests/test_bootstrap.py -v`
Expected: PASS.

> Примечание: `lifespan` вызывает реальный `DockerReloader()` и `SessionLocal` (Postgres) — в юнит-тестах app мы это не триггерим, т.к. TestClient в фикстуре не входит в `with`-контекст (события lifespan не запускаются при простом инстанцировании). Если используется `with TestClient(app)`, добавить мок. Текущая фикстура `client` создаёт TestClient без `with`, lifespan не выполняется — тесты не затрагиваются.

- [ ] **Step 5: Commit**

```bash
git add backend/app/bootstrap.py backend/app/main.py backend/tests/test_bootstrap.py
git commit -m "feat: startup bootstrap of admin, settings and configs"
```

### Task 6.2: Backend Dockerfile и entrypoint (миграции + uvicorn)

**Files:**
- Create: `backend/Dockerfile`
- Create: `backend/entrypoint.sh`

- [ ] **Step 1: Создать `Dockerfile`**

```dockerfile
# backend/Dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .
COPY . .
RUN chmod +x entrypoint.sh
EXPOSE 8000
CMD ["./entrypoint.sh"]
```

- [ ] **Step 2: Создать `entrypoint.sh`**

```bash
#!/usr/bin/env bash
set -e
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- [ ] **Step 3: Commit**

```bash
git add backend/Dockerfile backend/entrypoint.sh
git commit -m "build: backend Dockerfile and entrypoint"
```

---

## Phase 7 — Frontend (Vue 3 + Vite)

### Task 7.1: Каркас Vue + роутер + API-клиент

**Files:**
- Create: `frontend/package.json`, `frontend/vite.config.js`, `frontend/index.html`
- Create: `frontend/src/main.js`, `frontend/src/router.js`, `frontend/src/api.js`

- [ ] **Step 1: `package.json`**

```json
{
  "name": "naive-singbox-frontend",
  "private": true,
  "type": "module",
  "scripts": { "dev": "vite", "build": "vite build", "preview": "vite preview" },
  "dependencies": { "vue": "^3.4", "vue-router": "^4.3" },
  "devDependencies": { "vite": "^5.3", "@vitejs/plugin-vue": "^5.0" }
}
```

- [ ] **Step 2: `vite.config.js`**

```js
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
export default defineConfig({
  plugins: [vue()],
  server: { proxy: { '/api': 'http://localhost:8000' } },
})
```

- [ ] **Step 3: `index.html`**

```html
<!doctype html>
<html><head><meta charset="utf-8"><title>Naive Admin</title></head>
<body><div id="app"></div><script type="module" src="/src/main.js"></script></body></html>
```

- [ ] **Step 4: `src/api.js` (fetch-обёртка с токеном)**

```js
const tokenKey = 'token'
export function setToken(t) { localStorage.setItem(tokenKey, t) }
export function getToken() { return localStorage.getItem(tokenKey) }
export function logout() { localStorage.removeItem(tokenKey) }

async function req(method, url, body) {
  const headers = { 'Content-Type': 'application/json' }
  const t = getToken()
  if (t) headers['Authorization'] = `Bearer ${t}`
  const res = await fetch(url, { method, headers, body: body ? JSON.stringify(body) : undefined })
  if (res.status === 401) { logout(); location.hash = '#/login' }
  if (!res.ok && res.status !== 204) throw new Error(`HTTP ${res.status}`)
  return res.status === 204 ? null : res.json()
}
export const api = {
  login: (u, p) => req('POST', '/api/auth/login', { username: u, password: p }),
  clients: () => req('GET', '/api/clients'),
  createClient: (label) => req('POST', '/api/clients', { label }),
  updateClient: (id, patch) => req('PATCH', `/api/clients/${id}`, patch),
  deleteClient: (id) => req('DELETE', `/api/clients/${id}`),
  getSettings: () => req('GET', '/api/settings'),
  putSettings: (domain) => req('PUT', '/api/settings', { domain }),
}
```

- [ ] **Step 5: `src/router.js` и `src/main.js`**

```js
// src/router.js
import { createRouter, createWebHashHistory } from 'vue-router'
import Login from './views/Login.vue'
import Clients from './views/Clients.vue'
import SettingsView from './views/SettingsView.vue'
import { getToken } from './api'

const routes = [
  { path: '/login', component: Login },
  { path: '/', component: Clients },
  { path: '/settings', component: SettingsView },
]
const router = createRouter({ history: createWebHashHistory(), routes })
router.beforeEach((to) => {
  if (to.path !== '/login' && !getToken()) return '/login'
})
export default router
```

```js
// src/main.js
import { createApp } from 'vue'
import router from './router'
import App from './App.vue'
createApp(App).use(router).mount('#app')
```

- [ ] **Step 6: `src/App.vue`**

```vue
<template>
  <nav v-if="$route.path !== '/login'">
    <router-link to="/">Клиенты</router-link> |
    <router-link to="/settings">Настройки</router-link> |
    <a href="#" @click.prevent="doLogout">Выйти</a>
  </nav>
  <router-view />
</template>
<script setup>
import { useRouter } from 'vue-router'
import { logout } from './api'
const router = useRouter()
function doLogout() { logout(); router.push('/login') }
</script>
```

- [ ] **Step 7: Установить и проверить сборку**

Run: `cd frontend && npm install && npm run build`
Expected: успешная сборка (после создания view-компонентов в 7.2 — если падает на отсутствующих view, выполнить 7.2 до сборки).

- [ ] **Step 8: Commit**

```bash
git add frontend/package.json frontend/vite.config.js frontend/index.html frontend/src/main.js frontend/src/router.js frontend/src/api.js frontend/src/App.vue
git commit -m "feat: frontend scaffold, router and api client"
```

### Task 7.2: Экраны Login, Clients, Settings

**Files:**
- Create: `frontend/src/views/Login.vue`, `Clients.vue`, `SettingsView.vue`

- [ ] **Step 1: `views/Login.vue`**

```vue
<template>
  <form @submit.prevent="submit">
    <h2>Вход</h2>
    <input v-model="username" placeholder="Логин" />
    <input v-model="password" type="password" placeholder="Пароль" />
    <button>Войти</button>
    <p v-if="error" style="color:red">{{ error }}</p>
  </form>
</template>
<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, setToken } from '../api'
const username = ref(''), password = ref(''), error = ref('')
const router = useRouter()
async function submit() {
  try {
    const { access_token } = await api.login(username.value, password.value)
    setToken(access_token); router.push('/')
  } catch { error.value = 'Неверный логин или пароль' }
}
</script>
```

- [ ] **Step 2: `views/Clients.vue`**

```vue
<template>
  <h2>Клиенты</h2>
  <form @submit.prevent="add">
    <input v-model="label" placeholder="Имя клиента" />
    <button>Добавить</button>
  </form>
  <table border="1" cellpadding="6">
    <tr><th>Имя</th><th>Логин</th><th>Подписка</th><th>Вкл</th><th></th></tr>
    <tr v-for="c in clients" :key="c.id">
      <td>{{ c.label }}</td>
      <td>{{ c.username }}</td>
      <td><a :href="subUrl(c)" target="_blank">ссылка</a></td>
      <td><input type="checkbox" :checked="c.enabled" @change="toggle(c)" /></td>
      <td><button @click="remove(c)">Удалить</button></td>
    </tr>
  </table>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
const clients = ref([]), label = ref('')
async function load() { clients.value = await api.clients() }
async function add() { if (label.value) { await api.createClient(label.value); label.value=''; await load() } }
async function toggle(c) { await api.updateClient(c.id, { enabled: !c.enabled }); await load() }
async function remove(c) { await api.deleteClient(c.id); await load() }
function subUrl(c) { return `${location.origin}/sub/${c.sub_uuid}` }
onMounted(load)
</script>
```

- [ ] **Step 3: `views/SettingsView.vue`**

```vue
<template>
  <h2>Настройки</h2>
  <form @submit.prevent="save">
    <label>Домен: <input v-model="domain" placeholder="vpn.example.com" /></label>
    <button>Сохранить</button>
    <p v-if="saved" style="color:green">Сохранено (Caddy перезапущен)</p>
  </form>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
const domain = ref(''), saved = ref(false)
onMounted(async () => { domain.value = (await api.getSettings()).domain })
async function save() { await api.putSettings(domain.value); saved.value = true }
</script>
```

- [ ] **Step 4: Сборка**

Run: `cd frontend && npm run build`
Expected: `dist/` собран без ошибок.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views
git commit -m "feat: login, clients and settings views"
```

### Task 7.3: Frontend Dockerfile (сборка статики в том caddy)

**Files:**
- Create: `frontend/Dockerfile`

Фронт собирается в статику; caddy её НЕ отдаёт напрямую (caddy отдаёт fallback для не-API трафика). Поэтому админка отдаётся отдельным путём: проще всего отдавать статику через тот же FastAPI на корне домена под отдельным префиксом. Для MVP отдаём статику Vite через nginx-контейнер, доступный только локально, а caddy проксирует на него по пути `/admin/*`.

> Решение для MVP: добавить в Caddyfile маршрут `handle /admin/* { reverse_proxy frontend:80 }` и собрать фронт в nginx. Обновить генератор Caddyfile (см. Task 7.4).

- [ ] **Step 1: `frontend/Dockerfile` (multi-stage build → nginx)**

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
```

- [ ] **Step 2: Учесть base path** — в `vite.config.js` добавить `base: '/admin/'`, иначе ассеты не найдутся под `/admin/`.

```js
export default defineConfig({
  base: '/admin/',
  plugins: [vue()],
  server: { proxy: { '/api': 'http://localhost:8000' } },
})
```

- [ ] **Step 3: Commit**

```bash
git add frontend/Dockerfile frontend/vite.config.js
git commit -m "build: frontend Dockerfile served via nginx under /admin"
```

### Task 7.4: Обновить генератор Caddyfile под /admin

**Files:**
- Modify: `backend/app/generators.py`
- Modify: `backend/tests/test_generators.py`

- [ ] **Step 1: Обновить тест caddyfile**

```python
# в test_caddyfile_contains_domain_and_routes добавить:
    assert "handle /admin/* { reverse_proxy frontend:80 }" in text
```

- [ ] **Step 2: Запустить — FAIL**

Run: `cd backend && pytest tests/test_generators.py::test_caddyfile_contains_domain_and_routes -v`
Expected: FAIL.

- [ ] **Step 3: Обновить генератор**

```python
def caddyfile(domain: str) -> str:
    return f"""{domain} {{
  @naive method CONNECT
  handle @naive {{ reverse_proxy h2c://singbox:1080 }}
  handle /api/* {{ reverse_proxy fastapi:8000 }}
  handle /sub/* {{ reverse_proxy fastapi:8000 }}
  handle /admin/* {{ reverse_proxy frontend:80 }}
  handle {{ root * /srv/fallback; file_server }}
}}
"""
```

- [ ] **Step 4: Запустить — PASS**

Run: `cd backend && pytest tests/test_generators.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/generators.py backend/tests/test_generators.py
git commit -m "feat: route /admin to frontend in Caddyfile"
```

---

## Phase 8 — Инфраструктура: заглушка, compose, env

### Task 8.1: Статичная заглушка

**Files:**
- Create: `caddy/fallback/index.html`

- [ ] **Step 1: Создать нейтральную страницу**

```html
<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Welcome</title>
<style>body{font-family:system-ui;margin:0;display:grid;place-items:center;height:100vh;background:#fafafa;color:#333}</style>
</head><body><main><h1>It works!</h1><p>This website is under construction.</p></main></body></html>
```

- [ ] **Step 2: Commit**

```bash
git add caddy/fallback/index.html
git commit -m "feat: fallback masking page"
```

### Task 8.2: docker-compose.yml

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example`

- [ ] **Step 1: Создать `.env.example`**

```env
DATABASE_URL=postgresql+psycopg://naive:naive@postgres:5432/naive
JWT_SECRET=replace-with-long-random-string
ADMIN_USERNAME=admin
ADMIN_PASSWORD=replace-me
DOMAIN=vpn.example.com
POSTGRES_USER=naive
POSTGRES_PASSWORD=naive
POSTGRES_DB=naive
```

- [ ] **Step 2: Создать `docker-compose.yml`**

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes: [pgdata:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 5s
      retries: 10

  fastapi:
    build: ./backend
    environment:
      DATABASE_URL: ${DATABASE_URL}
      JWT_SECRET: ${JWT_SECRET}
      ADMIN_USERNAME: ${ADMIN_USERNAME}
      ADMIN_PASSWORD: ${ADMIN_PASSWORD}
      DOMAIN: ${DOMAIN}
      SINGBOX_CONFIG_PATH: /data/singbox/config.json
      CADDYFILE_PATH: /data/caddy/Caddyfile
      SINGBOX_CONTAINER: singbox
      CADDY_CONTAINER: caddy
    volumes:
      - singbox_conf:/data/singbox
      - caddy_conf:/data/caddy
      - /var/run/docker.sock:/var/run/docker.sock
    depends_on:
      postgres: { condition: service_healthy }

  singbox:
    image: ghcr.io/sagernet/sing-box:latest
    container_name: singbox
    command: ["run", "-c", "/etc/sing-box/config.json"]
    volumes:
      - singbox_conf:/etc/sing-box
    restart: unless-stopped

  caddy:
    image: caddy:2
    container_name: caddy
    ports: ["80:80", "443:443"]
    command: ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
    volumes:
      - caddy_conf:/etc/caddy
      - ./caddy/fallback:/srv/fallback:ro
      - caddy_data:/data
    depends_on: [fastapi, singbox]
    restart: unless-stopped

  frontend:
    build: ./frontend
    restart: unless-stopped

volumes:
  pgdata:
  singbox_conf:
  caddy_conf:
  caddy_data:
```

> Порядок старта: fastapi на старте (lifespan→bootstrap) генерирует `config.json` и `Caddyfile` в shared volumes ДО того, как sing-box/caddy успешно прочитают их. Поскольку singbox/caddy зависят от fastapi и имеют `restart: unless-stopped`, они перезапустятся и подхватят сгенерированные файлы. Это допустимо для MVP.

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml .env.example
git commit -m "build: docker-compose stack"
```

### Task 8.3: Ручная проверка end-to-end

**Files:** (нет — ручная проверка)

- [ ] **Step 1: Подготовить env**

Run: `cp .env.example .env` и заполнить `DOMAIN` реальным доменом (A-запись на сервер), `JWT_SECRET`, `ADMIN_PASSWORD`.

- [ ] **Step 2: Поднять стек**

Run: `docker compose up -d --build`
Expected: все контейнеры `healthy`/`running`. Проверить `docker compose logs caddy` — получен ACME-сертификат.

- [ ] **Step 3: Проверить заглушку**

Run: `curl -I https://<domain>/`
Expected: 200, HTML заглушки.

- [ ] **Step 4: Войти в админку**

Открыть `https://<domain>/admin/` → залогиниться → добавить клиента → скопировать ссылку подписки.

- [ ] **Step 5: Проверить подписку**

Run: `curl https://<domain>/sub/<uuid>`
Expected: sing-box JSON с правильным `server` = домен.

- [ ] **Step 6: Проверить прокси**

Импортировать подписку в sing-box-клиент, подключиться, проверить выход в интернет через сервер.

- [ ] **Step 7: Финальный commit (если были правки)**

```bash
git add -A && git commit -m "chore: e2e verification fixes"
```

---

## Self-Review

- **Spec coverage:** архитектура (Phase 8 compose), компоненты caddy/singbox/fastapi/vue/postgres (все фазы), модель данных (Task 2.2), все API-эндпоинты (Phase 5), генерация config.json/Caddyfile/подписки (Phase 1), bootstrap домена из env (Task 6.1), reload через docker (Task 4.1), заглушка (Task 8.1), тестирование (TDD во всех фазах). Покрыто.
- **Вне MVP** (учёт трафика, expiry, мультиадмины, naive:// URI) — не включено, согласно спеке.
- **Type consistency:** `apply_singbox(db, reloader)`, `apply_caddy(domain, reloader)`, `Reloader.restart(container)`, `singbox_config(users)`, `caddyfile(domain)`, `subscription(domain, username, password)` — имена консистентны между задачами и тестами.
- **Замечание для исполнителя:** в Task 5.3 удалить дублирующий `test_protected_requires_token` из `test_auth.py` (он живёт в `test_clients.py`). В Task 5.4 не забыть monkeypatch `app.services.settings.singbox_config_path` на tmp.
