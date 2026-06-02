# Рефакторинг: полный sing-box профиль + удобная раздача подписок

Дата: 2026-06-02
Ветка: feat/naive-singbox-mvp

## Контекст и проблема

MVP-панель отдаёт подписку `/sub/<uuid>` как sing-box-фрагмент с одним только
массивом `outbounds[]`. Такой фрагмент не импортируется как готовый профиль:
клиенту нужен полный конфиг (inbound + outbound + route). Ручная проверка
показала, что рабочим является **полный sing-box-профиль** (log + inbound
`mixed` + outbound `naive` + `route.final`).

Серверная часть (Caddy + `forward_proxy`) уже рабочая и не трогается — sing-box
в data-path сервера нет.

### Что едят клиенты (выяснено)

- **sing-box app** — импорт полного sing-box JSON через
  `sing-box://import-remote-profile?url=...`.
- **Hiddify** — sing-box-подписка через диплинк `hiddify://import/<url>`;
  sing-box умеет naive-outbound → полный профиль заходит штатно.
- **Happ Mobile** — naive **не поддерживается** (нативно: VLESS/VMess/Trojan/
  Shadowsocks/Socks5/Hysteria2/WireGuard). Полноценный naive-сценарий на Happ
  Mobile невозможен.
- **Happ Desktop** — может принять полный sing-box JSON через
  `custom-tunnel-config` (вне области этого рефакторинга).

Вывод: универсальный носитель naive — **полный sing-box JSON-профиль**.

## Цели

1. `/sub/<uuid>` отдаёт полный, готовый к импорту sing-box-профиль.
2. Раздача подписок удобна: диплинки sing-box/Hiddify и QR прямо в админке.
3. sing-box остаётся клиентским ядром (профиль строится под него), что
   оставляет задел под другие типы inbound в будущем.

## Вне области

- Поддержка Happ Mobile / другого протокола кроме naive.
- `tun`-inbound / системный VPN-профиль (выбран вариант, близкий к рабочему —
  `mixed`).
- Изменения Caddyfile-генератора, моделей, БД, серверной архитектуры.
- Happ Desktop `custom-tunnel-config`.

## Дизайн

### 1. Генератор профиля — `backend/app/generators.py`

Сигнатура: `subscription(domain, username, password, name) -> str`.
Возвращает JSON полного профиля (отступ 2):

```json
{
  "log": { "level": "info" },
  "inbounds": [
    { "type": "mixed", "tag": "mixed-in", "listen": "127.0.0.1", "listen_port": 2082 }
  ],
  "outbounds": [
    { "type": "naive", "tag": "proxy", "server": "<domain>", "server_port": 443,
      "username": "<username>", "password": "<password>",
      "tls": { "enabled": true, "server_name": "<domain>" } }
  ],
  "route": { "final": "proxy" }
}
```

`name` в тело профиля не попадает — используется только для заголовков ответа
(см. ниже). Остальное — дословно параметризованный рабочий конфиг.

### 2. Эндпоинт подписки — `backend/app/routers/subscription.py`

- Тело — результат `subscription(domain, c.username, c.password, c.label)`.
- `media_type="application/json"`.
- Дополнительные заголовки для красивого импорта/автообновления:
  - `profile-title: base64:<base64(name)>`
  - `profile-update-interval: 24`
  - `content-disposition: attachment; filename="<safe_name>.json"`
    (имя файла санитизируется: только `[A-Za-z0-9._-]`, иначе `profile`).
- 404 для несуществующего/выключенного `sub_uuid` — как сейчас.

### 3. Раздача в админке — `frontend/src/views/Clients.vue`

Колонку «Подписка» расширяем кнопками на каждого клиента:

- **Копировать ссылку** — `subUrl(c)` в буфер.
- **sing-box** — открыть `sing-box://import-remote-profile?url=<encodeURIComponent(subUrl)>#<name>`.
- **Hiddify** — открыть `hiddify://import/<subUrl>#<name>`.
- **QR** (toggle) — локально рисуется QR выбранного диплинка (по умолчанию
  sing-box) через библиотеку `qrcode`; без обращения к внешним сервисам.

`name` для фрагмента диплинка берётся из `c.label` (URL-энкодится).

Добавляем зависимость `qrcode` в `frontend/package.json`.

## Тестирование

- `backend/tests/test_generators.py` — обновить `test_subscription_*`:
  профиль содержит `log`, `inbounds[0].type == "mixed"`,
  `outbounds[0].type == "naive"` с корректными полями, `route.final == "proxy"`.
- `backend/tests/test_subscription.py` — новый тест: ответ `/sub/<uuid>` содержит
  заголовки `profile-title`, `profile-update-interval`, `content-disposition`;
  тело парсится в полный профиль; выключенный/несуществующий → 404.
- README — обновить секции «Подписка» и «Использование» (новый формат тела,
  диплинки, QR).

## Затрагиваемые файлы

- `backend/app/generators.py` — функция `subscription`.
- `backend/app/routers/subscription.py` — тело + заголовки.
- `backend/tests/test_generators.py`, `backend/tests/test_subscription.py`.
- `frontend/src/views/Clients.vue` — кнопки/диплинки/QR.
- `frontend/package.json` — `qrcode`.
- `README.md` — секции «Подписка», «Использование».
