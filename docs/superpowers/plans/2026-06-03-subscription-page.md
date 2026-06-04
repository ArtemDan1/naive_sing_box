# Subscription Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When `/sub/{uuid}` is opened in a browser, serve a styled Vue page (name, QR, one-click import buttons, install instructions); keep returning the existing JSON profile to client apps.

**Architecture:** `subscription.py` splits on User-Agent: browsers (`Mozilla` in UA) get an HTML shell rendered by the backend; everything else keeps the current JSON path. The HTML shell mounts a separate Vue entry (`sub`) whose assets are built by Vite under `/admin/assets/` with **fixed (non-hashed) filenames**, so the cross-container backend can reference them by a stable URL without reading the frontend's `dist/`. Deep-link strings and platform (desktop/mobile) are computed on the backend and injected via `window.__SUB__`.

**Tech Stack:** FastAPI (Python, no new deps — HTML built with an f-string + `json.dumps`), Vue 3 + Vite multi-page build + Tailwind v4, `qrcode` (already a dependency).

---

## File Structure

- `backend/app/subpage.py` — **new**. Pure helpers: `is_browser(ua)`, `detect_platform(ua)`, `build_deeplinks(sub_url)`, `render_sub_page(ctx)`, `render_sub_404()`. Isolated and unit-testable, keeps the router thin.
- `backend/app/routers/subscription.py` — **modify**. Add the browser branch to `get_subscription`.
- `backend/tests/test_subpage.py` — **new**. Unit tests for the pure helpers.
- `backend/tests/test_subscription.py` — **modify**. Add browser-vs-client integration tests.
- `frontend/vite.config.js` — **modify**. Multi-page input + fixed asset filenames.
- `frontend/sub.html` — **new**. Second Vite entry HTML.
- `frontend/src/sub/main.js` — **new**. Mounts the page, imports its CSS.
- `frontend/src/sub/sub.css` — **new**. `@import "tailwindcss";` for the sub entry.
- `frontend/src/sub/SubApp.vue` — **new**. The page UI.

---

## Task 1: Backend pure helpers (platform, deep-links)

**Files:**
- Create: `backend/app/subpage.py`
- Test: `backend/tests/test_subpage.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_subpage.py
from app.subpage import is_browser, detect_platform, build_deeplinks


def test_is_browser_true_for_mozilla():
    assert is_browser("Mozilla/5.0 (Macintosh) Safari/605") is True


def test_is_browser_false_for_clients():
    assert is_browser("sing-box/1.8.0") is False
    assert is_browser("HiddifyNext/2.0.0") is False
    assert is_browser("") is False


def test_detect_platform():
    assert detect_platform("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)") == "mobile"
    assert detect_platform("Mozilla/5.0 (Linux; Android 14)") == "mobile"
    assert detect_platform("Mozilla/5.0 (Macintosh; Intel Mac OS X)") == "desktop"
    assert detect_platform("Mozilla/5.0 (Windows NT 10.0; Win64)") == "desktop"


def test_build_deeplinks_encodes_url():
    sub = "https://vpn.example.com/sub/abc"
    dl = build_deeplinks(sub)
    assert dl["singbox"] == (
        "sing-box://import-remote-profile?url="
        "https%3A%2F%2Fvpn.example.com%2Fsub%2Fabc"
    )
    assert dl["karing"] == (
        "karing://install-config?url="
        "https%3A%2F%2Fvpn.example.com%2Fsub%2Fabc"
    )
    assert dl["hiddify"] == (
        "hiddify://import/https%3A%2F%2Fvpn.example.com%2Fsub%2Fabc"
    )
    assert dl["copy"] == sub
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_subpage.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.subpage'`

- [ ] **Step 3: Write the helpers**

```python
# backend/app/subpage.py
from urllib.parse import quote


def is_browser(ua: str) -> bool:
    return "mozilla" in ua.lower()


def detect_platform(ua: str) -> str:
    u = ua.lower()
    if "android" in u or "iphone" in u or "ipad" in u or "ios" in u:
        return "mobile"
    return "desktop"


def build_deeplinks(sub_url: str) -> dict[str, str]:
    enc = quote(sub_url, safe="")
    return {
        "singbox": f"sing-box://import-remote-profile?url={enc}",
        "hiddify": f"hiddify://import/{enc}",
        "karing": f"karing://install-config?url={enc}",
        "copy": sub_url,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_subpage.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/subpage.py backend/tests/test_subpage.py
git commit -m "feat: subscription page helpers (platform, deep-links)"
```

---

## Task 2: Backend HTML renderers (page + 404)

**Files:**
- Modify: `backend/app/subpage.py`
- Test: `backend/tests/test_subpage.py`

- [ ] **Step 1: Write the failing tests** (append to `backend/tests/test_subpage.py`)

```python
def test_render_sub_page_contains_context_and_assets():
    from app.subpage import render_sub_page
    html = render_sub_page(
        label="My Phone",
        sub_url="https://vpn.example.com/sub/abc",
        platform="desktop",
    )
    assert "<!doctype html>" in html.lower()
    assert '/admin/assets/sub.js' in html
    assert '/admin/assets/sub.css' in html
    assert 'window.__SUB__' in html
    # label/sub_url travel as JSON, so they appear in the inlined payload
    assert "My Phone" in html
    assert "https://vpn.example.com/sub/abc" in html
    assert '"platform": "desktop"' in html
    assert '"karing"' in html  # deep-links embedded


def test_render_sub_page_escapes_label_for_script():
    from app.subpage import render_sub_page
    html = render_sub_page(
        label="</script><b>x", sub_url="https://h/sub/a", platform="mobile"
    )
    # raw closing script tag must not appear unescaped inside the payload
    assert "</script><b>x" not in html


def test_render_sub_404_is_html():
    from app.subpage import render_sub_404
    html = render_sub_404()
    assert "<!doctype html>" in html.lower()
    assert "не найдена" in html.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_subpage.py -v`
Expected: FAIL with `ImportError: cannot import name 'render_sub_page'`

- [ ] **Step 3: Implement the renderers** (append to `backend/app/subpage.py`)

```python
import json

_ASSET_JS = "/admin/assets/sub.js"
_ASSET_CSS = "/admin/assets/sub.css"


def render_sub_page(label: str, sub_url: str, platform: str) -> str:
    payload = {
        "label": label,
        "sub_url": sub_url,
        "platform": platform,
        "deeplinks": build_deeplinks(sub_url),
    }
    # json.dumps escapes quotes; additionally neutralize "</" so a label can
    # never break out of the inline <script> element.
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Подписка</title>
<link rel="stylesheet" href="{_ASSET_CSS}">
<script>window.__SUB__ = {data};</script>
</head>
<body>
<div id="sub"></div>
<script type="module" src="{_ASSET_JS}"></script>
</body>
</html>"""


def render_sub_404() -> str:
    return """<!doctype html>
<html lang="ru">
<head><meta charset="utf-8"><title>Не найдено</title>
<link rel="stylesheet" href="/admin/assets/sub.css"></head>
<body style="font-family:system-ui;padding:3rem;text-align:center">
<h1>Подписка не найдена</h1>
<p>Ссылка недействительна или подписка отключена.</p>
</body>
</html>"""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_subpage.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/subpage.py backend/tests/test_subpage.py
git commit -m "feat: subscription page HTML renderers"
```

---

## Task 3: Wire the browser branch into the router

**Files:**
- Modify: `backend/app/routers/subscription.py`
- Test: `backend/tests/test_subscription.py`

- [ ] **Step 1: Write the failing tests** (append to `backend/tests/test_subscription.py`)

```python
_BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605.1.15"


def test_subscription_browser_gets_html_page(client, db_session):
    _seed_domain(db_session)
    db_session.add(
        Client(label="My Phone", username="alice", password="pw1", sub_uuid="abc", enabled=True)
    )
    db_session.commit()
    r = client.get("/sub/abc", headers={"user-agent": _BROWSER_UA})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "window.__SUB__" in r.text
    assert "My Phone" in r.text
    assert "vpn.example.com/sub/abc" in r.text
    assert '"platform": "desktop"' in r.text


def test_subscription_client_still_gets_json(client, db_session):
    # Regression: non-browser UA must keep returning the JSON profile.
    _seed_domain(db_session)
    db_session.add(
        Client(label="My Phone", username="alice", password="pw1", sub_uuid="abc", enabled=True)
    )
    db_session.commit()
    r = client.get("/sub/abc", headers={"user-agent": "sing-box/1.8.0"})
    assert r.headers["content-type"].startswith("application/json")
    json.loads(r.text)  # parses


def test_subscription_browser_404_is_html(client, db_session):
    _seed_domain(db_session)
    r = client.get("/sub/nope", headers={"user-agent": _BROWSER_UA})
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("text/html")
    assert "не найдена" in r.text.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_subscription.py -v`
Expected: FAIL — browser request currently returns `application/json`, not `text/html`.

- [ ] **Step 3: Add the browser branch**

Edit `backend/app/routers/subscription.py`. Add imports near the top (after the existing `from app.generators ...` lines):

```python
from app.subpage import is_browser, detect_platform, render_sub_page, render_sub_404
```

Replace the body of `get_subscription` (currently lines 32-49) with:

```python
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

    body, media_type = _negotiate(ua, domain, c.username, c.password)

    title = base64.b64encode(c.label.encode()).decode()
    headers = {
        "profile-title": f"base64:{title}",
        "profile-update-interval": "24",
        "content-disposition": f'attachment; filename="{_safe_filename(c.label)}.json"',
    }
    return Response(content=body, media_type=media_type, headers=headers)
```

- [ ] **Step 4: Run the full backend suite**

Run: `cd backend && python -m pytest tests/test_subscription.py tests/test_subpage.py -v`
Expected: PASS (all subscription + subpage tests). Existing tests (default UA `testclient`, not a browser) still get JSON.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/subscription.py backend/tests/test_subscription.py
git commit -m "feat: serve HTML subscription page to browsers"
```

---

## Task 4: Vite multi-page build with fixed asset names

**Files:**
- Modify: `frontend/vite.config.js`
- Create: `frontend/sub.html`, `frontend/src/sub/main.js`, `frontend/src/sub/sub.css`, `frontend/src/sub/SubApp.vue`

- [ ] **Step 1: Create the sub entry CSS**

```css
/* frontend/src/sub/sub.css */
@import "tailwindcss";

@layer base {
  body {
    @apply bg-neutral-50 text-neutral-900 antialiased;
    @apply dark:bg-neutral-950 dark:text-neutral-100;
  }
}
```

- [ ] **Step 2: Create the page component**

```vue
<!-- frontend/src/sub/SubApp.vue -->
<script setup>
import { ref, onMounted, computed } from 'vue'
import QRCode from 'qrcode'

const sub = window.__SUB__ || { label: '', sub_url: '', platform: 'desktop', deeplinks: {} }
const qr = ref('')
const copied = ref(false)

const buttons = computed(() => {
  const d = sub.deeplinks
  if (sub.platform === 'mobile') {
    return [
      { label: 'Karing', href: d.karing },
      { label: 'sing-box', href: d.singbox },
    ]
  }
  return [
    { label: 'Hiddify', href: d.hiddify },
    { label: 'Karing', href: d.karing },
    { label: 'sing-box', href: d.singbox },
  ]
})

async function copyLink() {
  await navigator.clipboard.writeText(sub.sub_url)
  copied.value = true
  setTimeout(() => (copied.value = false), 1500)
}

onMounted(async () => {
  if (sub.sub_url) qr.value = await QRCode.toDataURL(sub.sub_url, { width: 240, margin: 1 })
})
</script>

<template>
  <main class="mx-auto max-w-md px-4 py-10">
    <div class="card text-center">
      <h1 class="text-xl font-semibold">{{ sub.label }}</h1>
      <p class="mt-1 text-sm text-neutral-500">Подписка для подключения</p>

      <img v-if="qr" :src="qr" alt="QR" class="mx-auto mt-6 rounded-lg bg-white p-2" />

      <div class="mt-6 flex flex-col gap-2">
        <a v-for="b in buttons" :key="b.label" class="btn" :href="b.href">
          Импорт в {{ b.label }}
        </a>
        <button class="btn-ghost mt-1" @click="copyLink">
          {{ copied ? 'Скопировано!' : 'Скопировать ссылку' }}
        </button>
      </div>
    </div>

    <div class="card mt-6 text-sm leading-relaxed">
      <h2 class="mb-2 font-semibold">Как подключиться</h2>
      <ol class="list-decimal space-y-1 pl-5">
        <li>Установи клиент: <span v-if="sub.platform === 'mobile'">Karing или sing-box</span><span v-else>Hiddify, Karing или sing-box</span>.</li>
        <li>Нажми кнопку «Импорт» выше — профиль добавится автоматически.</li>
        <li>Если импорт не сработал — скопируй ссылку и добавь подписку вручную.</li>
        <li>Включи подключение в клиенте.</li>
      </ol>
    </div>
  </main>
</template>
```

- [ ] **Step 3: Create the entry script**

```js
// frontend/src/sub/main.js
import { createApp } from 'vue'
import SubApp from './SubApp.vue'
import './sub.css'

createApp(SubApp).mount('#sub')
```

- [ ] **Step 4: Create the entry HTML**

```html
<!-- frontend/sub.html -->
<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Подписка</title></head>
<body><div id="sub"></div><script type="module" src="/src/sub/main.js"></script></body></html>
```

- [ ] **Step 5: Update Vite config for multi-page + fixed names**

Replace `frontend/vite.config.js` with:

```js
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  base: '/admin/',
  plugins: [vue(), tailwindcss()],
  server: { proxy: { '/api': 'http://localhost:8000' } },
  build: {
    rollupOptions: {
      input: { main: 'index.html', sub: 'sub.html' },
      output: {
        entryFileNames: 'assets/[name].js',
        chunkFileNames: 'assets/[name].js',
        assetFileNames: 'assets/[name][extname]',
      },
    },
  },
})
```

- [ ] **Step 6: Build and confirm the emitted asset names**

Run: `cd frontend && npm run build && ls dist/assets`
Expected: the listing contains `sub.js` and `sub.css` (the names the backend references in `app/subpage.py`). It also contains `main.js` and the admin's CSS/chunks.

> If the CSS asset is emitted under a different name than `sub.css` (e.g. `style.css`), update `_ASSET_CSS` in `backend/app/subpage.py` and the `render_sub_404` link to match the actual filename, re-run `python -m pytest tests/test_subpage.py`, then rebuild.

- [ ] **Step 7: Commit**

```bash
git add frontend/vite.config.js frontend/sub.html frontend/src/sub
git commit -m "feat: Vue subscription page entry (QR, import buttons, instructions)"
```

---

## Task 5: Manual end-to-end verification

**Files:** none (verification only)

- [ ] **Step 1: Confirm asset wiring matches**

Run: `cd frontend && ls dist/assets | grep -E '^sub\.(js|css)$'`
Expected: both `sub.js` and `sub.css` listed. These must equal the constants in `backend/app/subpage.py` (`/admin/assets/sub.js`, `/admin/assets/sub.css`).

- [ ] **Step 2: Run the whole backend test suite (no regressions)**

Run: `cd backend && python -m pytest -q`
Expected: all tests pass.

- [ ] **Step 3: Smoke-test the page locally (optional, requires running stack)**

With the docker compose stack up and at least one client created, open `https://<domain>/sub/<uuid>` in a browser. Expected: name, QR, platform-appropriate import buttons, instructions; opening the same URL in a non-browser client (e.g. `curl`) still returns JSON:
`curl -A sing-box https://<domain>/sub/<uuid>` → JSON profile.

- [ ] **Step 4: Final commit (if any doc/constant tweaks were needed)**

```bash
git add -A
git commit -m "chore: subscription page verification tweaks"
```

---

## Self-Review Notes

- **Spec coverage:** UA split (Task 3), Vue separate entry with absolute `/admin/assets` paths (Task 4), QR/name/buttons/instructions (Task 4), platform-specific buttons (Task 4 `buttons` computed), copy-link everywhere (Task 4), auto theme (Tailwind `dark:` in `sub.css`), browser HTML 404 + empty-domain handled (Task 2/3; empty domain yields `https:///sub/...` — acceptable, panel should set domain), tests incl. regression (Tasks 1-3). Deep-link Karing/Hiddify formats are best-effort and flagged in the spec.
- **Cross-container note:** backend never reads the frontend `dist/`; it references fixed asset URLs served by nginx via Caddy's `/admin/*` route. This refines the spec's "read dist/sub.html" mechanic, which is not viable across separate containers.
- **Placeholders:** none — every code/test step is complete.
- **Type consistency:** `window.__SUB__` shape (`label`, `sub_url`, `platform`, `deeplinks{singbox,hiddify,karing,copy}`) is identical between `render_sub_page` (Task 2) and `SubApp.vue` (Task 4).
