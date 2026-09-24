import 'dart:async';
import 'dart:convert';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../models/telemetry_message.dart';

class WebSocketService {
  static final WebSocketService _instance = WebSocketService._internal();
  factory WebSocketService() => _instance;
  WebSocketService._internal();

  WebSocketChannel? _channel;
  final StreamController<TelemetryMessage> _messageController =
      StreamController<TelemetryMessage>.broadcast();
  Timer? _pingTimer;
  bool _isConnected = false;

  Stream<TelemetryMessage> get messages => _messageController.stream;
  bool get isConnected => _isConnected;

  void connect({required String baseUrl, required String token}) {
    disconnect();

    final wsScheme = baseUrl.startsWith('https') ? 'wss' : 'ws';
    final hostAndPort = baseUrl.replaceFirst(RegExp(r'^https?://'), '');
    final uri = Uri.parse('$wsScheme://$hostAndPort/ws?token=$token');

    try {
      _channel = WebSocketChannel.connect(uri);
      _isConnected = true;

      _channel?.stream.listen(
        (data) {
          try {
            final json = jsonDecode(data.toString()) as Map<String, dynamic>;
            final message = TelemetryMessage.fromJson(json);
            _messageController.add(message);
          } catch (e) {
            // Non-telemetry message (e.g. raw pong)
          }
        },
        onError: (err) {
          _isConnected = false;
        },
        onDone: () {
          _isConnected = false;
        },
      );

      // Keepalive ping every 20 seconds
      _pingTimer = Timer.periodic(const Duration(seconds: 20), (_) {
        if (_isConnected && _channel != null) {
          try {
            _channel!.sink.add(jsonEncode({'type': 'ping'}));
          } catch (_) {}
        }
      });
    } catch (e) {
      _isConnected = false;
    }
  }

  void disconnect() {
    _pingTimer?.cancel();
    _pingTimer = null;
    _channel?.sink.close();
    _channel = null;
    _isConnected = false;
  }
}
