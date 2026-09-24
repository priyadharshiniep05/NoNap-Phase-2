import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/telemetry_message.dart';
import '../services/alert_player.dart';
import '../services/notification_service.dart';
import 'auth_provider.dart';

class TelemetryState {
  final TelemetryMessage? latest;
  final List<TelemetryMessage> liveAlerts;
  final bool isMonitoring;

  TelemetryState({
    this.latest,
    this.liveAlerts = const [],
    this.isMonitoring = false,
  });

  TelemetryState copyWith({
    TelemetryMessage? latest,
    List<TelemetryMessage>? liveAlerts,
    bool? isMonitoring,
  }) {
    return TelemetryState(
      latest: latest ?? this.latest,
      liveAlerts: liveAlerts ?? this.liveAlerts,
      isMonitoring: isMonitoring ?? this.isMonitoring,
    );
  }
}

class TelemetryNotifier extends StateNotifier<TelemetryState> {
  final Ref _ref;
  final AlertPlayer _alertPlayer = AlertPlayer();
  final NotificationService _notifyService = NotificationService();

  TelemetryNotifier(this._ref) : super(TelemetryState()) {
    _initListener();
  }

  void _initListener() {
    final ws = _ref.read(wsServiceProvider);
    ws.messages.listen((msg) {
      final isAlert = msg.isAlert;

      // Handle sound and push notification if drowsy or accident
      if (isAlert) {
        final isCrit = msg.status == 'accident' || msg.severity == 'critical';
        _alertPlayer.playAlert(isCritical: isCrit);

        _notifyService.showAlertNotification(
          title: isCrit ? 'CRITICAL ALERT' : 'Drowsiness Detected',
          body: msg.message.isNotEmpty
              ? msg.message
              : 'Alert recorded at ${msg.timestamp}',
        );

        // Prepend to live alerts list
        final updatedAlerts = [msg, ...state.liveAlerts.take(19)];
        state = state.copyWith(latest: msg, liveAlerts: updatedAlerts);
      } else {
        state = state.copyWith(latest: msg);
      }
    });
  }

  void setMonitoring(bool running) {
    state = state.copyWith(isMonitoring: running);
  }

  void clearAlerts() {
    state = state.copyWith(liveAlerts: []);
  }
}

final telemetryProvider = StateNotifierProvider<TelemetryNotifier, TelemetryState>((ref) {
  return TelemetryNotifier(ref);
});
