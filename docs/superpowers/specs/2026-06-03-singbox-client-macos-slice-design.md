# sing-box клиент — первый вертикальный срез (macOS)

**Дата:** 2026-06-03
**Статус:** дизайн утверждён, готов к плану
**Репозиторий:** отдельный новый репозиторий (Flutter), не текущий серверный

## Контекст и общая цель проекта

Отдельное кросс-платформенное клиентское приложение на **Flutter + sing-box** с единой
кодовой базой. Целевые платформы MVP: **macOS, iOS, Windows**. Протоколы MVP:
**naiveproxy, VLESS, REALITY**. Отображение подписок в стиле Happ.

Проект слишком велик для одного спека и декомпозирован на независимые подсистемы:

1. **Платформенная VPN-обвязка** (самое дорогое/рискованное; для каждой ОС своя).
2. **UI-приложение** (список нод, коннект, статистика, дизайн «как Happ»).
3. **Подписки** (парсинг/синк форматов подписок).

Стратегия: сначала **вертикальный срез на одной платформе end-to-end**, доказывающий
самый рискованный путь, затем тиражирование и наращивание UI. Этот документ описывает
**первый срез — macOS через системный прокси**. Остальные платформы и фичи — отдельными
циклами спек→план→реализация.

## Цель среза

Доказать сквозной путь *подписка → список нод → коннект → реальный трафик через sing-box*
на macOS с минимальным UI.

### В границах

- Flutter-приложение под macOS (desktop).
- Ввод одного URL подписки, fetch по HTTP(S).
- Парсинг подписки: base64-список share-ссылок (`vless://`, REALITY как параметры vless,
  `naive+https://`).
- Список нод на экране (имя + тип протокола).
- Тап по ноде → генерация sing-box config с `mixed` inbound + выбранный outbound.
- Запуск bundled-бинарника **sing-box как дочернего процесса**.
- Установка **системного прокси** macOS на `mixed` порт при коннекте; снятие при дисконнекте.
- Индикатор статуса (disconnected / connecting / connected) + сырой лог sing-box.

### Вне границ (отдельные циклы потом)

TUN/полный перехват трафика, iOS, Windows, красивый дизайн «как Happ», пер-аппные правила,
автообновление подписки, переключение нод на лету, статистика трафика.

### Критерий успеха

Вставил URL своей подписки → вижу ноды → тапнул vless/REALITY/naive ноду → системный прокси
поднялся → `curl`/браузер через прокси резолвит внешний IP сервера.

## Архитектура

Слоистая структура: платформенная обвязка изолирована от UI (окупится при переносе на
iOS/Windows).

```
Flutter UI (Dart)
  └── AppController (состояние: подписка, ноды, статус коннекта)
        ├── SubscriptionService   — fetch URL, декод base64, парсинг share-ссылок → List<NodeConfig>
        ├── ConfigBuilder         — NodeConfig → sing-box JSON (mixed inbound + outbound)
        └── TunnelController (абстракция платформы)
              └── MacOSProcessTunnel (реализация через MethodChannel)
                    ↕ MethodChannel "singbox/tunnel"
  Native (Swift, macOS runner)
    ├── SingboxProcess   — запуск/остановка bundled sing-box, чтение stdout/stderr
    └── SystemProxy      — networksetup set/unset web+secure proxy
```

### Единицы (каждая тестируется отдельно)

| Единица | Что делает | Зависит от |
|---|---|---|
| `SubscriptionService` | HTTP-fetch + декод base64 + парсинг ссылок | http-клиент |
| `NodeConfig` | модель одной ноды (тип, host, port, params) | — |
| `ConfigBuilder` | детерминированно строит sing-box JSON | NodeConfig |
| `TunnelController` | интерфейс start(configJson)/stop()/статус-стрим | — |
| `MacOSProcessTunnel` | Dart-сторона MethodChannel | TunnelController |
| `SingboxProcess` (Swift) | жизненный цикл процесса sing-box | bundled бинарник |
| `SystemProxy` (Swift) | вкл/выкл системный прокси | networksetup |

**Почему MethodChannel, а не FFI:** для desktop-процессной модели нужно лишь «запусти
бинарник / останови / дай лог» — естественно ложится на native runner и переиспользует ту
же абстракцию `TunnelController`, которую на iOS заменит Network Extension. FFI/gomobile —
для мобильных, где процесс запустить нельзя.

## Поток данных

1. Юзер вставляет URL → `SubscriptionService.fetch(url)`.
2. Ответ: base64 → декод → строки `vless://...`, `naive+https://...` → `parse()` →
   `List<NodeConfig>`.
3. UI рендерит список. Юзер тапает ноду.
4. `ConfigBuilder.build(node)` → sing-box JSON (`mixed` inbound на `127.0.0.1:<port>`,
   выбранный outbound, дефолтный `route`).
5. `TunnelController.start(json)` → MethodChannel → Swift пишет config во временный файл,
   запускает `sing-box run -c`, стримит лог.
6. По строке готовности (или таймауту health-check через локальный прокси) → Swift
   включает `SystemProxy` → статус `connected`.
7. Дисконнект: снять системный прокси → убить процесс → статус `disconnected`.

## Обработка ошибок

Каждая ошибка → понятный статус в UI, не краш:

- URL недоступен / не 200 → `SubscriptionError.fetch`.
- Тело не декодится / нет валидных ссылок → `SubscriptionError.parse`.
- Неизвестная схема ссылки → ноду пропускаем, остальные показываем.
- Бинарник упал на старте (stderr, ненулевой exit) → `TunnelError.launch` + последние
  строки лога.
- Системный прокси не выставился (`networksetup` fail) → останавливаем процесс, не
  оставляем «полу-коннект».
- **Гарантия очистки:** при выходе из приложения / краше — снять системный прокси (иначе
  юзер останется без интернета). Native-сторона ставит обработчик на терминацию.

## Тестирование (TDD, по слоям)

- `SubscriptionService` — юнит-тесты парсинга на фикстурах ссылок (vless, REALITY-вариант,
  naive). Декод base64.
- `ConfigBuilder` — golden-тесты: NodeConfig → ожидаемый JSON.
- `TunnelController` — мок-реализация для тестов `AppController` (статусы, ошибки).
- Native `SystemProxy` — ручной чек set/unset + автоснятие при kill.
- **Сквозной ручной критерий** из «Критерий успеха» (curl через прокси → IP сервера).

## Открытые вопросы для следующих циклов

- Откуда брать bundled sing-box (версия, сборка, нотаризация для macOS).
- Точный формат подписки сервера (совместимость, см. память про naive-клиентов).
- Переход на TUN и Network Extension (macOS/iOS), gomobile/libbox для мобильных.
