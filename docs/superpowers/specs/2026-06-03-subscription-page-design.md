# Красивая страница подписки — дизайн

Дата: 2026-06-03

## Цель

Заменить «голую» выдачу JSON по ссылке подписки человекочитаемой страницей: при
открытии `/sub/{uuid}` в браузере пользователь видит имя, QR-код, кнопки one-click
импорта в клиенты и инструкцию по установке. Клиентские приложения (sing-box,
Hiddify, Karing) продолжают получать прежний JSON-профиль.

Это первый шаг; собственный десктоп/мобайл-клиент на ядре sing-box — отдельная
последующая задача, в данном спеке не рассматривается.

## Ключевые решения

- **Разделение по User-Agent на одном URL.** `/sub/{uuid}`:
  - UA содержит `Mozilla` (браузер) → HTML-страница подписки.
  - Иначе → текущий JSON (логика `_negotiate` не меняется).
- **Страница — отдельная точка входа Vue/Vite**, не часть `/admin/` SPA. Без
  редиректов.
- **Авто-тема** через `prefers-color-scheme` (Tailwind v4 `dark:`).
- **Без брендинга** на данном этапе — нейтральный современный стиль.
- **Данные инжектятся в HTML** (`window.__SUB__`), второго запроса нет.

## Архитектура

```
GET /sub/{uuid}
   ├─ UA = Mozilla (браузер)
   │     → найти Client(sub_uuid, enabled=True)
   │     → собрать контекст: label, sub_url, deeplinks, platform
   │     → прочитать dist/sub.html, инжектить <script>window.__SUB__=...</script>
   │     → вернуть text/html
   │           → Vue (SubApp) рисует имя / QR / кнопки / инструкцию
   └─ UA ≠ браузер
         → текущий JSON-профиль (без изменений)
```

### Сборка фронта

- `vite.config.js` → multi-page build: `index.html` (админка, base `/admin/`) +
  новый `sub.html` (страница подписки).
- Ассеты ссылаются по **абсолютным** путям (под существующим `/admin/assets/...`),
  чтобы не зависеть от переменного `{uuid}` в пути страницы.
- Vite кладёт `sub.html` с хешированными ассетами в `dist`. Бэкенд читает этот
  файл и вставляет `<script>window.__SUB__=...</script>` перед `</head>`. Сборка
  фронта и данные таким образом развязаны.

## Компоненты

### Бэкенд (`backend/app/routers/subscription.py`)

- В `get_subscription` добавить ветку браузера (UA содержит `Mozilla`).
- Контекст:
  - `label` — имя пользователя.
  - `sub_url` — `https://{domain}/sub/{sub_uuid}`.
  - `platform` — `desktop` / `mobile`, определяется по UA.
  - `deeplinks` — словарь схем (см. ниже).
- Хелпер построения deep-links (с URL-кодированием sub_url).
- Отдать HTML (прочитанный `dist/sub.html` + инжект `window.__SUB__`).

### Deep-link схемы (строятся на бэке)

- sing-box: `sing-box://import-remote-profile?url=<encoded sub_url>`
- Hiddify (desktop): `hiddify://import/<sub_url>`
- Karing: `karing://install-config?url=<encoded sub_url>` — точный формат
  уточнить при реализации.
- copy-link: сам `sub_url`.

### Фронт (`frontend/sub.html`, `frontend/src/sub/main.js`, `frontend/src/sub/SubApp.vue`)

- Читает `window.__SUB__`.
- Рендерит:
  - имя пользователя (`label`);
  - QR-код подписки (через имеющийся пакет `qrcode`);
  - кнопки по платформе:
    - desktop → Hiddify, Karing, sing-box;
    - mobile → Karing, sing-box, «Скопировать ссылку»;
    - «Скопировать ссылку» доступна везде;
  - блок инструкции по установке клиентов и импорту подписки.
- Авто-тема (`prefers-color-scheme`).

## Обработка ошибок

- `uuid` не найден / `enabled=False`:
  - браузер → HTML-404 («Подписка не найдена или отключена»);
  - не-браузер → текущий JSON/404 (без изменений).
- Пустой `domain` в Settings: страница рендерится, но в блоке URL выводится
  предупреждение «домен не настроен в панели».
- Ассеты не собраны: задокументировать, что страница требует `vite build`;
  в dev доступна через `vite dev` как отдельная страница.

## Тесты (`backend/tests/test_subscription.py`)

- UA=Mozilla → `Content-Type: text/html`, тело содержит `label`, `sub_url`,
  deep-links.
- UA=sing-box (и Hiddify) → прежний JSON (регресс существующего поведения).
- 404: браузер → HTML, клиент → прежнее поведение.
- Юнит на хелпер построения deep-links (корректное URL-кодирование).

## Затрагиваемые файлы

- `backend/app/routers/subscription.py` — ветка HTML + контекст + хелпер.
- `frontend/vite.config.js` — multi-page build.
- `frontend/sub.html`, `frontend/src/sub/main.js`, `frontend/src/sub/SubApp.vue` — новые.
- `backend/tests/test_subscription.py` — расширение тестов.

## Вне области (на потом)

- Отображение трафика и срока действия (нет полей в модели `Client`).
- Брендинг/лого/кастомные цвета.
- Собственный десктоп/мобайл-клиент на ядре sing-box.
