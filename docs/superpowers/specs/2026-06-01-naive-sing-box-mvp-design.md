# Naive + sing-box MVP — дизайн

Дата: 2026-06-01

## Цель

MVP панели управления naiveproxy на базе ядра sing-box: настройка сервера,
добавление/удаление клиентов, выдача им подписок (ссылка с уникальным id,
отдающая sing-box JSON-профиль). Стек: FastAPI (управление + подписки),
ядро sing-box, минимальный Vue-фронтенд, Caddy на 443 (TLS + маскировка +
заглушка для не-прокси трафика), PostgreSQL. Всё в Docker Compose на одном
сервере.

Референс архитектуры:
- https://sing-box.sagernet.org/configuration/inbound/naive/
- https://habr.com/ru/articles/1024990/

## Архитектура

Все сервисы в одном `docker-compose.yml` на одном сервере.

```
                  Интернет
                     │ :443 (TLS, ACME)
              ┌──────▼───────┐
              │    caddy     │  терминирует TLS по домену
              └──┬────────┬──┘
   CONNECT-прокси│        │ обычные GET (боты/браузеры)
   + /sub, /api  │        └──► заглушка (статичный сайт)
        ┌────────┼─────────────┐
        │        │             │
   h2c  ▼        ▼ /api,/sub
  ┌──────────┐ ┌──────────────┐
  │ sing-box │ │   fastapi    │──► docker.sock (reload sing-box/caddy)
  │  naive   │ │ (+Vue build) │──► postgres
  │ :1080    │ └──────┬───────┘
  └──────────┘        │
                ┌──────▼──────┐
                │  postgres   │
                └─────────────┘
```

### Компоненты

- **caddy** — единственный сервис на 443. Маршрутизация:
  - `CONNECT` → h2c в sing-box (`singbox:1080`);
  - `/api/*` и `/sub/*` → fastapi (`fastapi:8000`);
  - всё остальное → статичная заглушка (`/srv/fallback/index.html`),
    отдаётся как обычный сайт-имитатор.
  - Caddy сам получает ACME-сертификат для домена. Домен подставляется в
    сгенерированный Caddyfile.
- **sing-box** — naive inbound на `0.0.0.0:1080` внутри docker-сети, без TLS
  (h2c; TLS терминирует caddy). `users[]` — список активных клиентов.
  Outbound `direct`. Порт наружу НЕ публикуется — доступ только через caddy.
- **fastapi** — REST API: auth админа (JWT), CRUD клиентов, настройки
  (домен), отдача подписок `/sub/<uuid>` (sing-box JSON). Генерирует
  `config.json` для sing-box и `Caddyfile`, перезапускает соответствующие
  контейнеры через docker socket. Отдаёт собранный Vue (статику).
- **vue** — собирается в статику. Экран логина + таблица клиентов +
  страница настроек (домен).
- **postgres** — админы, клиенты, настройки.

### Решение по reload

sing-box не умеет горячо перечитывать `users[]`, поэтому при любом изменении
клиентов fastapi перезаписывает `config.json` на общем volume и **рестартит
контейнер sing-box** через docker API (`/var/run/docker.sock` примонтирован в
fastapi). Кратковременный обрыв активных соединений приемлем для MVP.
Caddyfile меняется только при смене домена → reload/restart caddy.

Reload-слой (docker restart) изолирован за интерфейсом, чтобы мокаться в тестах.

## Модель данных

PostgreSQL через SQLAlchemy + Alembic.

```
admins
  id            PK
  username      unique
  password_hash bcrypt
  created_at

clients
  id            PK
  label         текстовая метка (имя клиента)
  username      unique, автоген (для naive auth)
  password      автоген (для naive auth)
  sub_uuid      unique UUID — используется в ссылке /sub/<uuid>
  enabled       bool (true → попадает в users[] sing-box)
  created_at

settings        (singleton-строка)
  id            PK
  domain        домен сервера (для Caddyfile и подписок)
  updated_at
```

Первичный админ создаётся при старте из переменных окружения
(`ADMIN_USERNAME`, `ADMIN_PASSWORD`), если таблица пуста.

## API

Базовый префикс `/api`. Всё кроме login — под JWT (Bearer).

| Метод  | Путь                  | Назначение |
|--------|-----------------------|------------|
| POST   | `/api/auth/login`     | login+password → JWT |
| GET    | `/api/clients`        | список клиентов |
| POST   | `/api/clients`        | создать (label) → автоген username/password/sub_uuid |
| PATCH  | `/api/clients/{id}`   | изменить label / enabled |
| DELETE | `/api/clients/{id}`   | удалить |
| GET    | `/api/settings`       | получить домен |
| PUT    | `/api/settings`       | задать домен → регенерация Caddyfile + reload caddy |

Публичный эндпоинт (без JWT, через caddy):

| Метод | Путь              | Назначение |
|-------|-------------------|------------|
| GET   | `/sub/{sub_uuid}` | sing-box JSON-профиль для клиента |

Любая мутация клиентов (create / patch enabled / delete) → регенерация
`config.json` + рестарт sing-box. `/sub/{uuid}` для несуществующего или
disabled uuid → 404 (чтобы не раскрывать существование сервиса).

## Генерация конфигов

### sing-box config.json (из активных клиентов)

```json
{
  "log": { "level": "warn" },
  "inbounds": [{
    "type": "naive", "tag": "naive-in",
    "listen": "0.0.0.0", "listen_port": 1080, "network": "tcp",
    "users": [ { "username": "<u>", "password": "<p>" } ]
  }],
  "outbounds": [{ "type": "direct" }]
}
```

### Caddyfile (из домена)

```
{domain} {
  @naive method CONNECT
  handle @naive { reverse_proxy h2c://singbox:1080 }
  handle /api/* { reverse_proxy fastapi:8000 }
  handle /sub/* { reverse_proxy fastapi:8000 }
  handle { root * /srv/fallback; file_server }
}
```

Заглушка `/srv/fallback/index.html` — нейтральная статичная страница
(сгенерируем).

### Подписка /sub/{uuid} (sing-box клиентский JSON)

```json
{
  "outbounds": [{
    "type": "naive", "tag": "proxy",
    "server": "<domain>", "server_port": 443,
    "username": "<u>", "password": "<p>",
    "tls": { "enabled": true, "server_name": "<domain>" }
  }]
}
```

## Тестирование (TDD)

- Юнит: генераторы `config.json` и `Caddyfile` (чистые функции вход→строка),
  генерация подписки, автогенерация креды/uuid.
- API: pytest + httpx — auth/JWT, CRUD клиентов, 404 на чужой/disabled sub.
- Reload-слой (docker restart) изолирован за интерфейсом → в тестах мокается.
- Ручная проверка: поднять compose, добавить клиента, скачать подписку,
  подключиться sing-box-клиентом.

## Структура репозитория

```
backend/   FastAPI: app/, tests/, alembic/, Dockerfile
frontend/  Vue: src/, Dockerfile (или build в caddy volume)
caddy/     шаблон Caddyfile, fallback/
docker-compose.yml
.env.example
```

## Вне области MVP (YAGNI)

- Учёт/лимитирование трафика по юзерам (sing-box naive не умеет из коробки).
- Срок действия (expiry) клиентов.
- Несколько админов / роли.
- Горячий reload sing-box без рестарта.
- naive:// URI и другие форматы подписок, кроме sing-box JSON.
