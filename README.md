# naive_sing_box

MVP-панель управления [NaïveProxy](https://github.com/klzgrad/naiveproxy) на ядре
[sing-box](https://sing-box.sagernet.org/): добавление/удаление клиентов, выдача им
подписок (ссылка с уникальным id, отдающая sing-box JSON-профиль) и автоматическая
настройка прокси-сервера.

## Архитектура

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
   h2c  ▼        ▼ /api,/sub /admin
  ┌──────────┐ ┌──────────────┐
  │ sing-box │ │   fastapi    │──► docker.sock (reload sing-box/caddy)
  │  naive   │ │              │──► postgres
  │ :1080    │ └──────┬───────┘
  └──────────┘        │
                ┌──────▼──────┐
                │  postgres   │
                └─────────────┘
```

- **caddy** — единственный сервис на 443. Маршрутизация: `CONNECT` → sing-box (h2c);
  `/api/*` и `/sub/*` → FastAPI; `/admin/*` → фронтенд (nginx); всё остальное →
  статичная заглушка-маскировка. Сертификат берётся автоматически через ACME.
- **sing-box** — naive inbound на `:1080` внутри docker-сети, без TLS (TLS терминирует
  caddy). Список `users[]` управляется из FastAPI.
- **fastapi** — REST API (JWT-авторизация админа), CRUD клиентов, настройка домена,
  выдача подписок. Генерирует `config.json` для sing-box и `Caddyfile`, перезапускает
  контейнеры через docker socket.
- **frontend** — Vue 3, отдаётся nginx под `/admin/`.
- **postgres** — хранение админов, клиентов и настроек.

## Требования

- Сервер с публичным IP и Docker + Docker Compose.
- Домен с A-записью, указывающей на IP сервера (нужен для ACME-сертификата).
- Открытые порты **80** и **443** (80 нужен для ACME-челленджа).

## Развёртывание

### 1. Клонировать репозиторий

```bash
git clone https://github.com/ArtemDan1/naive_sing_box.git
cd naive_sing_box
```

### 2. Настроить переменные окружения

```bash
cp .env.example .env
```

Отредактируйте `.env`:

| Переменная          | Описание                                                        |
|---------------------|-----------------------------------------------------------------|
| `DATABASE_URL`      | строка подключения к Postgres (по умолчанию подходит для compose) |
| `JWT_SECRET`        | длинная случайная строка для подписи JWT (**обязательно сменить**) |
| `ADMIN_USERNAME`    | логин администратора панели                                     |
| `ADMIN_PASSWORD`    | пароль администратора (**обязательно сменить**)                 |
| `DOMAIN`            | ваш домен, напр. `vpn.example.com` (нужен для сертификата на старте) |
| `POSTGRES_USER`     | пользователь БД                                                 |
| `POSTGRES_PASSWORD` | пароль БД                                                       |
| `POSTGRES_DB`       | имя БД                                                          |

Сгенерировать секрет можно так:

```bash
openssl rand -hex 32
```

### 3. Поднять стек

```bash
docker compose up -d --build
```

На первом старте FastAPI применяет миграции, создаёт администратора и запись
настроек из `.env`, генерирует `config.json` и `Caddyfile`. Контейнеры sing-box и
caddy перезапускаются и подхватывают сгенерированные конфиги, после чего caddy
получает TLS-сертификат для домена.

Проверить, что сертификат получен:

```bash
docker compose logs caddy | grep -i certificate
```

### 4. Проверить работу

- Заглушка: `curl -I https://<DOMAIN>/` → должен вернуться `200` с HTML-заглушкой.
- Админка: откройте `https://<DOMAIN>/admin/` и войдите под `ADMIN_USERNAME` /
  `ADMIN_PASSWORD`.

## Использование

1. Войдите в админку `https://<DOMAIN>/admin/`.
2. На вкладке **Настройки** убедитесь, что домен задан верно (его можно сменить —
   тогда Caddy перезапустится и возьмёт новый сертификат).
3. На вкладке **Клиенты** добавьте клиента (укажите имя). Будут автоматически
   сгенерированы логин/пароль и уникальный `sub_uuid`.
4. Скопируйте ссылку **подписки** напротив клиента
   (`https://<DOMAIN>/sub/<sub_uuid>`).
5. Импортируйте подписку в клиент с поддержкой sing-box (приложение sing-box,
   NekoBox и т.п.) и подключайтесь.
6. Чекбокс **Вкл** временно отключает клиента (убирает из `users[]` sing-box),
   кнопка **Удалить** удаляет навсегда. Любое изменение перезапускает sing-box
   (кратковременный обрыв активных соединений).

## Подписка

`GET https://<DOMAIN>/sub/<sub_uuid>` возвращает sing-box outbound:

```json
{
  "outbounds": [{
    "type": "naive",
    "tag": "proxy",
    "server": "<DOMAIN>",
    "server_port": 443,
    "username": "<auto>",
    "password": "<auto>",
    "tls": { "enabled": true, "server_name": "<DOMAIN>" }
  }]
}
```

Несуществующий или отключённый `sub_uuid` отдаёт `404` (чтобы не раскрывать сервис).

## Локальная разработка

### Backend

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest                 # запустить тесты
uvicorn app.main:app --reload   # требует доступного Postgres из DATABASE_URL
```

### Frontend

```bash
cd frontend
npm install
npm run dev            # dev-сервер, проксирует /api на localhost:8000
npm run build          # production-сборка в dist/
```

## Эксплуатационные заметки

- При изменении клиентов FastAPI перезаписывает `config.json` и **перезапускает
  контейнер sing-box** через docker socket — активные соединения кратковременно
  рвутся. Для MVP это приемлемо.
- FastAPI монтирует `/var/run/docker.sock` для управления контейнерами sing-box и
  caddy. Это даёт контейнеру FastAPI контроль над docker-хостом — держите панель
  закрытой за авторизацией и не выставляйте порт FastAPI наружу (наружу смотрит
  только caddy).

## Вне области MVP

Учёт/лимитирование трафика по юзерам, срок действия клиентов, несколько админов,
форматы подписок кроме sing-box JSON, горячий reload sing-box без рестарта.

## Документация

- Дизайн: `docs/superpowers/specs/2026-06-01-naive-sing-box-mvp-design.md`
- План реализации: `docs/superpowers/plans/2026-06-01-naive-sing-box-mvp.md`
