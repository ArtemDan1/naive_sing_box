# sing-box клиент — macOS вертикальный срез: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Flutter-приложение под macOS, которое тянет URL подписки, показывает список нод и через дочерний процесс sing-box + системный прокси пускает реальный трафик.

**Architecture:** Слоистая структура — UI/AppController на Dart, чистые тестируемые единицы (`SubscriptionService`, `ConfigBuilder`, `NodeConfig`), абстракция `TunnelController` с macOS-реализацией через MethodChannel к Swift-runner, который запускает bundled sing-box и управляет системным прокси через `networksetup`.

**Tech Stack:** Flutter (desktop/macOS), Dart, MethodChannel, Swift (macOS runner), bundled бинарник sing-box, `flutter_test`.

---

## Структура файлов

Новый репозиторий: `/Users/anton/Documents/tests/singbox_flutter`, Flutter-пакет `singbox_client`.

| Путь | Ответственность |
|---|---|
| `lib/models/node_config.dart` | Иммутабельная модель одной ноды |
| `lib/services/subscription_service.dart` | fetch URL, base64-декод, парсинг share-ссылок |
| `lib/services/share_link_parser.dart` | парсинг одной ссылки (vless/reality/naive) → NodeConfig |
| `lib/services/config_builder.dart` | NodeConfig → sing-box JSON (Map) |
| `lib/tunnel/tunnel_controller.dart` | абстрактный интерфейс + статус-модель |
| `lib/tunnel/macos_process_tunnel.dart` | реализация через MethodChannel |
| `lib/app/app_controller.dart` | состояние приложения (подписка, ноды, статус) |
| `lib/ui/home_screen.dart` | экран: поле URL, список нод, статус, лог |
| `lib/main.dart` | точка входа, сборка зависимостей |
| `macos/Runner/SingboxProcess.swift` | жизненный цикл процесса sing-box |
| `macos/Runner/SystemProxy.swift` | вкл/выкл системного прокси через networksetup |
| `macos/Runner/TunnelChannel.swift` | MethodChannel handler, связывает Process+Proxy |
| `macos/Runner/Resources/sing-box` | bundled бинарник |
| `test/...` | зеркало юнит-тестов |

---

## Task 1: Скаффолд Flutter-проекта

**Files:**
- Create: весь проект `/Users/anton/Documents/tests/singbox_flutter`

- [ ] **Step 1: Создать проект с поддержкой macOS**

```bash
cd /Users/anton/Documents/tests
flutter create --platforms=macos,ios,windows --org com.singboxclient singbox_flutter
cd singbox_flutter
flutter config --enable-macos-desktop
```

- [ ] **Step 2: Проверить, что приложение собирается и запускается**

Run: `flutter run -d macos`
Expected: открывается дефолтное окно Flutter-counter. Закрыть окно.

- [ ] **Step 3: Удалить дефолтный счётчик из main.dart**

Заменить `lib/main.dart` на минимум:

```dart
import 'package:flutter/material.dart';

void main() => runApp(const App());

class App extends StatelessWidget {
  const App({super.key});
  @override
  Widget build(BuildContext context) =>
      const MaterialApp(home: Scaffold(body: Center(child: Text('singbox'))));
}
```

- [ ] **Step 4: Инициализировать git и закоммитить**

```bash
cd /Users/anton/Documents/tests/singbox_flutter
git init -q && git add -A
git commit -q -m "chore: scaffold Flutter macOS/iOS/Windows project"
```

---

## Task 2: Модель NodeConfig

**Files:**
- Create: `lib/models/node_config.dart`
- Test: `test/models/node_config_test.dart`

- [ ] **Step 1: Написать падающий тест**

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:singbox_client/models/node_config.dart';

void main() {
  test('NodeConfig равенство по значению', () {
    const a = NodeConfig(
      name: 'n', protocol: NodeProtocol.vless, host: 'h', port: 443,
      params: {'uuid': 'u'},
    );
    const b = NodeConfig(
      name: 'n', protocol: NodeProtocol.vless, host: 'h', port: 443,
      params: {'uuid': 'u'},
    );
    expect(a, equals(b));
  });
}
```

- [ ] **Step 2: Запустить тест — должен упасть**

Run: `flutter test test/models/node_config_test.dart`
Expected: FAIL — `node_config.dart` не найден.

- [ ] **Step 3: Реализовать модель**

```dart
import 'package:flutter/foundation.dart';

enum NodeProtocol { vless, naive }

@immutable
class NodeConfig {
  final String name;
  final NodeProtocol protocol;
  final String host;
  final int port;
  final Map<String, String> params;

  const NodeConfig({
    required this.name,
    required this.protocol,
    required this.host,
    required this.port,
    required this.params,
  });

  @override
  bool operator ==(Object other) =>
      other is NodeConfig &&
      other.name == name &&
      other.protocol == protocol &&
      other.host == host &&
      other.port == port &&
      mapEquals(other.params, params);

  @override
  int get hashCode => Object.hash(name, protocol, host, port,
      Object.hashAllUnordered(params.entries.map((e) => '${e.key}:${e.value}')));
}
```

- [ ] **Step 4: Запустить тест — должен пройти**

Run: `flutter test test/models/node_config_test.dart`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/models/node_config.dart test/models/node_config_test.dart
git commit -q -m "feat: NodeConfig value model"
```

---

## Task 3: Парсер share-ссылок

REALITY — это vless с `security=reality`, поэтому отдельного enum-значения не нужно: признак reality живёт в `params['security']`.

**Files:**
- Create: `lib/services/share_link_parser.dart`
- Test: `test/services/share_link_parser_test.dart`

- [ ] **Step 1: Написать падающие тесты**

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:singbox_client/models/node_config.dart';
import 'package:singbox_client/services/share_link_parser.dart';

void main() {
  test('парсит vless+reality', () {
    const link =
        'vless://11111111-1111-1111-1111-111111111111@example.com:443'
        '?security=reality&pbk=KEY&fp=chrome&sni=www.apple.com&sid=ab&flow=xtls-rprx-vision'
        '#Server%20A';
    final node = parseShareLink(link)!;
    expect(node.protocol, NodeProtocol.vless);
    expect(node.host, 'example.com');
    expect(node.port, 443);
    expect(node.name, 'Server A');
    expect(node.params['uuid'], '11111111-1111-1111-1111-111111111111');
    expect(node.params['security'], 'reality');
    expect(node.params['pbk'], 'KEY');
    expect(node.params['sni'], 'www.apple.com');
    expect(node.params['flow'], 'xtls-rprx-vision');
  });

  test('парсит naive+https', () {
    const link = 'naive+https://user:pass@example.com:443#Naive%20B';
    final node = parseShareLink(link)!;
    expect(node.protocol, NodeProtocol.naive);
    expect(node.host, 'example.com');
    expect(node.port, 443);
    expect(node.name, 'Naive B');
    expect(node.params['username'], 'user');
    expect(node.params['password'], 'pass');
  });

  test('неизвестная схема → null', () {
    expect(parseShareLink('ss://whatever'), isNull);
  });
}
```

- [ ] **Step 2: Запустить — упадёт**

Run: `flutter test test/services/share_link_parser_test.dart`
Expected: FAIL — `share_link_parser.dart` не найден.

- [ ] **Step 3: Реализовать парсер**

```dart
import '../models/node_config.dart';

/// Парсит одну share-ссылку. Возвращает null для неизвестной схемы.
NodeConfig? parseShareLink(String raw) {
  final link = raw.trim();
  if (link.startsWith('vless://')) return _parseVless(link);
  if (link.startsWith('naive+https://')) return _parseNaive(link);
  return null;
}

String _name(Uri uri, String fallback) =>
    uri.fragment.isEmpty ? fallback : Uri.decodeComponent(uri.fragment);

NodeConfig _parseVless(String link) {
  final uri = Uri.parse(link);
  final params = <String, String>{
    'uuid': uri.userInfo,
    ...uri.queryParameters,
  };
  return NodeConfig(
    name: _name(uri, uri.host),
    protocol: NodeProtocol.vless,
    host: uri.host,
    port: uri.port,
    params: params,
  );
}

NodeConfig _parseNaive(String link) {
  // naive+https://user:pass@host:port#name
  final uri = Uri.parse(link.replaceFirst('naive+https://', 'https://'));
  final creds = uri.userInfo.split(':');
  return NodeConfig(
    name: _name(uri, uri.host),
    protocol: NodeProtocol.naive,
    host: uri.host,
    port: uri.port == 0 ? 443 : uri.port,
    params: {
      'username': creds.isNotEmpty ? Uri.decodeComponent(creds[0]) : '',
      'password': creds.length > 1 ? Uri.decodeComponent(creds[1]) : '',
    },
  );
}
```

- [ ] **Step 4: Запустить — пройдёт**

Run: `flutter test test/services/share_link_parser_test.dart`
Expected: PASS (3 теста).

- [ ] **Step 5: Commit**

```bash
git add lib/services/share_link_parser.dart test/services/share_link_parser_test.dart
git commit -q -m "feat: share link parser (vless/reality/naive)"
```

---

## Task 4: SubscriptionService

**Files:**
- Create: `lib/services/subscription_service.dart`
- Test: `test/services/subscription_service_test.dart`
- Modify: `pubspec.yaml` (зависимость `http`)

- [ ] **Step 1: Добавить http в pubspec**

```bash
cd /Users/anton/Documents/tests/singbox_flutter
flutter pub add http
```

- [ ] **Step 2: Написать падающие тесты**

Инъектируем функцию-загрузчик, чтобы не ходить в сеть.

```dart
import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:singbox_client/models/node_config.dart';
import 'package:singbox_client/services/subscription_service.dart';

void main() {
  test('декодит base64-подписку и парсит ноды', () async {
    const links =
        'vless://11111111-1111-1111-1111-111111111111@h:443?security=reality#A\n'
        'naive+https://u:p@h2:443#B';
    final body = base64.encode(utf8.encode(links));
    final svc = SubscriptionService(fetcher: (url) async => body);

    final nodes = await svc.load('https://example.com/sub');

    expect(nodes, hasLength(2));
    expect(nodes[0].protocol, NodeProtocol.vless);
    expect(nodes[1].protocol, NodeProtocol.naive);
  });

  test('пропускает нераспознанные строки', () async {
    const links = 'ss://bad\nvless://u@h:443#A';
    final body = base64.encode(utf8.encode(links));
    final svc = SubscriptionService(fetcher: (url) async => body);
    final nodes = await svc.load('https://x');
    expect(nodes, hasLength(1));
  });

  test('пустой результат → SubscriptionException', () async {
    final body = base64.encode(utf8.encode('ss://only-bad'));
    final svc = SubscriptionService(fetcher: (url) async => body);
    expect(() => svc.load('https://x'),
        throwsA(isA<SubscriptionException>()));
  });
}
```

- [ ] **Step 3: Запустить — упадёт**

Run: `flutter test test/services/subscription_service_test.dart`
Expected: FAIL — `subscription_service.dart` не найден.

- [ ] **Step 4: Реализовать сервис**

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/node_config.dart';
import 'share_link_parser.dart';

typedef Fetcher = Future<String> Function(String url);

class SubscriptionException implements Exception {
  final String message;
  SubscriptionException(this.message);
  @override
  String toString() => 'SubscriptionException: $message';
}

class SubscriptionService {
  final Fetcher _fetcher;

  SubscriptionService({Fetcher? fetcher}) : _fetcher = fetcher ?? _httpFetch;

  static Future<String> _httpFetch(String url) async {
    final resp = await http.get(Uri.parse(url));
    if (resp.statusCode != 200) {
      throw SubscriptionException('HTTP ${resp.statusCode}');
    }
    return resp.body;
  }

  Future<List<NodeConfig>> load(String url) async {
    final raw = await _fetcher(url);
    final decoded = _maybeBase64(raw.trim());
    final nodes = const LineSplitter()
        .convert(decoded)
        .where((l) => l.trim().isNotEmpty)
        .map(parseShareLink)
        .whereType<NodeConfig>()
        .toList();
    if (nodes.isEmpty) {
      throw SubscriptionException('подписка не содержит валидных нод');
    }
    return nodes;
  }

  String _maybeBase64(String body) {
    if (body.contains('://')) return body; // уже plain-текст ссылок
    try {
      return utf8.decode(base64.decode(base64.normalize(body)));
    } catch (_) {
      return body;
    }
  }
}
```

- [ ] **Step 5: Запустить — пройдёт**

Run: `flutter test test/services/subscription_service_test.dart`
Expected: PASS (3 теста).

- [ ] **Step 6: Commit**

```bash
git add pubspec.yaml pubspec.lock lib/services/subscription_service.dart test/services/subscription_service_test.dart
git commit -q -m "feat: subscription service (fetch + decode + parse)"
```

---

## Task 5: ConfigBuilder

Строит sing-box-конфиг как Dart `Map` (golden-тесты сравнивают структуру). `mixed` inbound на фиксированном `127.0.0.1:<port>`.

**Files:**
- Create: `lib/services/config_builder.dart`
- Test: `test/services/config_builder_test.dart`

- [ ] **Step 1: Написать падающие тесты**

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:singbox_client/models/node_config.dart';
import 'package:singbox_client/services/config_builder.dart';

void main() {
  const builder = ConfigBuilder(localPort: 2080);

  test('vless+reality → корректный outbound', () {
    const node = NodeConfig(
      name: 'A', protocol: NodeProtocol.vless, host: 'example.com', port: 443,
      params: {
        'uuid': 'uid', 'security': 'reality', 'pbk': 'KEY',
        'sni': 'www.apple.com', 'sid': 'ab', 'fp': 'chrome',
        'flow': 'xtls-rprx-vision',
      },
    );
    final cfg = builder.build(node);

    final inbound = cfg['inbounds'][0];
    expect(inbound['type'], 'mixed');
    expect(inbound['listen'], '127.0.0.1');
    expect(inbound['listen_port'], 2080);

    final out = cfg['outbounds'][0];
    expect(out['type'], 'vless');
    expect(out['server'], 'example.com');
    expect(out['server_port'], 443);
    expect(out['uuid'], 'uid');
    expect(out['flow'], 'xtls-rprx-vision');
    expect(out['tls']['enabled'], true);
    expect(out['tls']['server_name'], 'www.apple.com');
    expect(out['tls']['utls']['fingerprint'], 'chrome');
    expect(out['tls']['reality']['enabled'], true);
    expect(out['tls']['reality']['public_key'], 'KEY');
    expect(out['tls']['reality']['short_id'], 'ab');
  });

  test('naive → http outbound с TLS', () {
    const node = NodeConfig(
      name: 'B', protocol: NodeProtocol.naive, host: 'h', port: 443,
      params: {'username': 'u', 'password': 'p'},
    );
    final out = builder.build(node)['outbounds'][0];
    expect(out['type'], 'http');
    expect(out['server'], 'h');
    expect(out['username'], 'u');
    expect(out['password'], 'p');
    expect(out['tls']['enabled'], true);
  });
}
```

- [ ] **Step 2: Запустить — упадёт**

Run: `flutter test test/services/config_builder_test.dart`
Expected: FAIL — `config_builder.dart` не найден.

- [ ] **Step 3: Реализовать builder**

> Замечание: naive маппится на `http`-outbound с TLS как ближайшее нативно поддерживаемое sing-box приближение. Полная padding-совместимость naiveproxy — отдельный follow-up.

```dart
import '../models/node_config.dart';

class ConfigBuilder {
  final int localPort;
  const ConfigBuilder({this.localPort = 2080});

  Map<String, dynamic> build(NodeConfig node) => {
        'log': {'level': 'info'},
        'inbounds': [
          {
            'type': 'mixed',
            'tag': 'mixed-in',
            'listen': '127.0.0.1',
            'listen_port': localPort,
          }
        ],
        'outbounds': [_outbound(node)],
      };

  Map<String, dynamic> _outbound(NodeConfig n) {
    switch (n.protocol) {
      case NodeProtocol.vless:
        return _vless(n);
      case NodeProtocol.naive:
        return _naive(n);
    }
  }

  Map<String, dynamic> _vless(NodeConfig n) {
    final tls = <String, dynamic>{
      'enabled': true,
      'server_name': n.params['sni'] ?? n.host,
    };
    if (n.params['fp'] != null) {
      tls['utls'] = {'enabled': true, 'fingerprint': n.params['fp']};
    }
    if (n.params['security'] == 'reality') {
      tls['reality'] = {
        'enabled': true,
        'public_key': n.params['pbk'] ?? '',
        'short_id': n.params['sid'] ?? '',
      };
    }
    final out = <String, dynamic>{
      'type': 'vless',
      'tag': 'proxy',
      'server': n.host,
      'server_port': n.port,
      'uuid': n.params['uuid'] ?? '',
      'tls': tls,
    };
    if ((n.params['flow'] ?? '').isNotEmpty) out['flow'] = n.params['flow'];
    return out;
  }

  Map<String, dynamic> _naive(NodeConfig n) => {
        'type': 'http',
        'tag': 'proxy',
        'server': n.host,
        'server_port': n.port,
        'username': n.params['username'] ?? '',
        'password': n.params['password'] ?? '',
        'tls': {'enabled': true, 'server_name': n.host},
      };
}
```

- [ ] **Step 4: Запустить — пройдёт**

Run: `flutter test test/services/config_builder_test.dart`
Expected: PASS (2 теста).

- [ ] **Step 5: Commit**

```bash
git add lib/services/config_builder.dart test/services/config_builder_test.dart
git commit -q -m "feat: sing-box config builder (vless/reality/naive)"
```

---

## Task 6: TunnelController + статус-модель + фейк

**Files:**
- Create: `lib/tunnel/tunnel_controller.dart`
- Test: `test/tunnel/fake_tunnel_test.dart`

- [ ] **Step 1: Написать падающий тест на фейк-реализацию**

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:singbox_client/tunnel/tunnel_controller.dart';

class FakeTunnel extends TunnelController {
  @override
  Future<void> start(Map<String, dynamic> config) async =>
      emit(TunnelStatus.connected);
  @override
  Future<void> stop() async => emit(TunnelStatus.disconnected);
}

void main() {
  test('start → connected, stop → disconnected', () async {
    final t = FakeTunnel();
    final seen = <TunnelStatus>[];
    t.statusStream.listen(seen.add);
    await t.start({});
    await t.stop();
    await Future<void>.delayed(Duration.zero);
    expect(seen, [TunnelStatus.connected, TunnelStatus.disconnected]);
  });
}
```

- [ ] **Step 2: Запустить — упадёт**

Run: `flutter test test/tunnel/fake_tunnel_test.dart`
Expected: FAIL — `tunnel_controller.dart` не найден.

- [ ] **Step 3: Реализовать абстракцию**

```dart
import 'dart:async';

enum TunnelStatus { disconnected, connecting, connected, error }

abstract class TunnelController {
  final _statusCtrl = StreamController<TunnelStatus>.broadcast();
  final _logCtrl = StreamController<String>.broadcast();

  Stream<TunnelStatus> get statusStream => _statusCtrl.stream;
  Stream<String> get logStream => _logCtrl.stream;

  TunnelStatus _status = TunnelStatus.disconnected;
  TunnelStatus get status => _status;

  /// Запускает туннель с готовым sing-box config (Map).
  Future<void> start(Map<String, dynamic> config);

  /// Останавливает туннель и снимает системный прокси.
  Future<void> stop();

  void emit(TunnelStatus s) {
    _status = s;
    _statusCtrl.add(s);
  }

  void emitLog(String line) => _logCtrl.add(line);

  Future<void> dispose() async {
    await _statusCtrl.close();
    await _logCtrl.close();
  }
}
```

- [ ] **Step 4: Запустить — пройдёт**

Run: `flutter test test/tunnel/fake_tunnel_test.dart`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/tunnel/tunnel_controller.dart test/tunnel/fake_tunnel_test.dart
git commit -q -m "feat: TunnelController abstraction + status model"
```

---

## Task 7: AppController (состояние приложения)

**Files:**
- Create: `lib/app/app_controller.dart`
- Test: `test/app/app_controller_test.dart`

- [ ] **Step 1: Написать падающие тесты с фейками**

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:singbox_client/app/app_controller.dart';
import 'package:singbox_client/models/node_config.dart';
import 'package:singbox_client/services/subscription_service.dart';
import 'package:singbox_client/services/config_builder.dart';
import 'package:singbox_client/tunnel/tunnel_controller.dart';

class FakeTunnel extends TunnelController {
  Map<String, dynamic>? lastConfig;
  @override
  Future<void> start(Map<String, dynamic> config) async {
    lastConfig = config;
    emit(TunnelStatus.connected);
  }
  @override
  Future<void> stop() async => emit(TunnelStatus.disconnected);
}

void main() {
  late FakeTunnel tunnel;
  late AppController app;

  setUp(() {
    tunnel = FakeTunnel();
    app = AppController(
      subscription: SubscriptionService(
        fetcher: (_) async =>
            'vless://uid@h:443?security=reality#A',
      ),
      builder: const ConfigBuilder(),
      tunnel: tunnel,
    );
  });

  test('loadSubscription заполняет nodes', () async {
    await app.loadSubscription('https://x');
    expect(app.nodes, hasLength(1));
    expect(app.nodes.first.protocol, NodeProtocol.vless);
  });

  test('connect строит конфиг и стартует туннель', () async {
    await app.loadSubscription('https://x');
    await app.connect(app.nodes.first);
    expect(tunnel.lastConfig!['outbounds'][0]['type'], 'vless');
    expect(app.status, TunnelStatus.connected);
  });

  test('disconnect останавливает туннель', () async {
    await app.loadSubscription('https://x');
    await app.connect(app.nodes.first);
    await app.disconnect();
    expect(app.status, TunnelStatus.disconnected);
  });
}
```

- [ ] **Step 2: Запустить — упадёт**

Run: `flutter test test/app/app_controller_test.dart`
Expected: FAIL — `app_controller.dart` не найден.

- [ ] **Step 3: Реализовать контроллер**

```dart
import 'package:flutter/foundation.dart';
import '../models/node_config.dart';
import '../services/subscription_service.dart';
import '../services/config_builder.dart';
import '../tunnel/tunnel_controller.dart';

class AppController extends ChangeNotifier {
  final SubscriptionService _subscription;
  final ConfigBuilder _builder;
  final TunnelController _tunnel;

  AppController({
    required SubscriptionService subscription,
    required ConfigBuilder builder,
    required TunnelController tunnel,
  })  : _subscription = subscription,
        _builder = builder,
        _tunnel = tunnel {
    _tunnel.statusStream.listen((s) {
      _status = s;
      notifyListeners();
    });
  }

  List<NodeConfig> _nodes = [];
  List<NodeConfig> get nodes => _nodes;

  TunnelStatus _status = TunnelStatus.disconnected;
  TunnelStatus get status => _status;

  String? _error;
  String? get error => _error;

  Future<void> loadSubscription(String url) async {
    try {
      _error = null;
      _nodes = await _subscription.load(url);
    } on SubscriptionException catch (e) {
      _error = e.message;
      _nodes = [];
    }
    notifyListeners();
  }

  Future<void> connect(NodeConfig node) async {
    _status = TunnelStatus.connecting;
    notifyListeners();
    await _tunnel.start(_builder.build(node));
  }

  Future<void> disconnect() => _tunnel.stop();
}
```

- [ ] **Step 4: Запустить — пройдёт**

Run: `flutter test test/app/app_controller_test.dart`
Expected: PASS (3 теста).

- [ ] **Step 5: Commit**

```bash
git add lib/app/app_controller.dart test/app/app_controller_test.dart
git commit -q -m "feat: AppController state orchestration"
```

---

## Task 8: MacOSProcessTunnel (Dart-сторона MethodChannel)

**Files:**
- Create: `lib/tunnel/macos_process_tunnel.dart`
- Test: `test/tunnel/macos_process_tunnel_test.dart`

- [ ] **Step 1: Написать тест с мок-каналом**

```dart
import 'dart:convert';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:singbox_client/tunnel/macos_process_tunnel.dart';
import 'package:singbox_client/tunnel/tunnel_controller.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const channel = MethodChannel('singbox/tunnel');

  test('start шлёт JSON-конфиг и эмитит connected', () async {
    final calls = <MethodCall>[];
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
      calls.add(call);
      return null;
    });

    final tunnel = MacOSProcessTunnel();
    final seen = <TunnelStatus>[];
    tunnel.statusStream.listen(seen.add);

    await tunnel.start({'outbounds': []});

    expect(calls.single.method, 'start');
    final sent = jsonDecode(calls.single.arguments['config'] as String);
    expect(sent['outbounds'], isEmpty);
    await Future<void>.delayed(Duration.zero);
    expect(seen, contains(TunnelStatus.connected));
  });
}
```

- [ ] **Step 2: Запустить — упадёт**

Run: `flutter test test/tunnel/macos_process_tunnel_test.dart`
Expected: FAIL — `macos_process_tunnel.dart` не найден.

- [ ] **Step 3: Реализовать Dart-сторону**

```dart
import 'dart:convert';
import 'package:flutter/services.dart';
import 'tunnel_controller.dart';

class MacOSProcessTunnel extends TunnelController {
  static const _channel = MethodChannel('singbox/tunnel');
  static const _events = EventChannel('singbox/tunnel/events');

  MacOSProcessTunnel() {
    _events.receiveBroadcastStream().listen((e) {
      final map = Map<String, dynamic>.from(e as Map);
      if (map['type'] == 'log') emitLog(map['line'] as String);
      if (map['type'] == 'status') {
        emit(TunnelStatus.values.byName(map['value'] as String));
      }
    });
  }

  @override
  Future<void> start(Map<String, dynamic> config) async {
    emit(TunnelStatus.connecting);
    try {
      await _channel.invokeMethod('start', {'config': jsonEncode(config)});
      emit(TunnelStatus.connected);
    } on PlatformException catch (e) {
      emitLog('start failed: ${e.message}');
      emit(TunnelStatus.error);
    }
  }

  @override
  Future<void> stop() async {
    await _channel.invokeMethod('stop');
    emit(TunnelStatus.disconnected);
  }
}
```

- [ ] **Step 4: Запустить — пройдёт**

Run: `flutter test test/tunnel/macos_process_tunnel_test.dart`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/tunnel/macos_process_tunnel.dart test/tunnel/macos_process_tunnel_test.dart
git commit -q -m "feat: macOS process tunnel (Dart MethodChannel side)"
```

---

## Task 9: Bundled бинарник sing-box

**Files:**
- Create: `macos/Runner/Resources/sing-box`
- Modify: `macos/Runner.xcodeproj` (через Xcode — добавить в Copy Bundle Resources)

- [ ] **Step 1: Скачать бинарник sing-box для macOS (arm64)**

```bash
cd /Users/anton/Documents/tests/singbox_flutter
mkdir -p macos/Runner/Resources
SBVER=1.11.4
curl -L -o /tmp/sb.tar.gz \
  "https://github.com/SagerNet/sing-box/releases/download/v${SBVER}/sing-box-${SBVER}-darwin-arm64.tar.gz"
tar -xzf /tmp/sb.tar.gz -C /tmp
cp /tmp/sing-box-${SBVER}-darwin-arm64/sing-box macos/Runner/Resources/sing-box
chmod +x macos/Runner/Resources/sing-box
```

- [ ] **Step 2: Проверить, что бинарник работает**

Run: `macos/Runner/Resources/sing-box version`
Expected: печатает версию sing-box.

- [ ] **Step 3: Добавить ресурс в Xcode-проект**

Открыть `macos/Runner.xcworkspace` в Xcode → перетащить `Resources/sing-box` в Runner target → отметить **Copy Bundle Resources**. Сохранить.

- [ ] **Step 4: Commit**

```bash
git add macos/Runner/Resources/sing-box macos/Runner.xcodeproj
git commit -q -m "chore: bundle sing-box macOS binary"
```

---

## Task 10: Native Swift (процесс + прокси + канал)

**Files:**
- Create: `macos/Runner/SystemProxy.swift`
- Create: `macos/Runner/SingboxProcess.swift`
- Create: `macos/Runner/TunnelChannel.swift`
- Modify: `macos/Runner/AppDelegate.swift` (зарегистрировать канал)

- [ ] **Step 1: SystemProxy.swift**

```swift
import Foundation

/// Управляет системным HTTP/HTTPS прокси через networksetup.
enum SystemProxy {
  static let service = "Wi-Fi"

  static func enable(host: String, port: Int) throws {
    try run(["-setwebproxy", service, host, String(port)])
    try run(["-setsecurewebproxy", service, host, String(port)])
    try run(["-setwebproxystate", service, "on"])
    try run(["-setsecurewebproxystate", service, "on"])
  }

  static func disable() {
    try? run(["-setwebproxystate", service, "off"])
    try? run(["-setsecurewebproxystate", service, "off"])
  }

  private static func run(_ args: [String]) throws {
    let p = Process()
    p.executableURL = URL(fileURLWithPath: "/usr/sbin/networksetup")
    p.arguments = args
    try p.run()
    p.waitUntilExit()
    if p.terminationStatus != 0 {
      throw NSError(domain: "SystemProxy", code: Int(p.terminationStatus))
    }
  }
}
```

- [ ] **Step 2: SingboxProcess.swift**

```swift
import Foundation

/// Жизненный цикл дочернего процесса sing-box.
final class SingboxProcess {
  private var process: Process?
  var onLog: ((String) -> Void)?

  func start(configJSON: String) throws {
    let dir = FileManager.default.temporaryDirectory
    let cfg = dir.appendingPathComponent("singbox-config.json")
    try configJSON.write(to: cfg, atomically: true, encoding: .utf8)

    guard let bin = Bundle.main.url(forResource: "sing-box", withExtension: nil)
    else { throw NSError(domain: "Singbox", code: 1,
            userInfo: [NSLocalizedDescriptionKey: "binary not bundled"]) }

    let p = Process()
    p.executableURL = bin
    p.arguments = ["run", "-c", cfg.path]
    let pipe = Pipe()
    p.standardOutput = pipe
    p.standardError = pipe
    pipe.fileHandleForReading.readabilityHandler = { [weak self] h in
      let data = h.availableData
      if let s = String(data: data, encoding: .utf8), !s.isEmpty {
        self?.onLog?(s)
      }
    }
    try p.run()
    process = p
  }

  func stop() {
    process?.terminate()
    process = nil
  }
}
```

- [ ] **Step 3: TunnelChannel.swift**

```swift
import FlutterMacOS
import Foundation

/// Связывает MethodChannel singbox/tunnel с процессом и системным прокси.
final class TunnelChannel: NSObject, FlutterStreamHandler {
  static let localHost = "127.0.0.1"
  static let localPort = 2080

  private let singbox = SingboxProcess()
  private var sink: FlutterEventSink?

  func register(with registrar: FlutterPluginRegistrar) {
    let method = FlutterMethodChannel(
      name: "singbox/tunnel", binaryMessenger: registrar.messenger)
    let events = FlutterEventChannel(
      name: "singbox/tunnel/events", binaryMessenger: registrar.messenger)
    events.setStreamHandler(self)

    singbox.onLog = { [weak self] line in
      self?.sink?(["type": "log", "line": line])
    }

    method.setMethodCallHandler { [weak self] call, result in
      guard let self = self else { return }
      switch call.method {
      case "start":
        guard let args = call.arguments as? [String: Any],
              let cfg = args["config"] as? String else {
          result(FlutterError(code: "ARG", message: "no config", details: nil))
          return
        }
        do {
          try self.singbox.start(configJSON: cfg)
          try SystemProxy.enable(host: Self.localHost, port: Self.localPort)
          result(nil)
        } catch {
          self.singbox.stop()
          SystemProxy.disable()
          result(FlutterError(code: "START",
                  message: error.localizedDescription, details: nil))
        }
      case "stop":
        SystemProxy.disable()
        self.singbox.stop()
        result(nil)
      default:
        result(FlutterMethodNotImplemented)
      }
    }
  }

  func onListen(withArguments _: Any?, eventSink events: @escaping FlutterEventSink)
      -> FlutterError? { sink = events; return nil }
  func onCancel(withArguments _: Any?) -> FlutterError? { sink = nil; return nil }
}
```

- [ ] **Step 4: Зарегистрировать канал и страховку очистки в AppDelegate.swift**

Заменить тело `AppDelegate`:

```swift
import Cocoa
import FlutterMacOS

@main
class AppDelegate: FlutterAppDelegate {
  private let tunnel = TunnelChannel()

  override func applicationDidFinishLaunching(_ notification: Notification) {
    let controller = mainFlutterWindow?.contentViewController
        as! FlutterViewController
    tunnel.register(with: controller.registrar(forPlugin: "TunnelChannel"))
    super.applicationDidFinishLaunching(notification)
  }

  override func applicationShouldTerminateAfterLastWindowClosed(
      _ sender: NSApplication) -> Bool { true }

  override func applicationWillTerminate(_ notification: Notification) {
    SystemProxy.disable() // страховка: не оставить юзера без интернета
  }
}
```

- [ ] **Step 5: Снять sandbox-ограничения для запуска процесса и networksetup**

В `macos/Runner/DebugProfile.entitlements` и `Release.entitlements` убрать
`com.apple.security.app-sandbox` (выставить `false`) — иначе нельзя запускать
бинарник и `networksetup`. Это осознанный компромисс MVP (App Store-совместимость —
отдельный цикл).

```xml
<key>com.apple.security.app-sandbox</key>
<false/>
```

- [ ] **Step 6: Собрать и убедиться, что компилируется**

Run: `flutter build macos --debug`
Expected: BUILD succeeded.

- [ ] **Step 7: Commit**

```bash
git add macos/
git commit -q -m "feat: native macOS tunnel (process + system proxy + channel)"
```

---

## Task 11: UI и сборка зависимостей

**Files:**
- Create: `lib/ui/home_screen.dart`
- Modify: `lib/main.dart`

- [ ] **Step 1: home_screen.dart**

```dart
import 'package:flutter/material.dart';
import '../app/app_controller.dart';
import '../tunnel/tunnel_controller.dart';

class HomeScreen extends StatefulWidget {
  final AppController controller;
  const HomeScreen({super.key, required this.controller});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final _url = TextEditingController();

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: widget.controller,
      builder: (context, _) {
        final c = widget.controller;
        return Scaffold(
          appBar: AppBar(title: Text('sing-box · ${c.status.name}')),
          body: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(children: [
                  Expanded(
                    child: TextField(
                      controller: _url,
                      decoration: const InputDecoration(
                          labelText: 'URL подписки'),
                    ),
                  ),
                  const SizedBox(width: 8),
                  FilledButton(
                    onPressed: () => c.loadSubscription(_url.text.trim()),
                    child: const Text('Загрузить'),
                  ),
                ]),
                if (c.error != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Text(c.error!,
                        style: const TextStyle(color: Colors.red)),
                  ),
                const SizedBox(height: 12),
                Expanded(
                  child: ListView.builder(
                    itemCount: c.nodes.length,
                    itemBuilder: (context, i) {
                      final n = c.nodes[i];
                      return ListTile(
                        title: Text(n.name),
                        subtitle: Text('${n.protocol.name} · ${n.host}:${n.port}'),
                        trailing: const Icon(Icons.bolt),
                        onTap: () => c.connect(n),
                      );
                    },
                  ),
                ),
                if (c.status == TunnelStatus.connected)
                  FilledButton.tonal(
                    onPressed: c.disconnect,
                    child: const Text('Отключить'),
                  ),
              ],
            ),
          ),
        );
      },
    );
  }
}
```

- [ ] **Step 2: main.dart — собрать зависимости**

```dart
import 'package:flutter/material.dart';
import 'app/app_controller.dart';
import 'services/subscription_service.dart';
import 'services/config_builder.dart';
import 'tunnel/macos_process_tunnel.dart';
import 'ui/home_screen.dart';

void main() {
  final controller = AppController(
    subscription: SubscriptionService(),
    builder: const ConfigBuilder(localPort: 2080),
    tunnel: MacOSProcessTunnel(),
  );
  runApp(MaterialApp(
    title: 'singbox client',
    theme: ThemeData(useMaterial3: true),
    home: HomeScreen(controller: controller),
  ));
}
```

- [ ] **Step 3: Прогнать весь тест-сьют**

Run: `flutter test`
Expected: все тесты PASS.

- [ ] **Step 4: Commit**

```bash
git add lib/ui/home_screen.dart lib/main.dart
git commit -q -m "feat: home screen UI and dependency wiring"
```

---

## Task 12: Сквозная ручная проверка (критерий успеха)

- [ ] **Step 1: Запустить приложение**

Run: `flutter run -d macos`
Expected: окно с полем URL.

- [ ] **Step 2: Загрузить реальную подписку**

Вставить URL подписки своего сервера → «Загрузить». Ожидаемо: список нод (vless/reality/naive).

- [ ] **Step 3: Подключиться к ноде**

Тапнуть vless/reality ноду. Статус в заголовке → `connected`. Системный прокси выставлен.

- [ ] **Step 4: Проверить трафик через прокси**

Run: `curl -x http://127.0.0.1:2080 -s https://api.ipify.org`
Expected: печатает внешний IP **сервера** (не домашний).

- [ ] **Step 5: Отключиться и проверить очистку**

Нажать «Отключить». Затем:
Run: `networksetup -getwebproxy Wi-Fi`
Expected: `Enabled: No`.

- [ ] **Step 6: Проверить страховку при выходе**

Подключиться снова, затем закрыть приложение (Cmd+Q). Проверить:
Run: `networksetup -getwebproxy Wi-Fi`
Expected: `Enabled: No` (прокси снят при терминации).

---

## Self-Review заметки

- **Покрытие спека:** подписка (Task 4), парсинг vless/reality/naive (Task 3), список нод (Task 11), config-генерация (Task 5), процесс sing-box (Task 9/10), системный прокси + очистка (Task 10), статусы (Task 6/7), критерий успеха (Task 12). ✓
- **naive:** маппинг на `http`-outbound с TLS — задокументированное приближение MVP; полная padding-совместимость вынесена в follow-up (как и в спеке).
- **Sandbox off** — осознанный MVP-компромисс; App Store/Network Extension — отдельный цикл.
- **Имена типов** согласованы между задачами: `NodeConfig`, `NodeProtocol`, `TunnelStatus`, `TunnelController.emit/emitLog`, `SubscriptionException`, `ConfigBuilder.build`, `AppController.connect/disconnect/loadSubscription`.
