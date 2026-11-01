import 'dart:async';
import 'dart:convert';
import 'dart:math';

import 'package:web_socket_channel/web_socket_channel.dart';

import '../models/telemetry_message.dart';

enum WsStatus { disconnected, connecting, connected, reconnecting }

/// One WebSocket per signed-in user (/ws/driver/{id} or /ws/fleet/{id}).
///
/// Reconnects by itself with exponential backoff (1 s → 15 s, with jitter),
/// gets a fresh token before every attempt, and treats 35 s of silence as a
/// dead link. Every message carrying a frame_id is echoed back as a `receipt`
/// with the phone's receive time, for the latency CSV.
class WebSocketService {
  static final WebSocketService _instance = WebSocketService._internal();
  factory WebSocketService() => _instance;
  WebSocketService._internal();

  final _events = StreamController<Map<String, dynamic>>.broadcast();
  final _statusCtl = StreamController<WsStatus>.broadcast();
  final _rand = Random();

  WebSocketChannel? _channel;
  StreamSubscription? _sub;
  Timer? _pingTimer;
  Timer? _retryTimer;
  Timer? _watchdog;
  DateTime _lastMessage = DateTime.now();
  int _attempt = 0;
  bool _wanted = false;
  WsStatus _status = WsStatus.disconnected;

  String Function()? _baseUrl;
  Future<String?> Function()? _token;
  String _path = '/ws';

  /// Every decoded server message.
  Stream<Map<String, dynamic>> get events => _events.stream;
  Stream<WsStatus> get statusStream => _statusCtl.stream;
  WsStatus get status => _status;
  bool get isConnected => _status == WsStatus.connected;

  Stream<TelemetryMessage> get telemetry =>
      events.where((m) => m['type'] == 'telemetry').map(TelemetryMessage.fromJson);

  Stream<Map<String, dynamic>> ofType(String type) => events.where((m) => m['type'] == type);

  void start({
    required String path,
    required String Function() baseUrl,
    required Future<String?> Function() token,
  }) {
    stop();
    _wanted = true;
    _path = path;
    _baseUrl = baseUrl;
    _token = token;
    _attempt = 0;
    _connect();
  }

  void stop() {
    _wanted = false;
    _retryTimer?.cancel();
    _teardown();
    _setStatus(WsStatus.disconnected);
  }

  /// Reconnect now (e.g. app returned to foreground).
  void kick() {
    if (!_wanted || _status == WsStatus.connected || _status == WsStatus.connecting) return;
    _retryTimer?.cancel();
    _attempt = 0;
    _connect();
  }

  void _setStatus(WsStatus s) {
    if (_status == s) return;
    _status = s;
    _statusCtl.add(s);
  }

  void _teardown() {
    _pingTimer?.cancel();
    _watchdog?.cancel();
    _sub?.cancel();
    _sub = null;
    try {
      _channel?.sink.close();
    } catch (_) {}
    _channel = null;
  }

  Future<void> _connect() async {
    if (!_wanted) return;
    _teardown();
    _setStatus(_attempt == 0 ? WsStatus.connecting : WsStatus.reconnecting);

    final base = _baseUrl?.call() ?? '';
    final token = await _token?.call();
    if (base.isEmpty || token == null) {
      _scheduleRetry();
      return;
    }
    final scheme = base.startsWith('https') ? 'wss' : 'ws';
    final host = base.replaceFirst(RegExp(r'^https?://'), '');
    final uri = Uri.parse('$scheme://$host$_path?token=${Uri.encodeQueryComponent(token)}');

    try {
      final ch = WebSocketChannel.connect(uri);
      _channel = ch;
      await ch.ready.timeout(const Duration(seconds: 6));
      if (!_wanted || _channel != ch) return;
      _attempt = 0;
      _lastMessage = DateTime.now();
      _setStatus(WsStatus.connected);
      _sub = ch.stream.listen(_onData, onError: (_) => _onClosed(), onDone: _onClosed, cancelOnError: true);
      _pingTimer = Timer.periodic(const Duration(seconds: 15), (_) => _send({'type': 'ping'}));
      _watchdog = Timer.periodic(const Duration(seconds: 5), (_) {
        if (DateTime.now().difference(_lastMessage) > const Duration(seconds: 35)) _onClosed();
      });
    } catch (_) {
      _onClosed();
    }
  }

  void _onData(dynamic data) {
    final receivedMs = DateTime.now().millisecondsSinceEpoch;
    _lastMessage = DateTime.now();
    Map<String, dynamic> msg;
    try {
      msg = (jsonDecode(data.toString()) as Map).cast<String, dynamic>();
    } catch (_) {
      return;
    }
    final frameId = msg['frame_id'];
    if (frameId is String && frameId.isNotEmpty) {
      _send({'type': 'receipt', 'frame_id': frameId, 'received_ms': receivedMs});
    }
    _events.add(msg);
  }

  void _onClosed() {
    if (!_wanted) return;
    _teardown();
    _scheduleRetry();
  }

  void _scheduleRetry() {
    _setStatus(WsStatus.reconnecting);
    _retryTimer?.cancel();
    final base = min(15.0, pow(2, _attempt).toDouble());
    final delay = Duration(milliseconds: (base * 1000 * (0.8 + _rand.nextDouble() * 0.4)).round());
    _attempt = min(_attempt + 1, 6);
    _retryTimer = Timer(delay, _connect);
  }

  void _send(Map<String, dynamic> m) {
    try {
      _channel?.sink.add(jsonEncode(m));
    } catch (_) {}
  }
}
