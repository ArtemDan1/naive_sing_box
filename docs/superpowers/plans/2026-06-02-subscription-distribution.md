# Full sing-box Profile + Subscription Distribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/sub/<uuid>` return a complete, import-ready sing-box profile and add one-tap distribution (sing-box/Hiddify deep links + QR) to the admin panel.

**Architecture:** Backend `generators.subscription()` emits a full sing-box JSON profile (log + `mixed` inbound + `naive` outbound + route) instead of an outbounds-only fragment; the `/sub` endpoint adds import/auto-update headers; the Vue clients view gains copy/deep-link/QR controls. No server/Caddy/DB changes.

**Tech Stack:** Python 3 / FastAPI / SQLAlchemy / pytest (backend), Vue 3 / Vite + `qrcode` lib (frontend).

---

### Task 1: Full sing-box profile generator

**Files:**
- Modify: `backend/app/generators.py:46-58` (the `subscription` function)
- Test: `backend/tests/test_generators.py:40-48`

- [ ] **Step 1: Replace the subscription test with a full-profile test**

In `backend/tests/test_generators.py`, replace `test_subscription_outbound` (lines 40-48) with:

```python
def test_subscription_full_profile():
    prof = json.loads(subscription("vpn.example.com", "alice", "pw1", "Phone"))
    assert prof["log"]["level"] == "info"

    inb = prof["inbounds"][0]
    assert inb["type"] == "mixed"
    assert inb["tag"] == "mixed-in"
    assert inb["listen"] == "127.0.0.1"
    assert inb["listen_port"] == 2082

    out = prof["outbounds"][0]
    assert out["type"] == "naive"
    assert out["tag"] == "proxy"
    assert out["server"] == "vpn.example.com"
    assert out["server_port"] == 443
    assert out["username"] == "alice"
    assert out["password"] == "pw1"
    assert out["tls"] == {"enabled": True, "server_name": "vpn.example.com"}

    assert prof["route"]["final"] == "proxy"


def test_subscription_name_not_in_body():
    prof = json.loads(subscription("vpn.example.com", "alice", "pw1", "Phone"))
    assert "Phone" not in json.dumps(prof)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_generators.py -v`
Expected: FAIL — `test_subscription_full_profile` fails (current body has no `log`/`inbounds`/`route`) and `subscription()` is called with 4 args but only accepts 3 (TypeError).

- [ ] **Step 3: Rewrite `subscription` to emit the full profile**

Replace `backend/app/generators.py` lines 46-58 with:

```python
def subscription(domain: str, username: str, password: str, name: str = "") -> str:
    """Full sing-box client profile (log + mixed inbound + naive outbound + route).

    `name` is intentionally not embedded in the profile body — it is only used
    for the subscription response headers (profile title / filename).
    """
    cfg = {
        "log": {"level": "info"},
        "inbounds": [{
            "type": "mixed",
            "tag": "mixed-in",
            "listen": "127.0.0.1",
            "listen_port": 2082,
        }],
        "outbounds": [{
            "type": "naive",
            "tag": "proxy",
            "server": domain,
            "server_port": 443,
            "username": username,
            "password": password,
            "tls": {"enabled": True, "server_name": domain},
        }],
        "route": {"final": "proxy"},
    }
    return json.dumps(cfg, indent=2)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_generators.py -v`
Expected: PASS (all generator tests, including the two new subscription tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/generators.py backend/tests/test_generators.py
git commit -m "feat: emit full sing-box profile from subscription generator"
```

---

### Task 2: Subscription endpoint headers + name

**Files:**
- Modify: `backend/app/routers/subscription.py` (whole file)
- Test: `backend/tests/test_subscription.py:11-22` (update) and add new tests

- [ ] **Step 1: Update existing test and add a headers test**

In `backend/tests/test_subscription.py`, replace `test_subscription_returns_profile` (lines 11-22) with the following, and add the two functions after it:

```python
def test_subscription_returns_profile(client, db_session):
    _seed_domain(db_session)
    db_session.add(
        Client(label="My Phone", username="alice", password="pw1", sub_uuid="abc", enabled=True)
    )
    db_session.commit()
    r = client.get("/sub/abc")
    assert r.status_code == 200
    prof = json.loads(r.text)
    assert prof["inbounds"][0]["type"] == "mixed"
    out = prof["outbounds"][0]
    assert out["type"] == "naive"
    assert out["server"] == "vpn.example.com"
    assert out["username"] == "alice"
    assert prof["route"]["final"] == "proxy"


def test_subscription_headers(client, db_session):
    import base64
    _seed_domain(db_session)
    db_session.add(
        Client(label="My Phone", username="alice", password="pw1", sub_uuid="abc", enabled=True)
    )
    db_session.commit()
    r = client.get("/sub/abc")
    assert r.headers["profile-title"] == "base64:" + base64.b64encode("My Phone".encode()).decode()
    assert r.headers["profile-update-interval"] == "24"
    assert r.headers["content-disposition"] == 'attachment; filename="My_Phone.json"'


def test_subscription_filename_sanitized(client, db_session):
    _seed_domain(db_session)
    db_session.add(
        Client(label="My/Phone v2!", username="alice", password="pw1", sub_uuid="abc", enabled=True)
    )
    db_session.commit()
    r = client.get("/sub/abc")
    assert r.headers["content-disposition"] == 'attachment; filename="My_Phone_v2.json"'
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_subscription.py -v`
Expected: FAIL — `subscription()` now requires the `name` arg path works, but headers (`profile-title`, etc.) are absent → KeyError on the header assertions.

- [ ] **Step 3: Rewrite the subscription router**

Replace the entire contents of `backend/app/routers/subscription.py` with:

```python
import base64
import re

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Client, Settings
from app.generators import subscription as gen_subscription

router = APIRouter(tags=["subscription"])


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")
    return cleaned or "profile"


@router.get("/sub/{sub_uuid}")
def get_subscription(sub_uuid: str, db: Session = Depends(get_db)):
    c = db.query(Client).filter_by(sub_uuid=sub_uuid, enabled=True).first()
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    s = db.query(Settings).first()
    domain = s.domain if s else ""
    body = gen_subscription(domain, c.username, c.password, c.label)
    title = base64.b64encode(c.label.encode()).decode()
    headers = {
        "profile-title": f"base64:{title}",
        "profile-update-interval": "24",
        "content-disposition": f'attachment; filename="{_safe_filename(c.label)}.json"',
    }
    return Response(content=body, media_type="application/json", headers=headers)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_subscription.py -v`
Expected: PASS (all four subscription tests).

- [ ] **Step 5: Run the full backend suite**

Run: `cd backend && python -m pytest -q`
Expected: PASS (no regressions across all tests).

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/subscription.py backend/tests/test_subscription.py
git commit -m "feat: add profile-title/update-interval/filename headers to subscription"
```

---

### Task 3: Add qrcode dependency to frontend

**Files:**
- Modify: `frontend/package.json:8` (the `dependencies` block)

- [ ] **Step 1: Add the dependency and install**

Run:

```bash
cd frontend && npm install qrcode@^1.5
```

This adds `"qrcode": "^1.5"` to `dependencies` in `frontend/package.json` and updates `package-lock.json`.

- [ ] **Step 2: Verify it resolves**

Run: `cd frontend && node -e "require('qrcode'); console.log('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore: add qrcode dependency for subscription QR codes"
```

---

### Task 4: Distribution controls in the clients view

**Files:**
- Modify: `frontend/src/views/Clients.vue` (whole file)

> Note: this view has no automated tests in the project; verification is a manual build + smoke check (Step 3-4).

- [ ] **Step 1: Rewrite `Clients.vue` with copy/deep-link/QR controls**

Replace the entire contents of `frontend/src/views/Clients.vue` with:

```vue
<template>
  <h2>Клиенты</h2>
  <form @submit.prevent="add">
    <input v-model="label" placeholder="Имя клиента" />
    <button>Добавить</button>
  </form>
  <table border="1" cellpadding="6">
    <tr><th>Имя</th><th>Логин</th><th>Подписка</th><th>Вкл</th><th></th></tr>
    <template v-for="c in clients" :key="c.id">
      <tr>
        <td>{{ c.label }}</td>
        <td>{{ c.username }}</td>
        <td>
          <a :href="subUrl(c)" target="_blank">ссылка</a>
          <button type="button" @click="copy(c)">Копировать</button>
          <a :href="singboxLink(c)">sing-box</a>
          <a :href="hiddifyLink(c)">Hiddify</a>
          <button type="button" @click="toggleQr(c)">QR</button>
        </td>
        <td><input type="checkbox" :checked="c.enabled" @change="toggle(c)" /></td>
        <td><button @click="remove(c)">Удалить</button></td>
      </tr>
      <tr v-if="qrFor === c.id">
        <td colspan="5"><img :src="qrData" alt="QR" /></td>
      </tr>
    </template>
  </table>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import QRCode from 'qrcode'
import { api } from '../api'

const clients = ref([]), label = ref('')
const qrFor = ref(null), qrData = ref('')

async function load() { clients.value = await api.clients() }
async function add() { if (label.value) { await api.createClient(label.value); label.value = ''; await load() } }
async function toggle(c) { await api.updateClient(c.id, { enabled: !c.enabled }); await load() }
async function remove(c) { await api.deleteClient(c.id); await load() }

function subUrl(c) { return `${location.origin}/sub/${c.sub_uuid}` }
function singboxLink(c) {
  return `sing-box://import-remote-profile?url=${encodeURIComponent(subUrl(c))}#${encodeURIComponent(c.label)}`
}
function hiddifyLink(c) {
  return `hiddify://import/${subUrl(c)}#${encodeURIComponent(c.label)}`
}
async function copy(c) { await navigator.clipboard.writeText(subUrl(c)) }
async function toggleQr(c) {
  if (qrFor.value === c.id) { qrFor.value = null; return }
  qrData.value = await QRCode.toDataURL(singboxLink(c))
  qrFor.value = c.id
}
onMounted(load)
</script>
```

- [ ] **Step 2: Lint-build the frontend**

Run: `cd frontend && npm run build`
Expected: build succeeds, `dist/` produced, no Vue compile errors.

- [ ] **Step 3: Smoke-check the dev server (manual)**

Run: `cd frontend && npm run dev` then open the printed URL, go to the Clients view.
Expected: each client row shows «ссылка / Копировать / sing-box / Hiddify / QR»; clicking QR renders an image row; clicking again hides it. (Deep links only resolve on a device with the apps installed — verifying the buttons render and QR draws is sufficient here.)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/Clients.vue
git commit -m "feat: add copy/sing-box/Hiddify deep links and QR to clients view"
```

---

### Task 5: Update README

**Files:**
- Modify: `README.md:127-145` («Подписка» section) and `README.md:118-122` (subscription usage step)

- [ ] **Step 1: Update the «Подписка» section**

Replace `README.md` lines 127-145 (the `## Подписка` section through the `404` note) with:

````markdown
## Подписка

`GET https://<DOMAIN>/sub/<sub_uuid>` возвращает **полный sing-box-профиль**,
готовый к импорту:

```json
{
  "log": { "level": "info" },
  "inbounds": [
    { "type": "mixed", "tag": "mixed-in", "listen": "127.0.0.1", "listen_port": 2082 }
  ],
  "outbounds": [
    { "type": "naive", "tag": "proxy", "server": "<DOMAIN>", "server_port": 443,
      "username": "<auto>", "password": "<auto>",
      "tls": { "enabled": true, "server_name": "<DOMAIN>" } }
  ],
  "route": { "final": "proxy" }
}
```

Ответ содержит заголовки `profile-title` (имя клиента), `profile-update-interval`
(24 ч) и `content-disposition`, чтобы клиент показал имя профиля и сам обновлял
подписку.

Профиль импортируется в **sing-box app**, **Hiddify** и **Happ Desktop**.
В админке у каждого клиента есть кнопки быстрого импорта:

- **sing-box** — `sing-box://import-remote-profile?url=<sub>`
- **Hiddify** — `hiddify://import/<sub>`
- **QR** — QR-код ссылки импорта (для сканирования телефоном).

> Happ Mobile не поддерживает протокол naive — для него этот профиль не подходит.

Несуществующий или отключённый `sub_uuid` отдаёт `404` (чтобы не раскрывать сервис).
````

- [ ] **Step 2: Update the usage step about subscriptions**

In `README.md`, replace lines 118-122 (steps 4-5 of «Использование») with:

```markdown
4. Скопируйте ссылку **подписки** напротив клиента
   (`https://<DOMAIN>/sub/<sub_uuid>`) или используйте кнопки **sing-box** /
   **Hiddify** / **QR** для быстрого импорта.
5. Импортируйте подписку в клиент с поддержкой sing-box (sing-box app, Hiddify,
   Happ Desktop) и подключайтесь.
```

- [ ] **Step 3: Verify the changes read correctly**

Run: `git diff README.md`
Expected: the «Подписка» section shows the full profile + deep links; the usage step mentions the buttons. No stray duplication.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document full sing-box profile and import deep links"
```

---

## Final verification

- [ ] **Backend suite green**

Run: `cd backend && python -m pytest -q`
Expected: all tests pass.

- [ ] **Frontend builds**

Run: `cd frontend && npm run build`
Expected: build succeeds.
