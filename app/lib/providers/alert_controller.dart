import 'dart:async';

import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/alert_item.dart';
import '../services/alarm_service.dart';
import '../services/api_service.dart';
import '../services/notification_service.dart';
import '../services/ws_service.dart';
import 'auth_provider.dart';
import 'driver_provider.dart';

/// What the driver sees right now.
class AlertUiState {
  /// Level 1: amber banner (auto-dismisses after 4 s).
  final AlertItem? banner;
  final String bannerMessage;

  /// Level 2-3: full-screen takeover.
  final AlertItem? takeover;
  final String takeoverMessage;
  final String spoken;
  final DateTime? countdownStart;
  final bool acking;
  final String? ackError;

  /// Shown briefly after "I'm awake": "Stay safe — consider a break".
  final AlertItem? confirmed;

  const AlertUiState({
    this.banner,
    this.bannerMessage = '',
    this.takeover,
    this.takeoverMessage = '',
    this.spoken = '',
    this.countdownStart,
    this.acking = false,
    this.ackError,
    this.confirmed,
  });

  int get level => takeover?.effectiveLevel ?? (banner != null ? 1 : 0);

  AlertUiState copyWith({
    AlertItem? banner,
    bool clearBanner = false,
    String? bannerMessage,
    AlertItem? takeover,
    bool clearTakeover = false,
    String? takeoverMessage,
    String? spoken,
    DateTime? countdownStart,
    bool? acking,
    String? ackError,
    AlertItem? confirmed,
    bool clearConfirmed = false,
  }) {
    return AlertUiState(
      banner: clearBanner ? null : (banner ?? this.banner),
      bannerMessage: bannerMessage ?? this.bannerMessage,
      takeover: clearTakeover ? null : (takeover ?? this.takeover),
      takeoverMessage: takeoverMessage ?? this.takeoverMessage,
      spoken: spoken ?? this.spoken,
      countdownStart: clearTakeover ? null : (countdownStart ?? this.countdownStart),
      acking: acking ?? this.acking,
      ackError: ackError,
      confirmed: clearConfirmed ? null : (confirmed ?? this.confirmed),
    );
  }
}

/// Turns server alert_event messages into the phone's alarm behaviour.
class AlertController extends StateNotifier<AlertUiState> {
  final Ref _ref;
  final ApiService _api;
  final AlarmService _alarm;
  final List<StreamSubscription> _subs = [];
  Timer? _bannerTimer;
  Timer? _confirmTimer;
  final Set<String> _acked = {};

  AlertController(this._ref, this._api, this._alarm, WebSocketService ws) : super(const AlertUiState()) {
    _alarm.init();
    _subs.add(ws.ofType('alert_event').listen(_onAlertEvent));
    _subs.add(ws.ofType('snapshot').listen(_onSnapshot));
  }

  void _onSnapshot(Map<String, dynamic> m) {
    // Reconnected mid-alert: bring the open alert back on screen.
    for (final raw in (m['open_alerts'] as List? ?? const [])) {
      final a = AlertItem.fromJson((raw as Map).cast<String, dynamic>());
      if (a.effectiveLevel >= 2 && !_acked.contains(a.id) && state.takeover?.id != a.id) {
        _showTakeover(a, a.effectiveLevel >= 3 ? 'Your fleet manager has been notified.' : 'You seem drowsy.',
            _defaultSpoken(a));
      }
    }
  }

  void _onAlertEvent(Map<String, dynamic> m) {
    final raw = m['alert'];
    if (raw is! Map) return;
    final a = AlertItem.fromJson(raw.cast<String, dynamic>());
    final event = m['event'] as String? ?? '';
    final message = m['message'] as String? ?? '';
    final spoken = m['spoken'] as String? ?? '';

    _ref.read(driverDataProvider.notifier).upsert(a);

    switch (event) {
      case 'raised':
      case 'upgraded':
      case 'escalated':
        if (_acked.contains(a.id)) return;
        if (a.effectiveLevel >= 2) {
          _showTakeover(a, message, spoken);
        } else {
          _showBanner(a, message);
        }
        NotificationService().showIfBackground(
          title: a.effectiveLevel >= 2 ? 'Wake up! Level ${a.effectiveLevel} drowsiness alert' : 'Stay focused',
          body: message,
          id: a.id.hashCode,
        );
        break;
      case 'acknowledged':
        _acked.add(a.id);
        if (state.takeover?.id == a.id || state.banner?.id == a.id) _finish(a);
        break;
      case 'resolved':
        if (state.banner?.id == a.id) _dismissBanner();
        break;
    }
  }

  String _defaultSpoken(AlertItem a) {
    final name = firstNameOf(a.driverName ?? 'Driver');
    return a.effectiveLevel >= 3
        ? '$name, wake up. Your fleet manager has been notified. Please pull over now.'
        : '$name, you seem drowsy. Please pull over and take a break.';
  }

  void _showBanner(AlertItem a, String message) {
    if (state.takeover != null) return;
    _bannerTimer?.cancel();
    state = state.copyWith(banner: a, bannerMessage: message, clearConfirmed: true);
    _alarm.chime();
    _bannerTimer = Timer(const Duration(seconds: 4), _dismissBanner);
  }

  void _dismissBanner() {
    _bannerTimer?.cancel();
    if (mounted && state.banner != null) state = state.copyWith(clearBanner: true);
  }

  void _showTakeover(AlertItem a, String message, String spoken) {
    _bannerTimer?.cancel();
    final sameAlert = state.takeover?.id == a.id;
    state = state.copyWith(
      takeover: a,
      takeoverMessage: message,
      spoken: spoken.isNotEmpty ? spoken : _defaultSpoken(a),
      // The 10 s ring starts when level 2 first appears; level 3 keeps it drained.
      countdownStart: sameAlert ? state.countdownStart : DateTime.now(),
      clearBanner: true,
      clearConfirmed: true,
    );
    HapticFeedback.heavyImpact();
    _alarm.startCritical(state.spoken);
  }

  /// "I'm awake": stop everything at once, then tell the server.
  Future<void> acknowledge() async {
    final a = state.takeover ?? state.banner;
    if (a == null || state.acking) return;
    _acked.add(a.id);
    await _alarm.stopAll();
    HapticFeedback.lightImpact();
    state = state.copyWith(acking: true, ackError: null);
    try {
      final updated = await _api.acknowledgeAlert(a.id);
      _ref.read(driverDataProvider.notifier).upsert(updated);
      _finish(updated);
    } catch (e) {
      // Not recorded on the server: keep the alert up and ring again.
      _acked.remove(a.id);
      state = state.copyWith(acking: false, ackError: friendlyError(e));
      if (a.effectiveLevel >= 2) _alarm.startCritical(state.spoken);
    }
  }

  void _finish(AlertItem a) {
    _alarm.stopAll();
    _bannerTimer?.cancel();
    final hadTakeover = state.takeover != null;
    state = state.copyWith(
      clearTakeover: true,
      clearBanner: true,
      acking: false,
      // The WS "acknowledged" event and the HTTP ack response both land here;
      // the second call must not hide the confirmation the first one showed.
      confirmed: hadTakeover ? a : null,
    );
    _confirmTimer?.cancel();
    if (hadTakeover) {
      _confirmTimer = Timer(const Duration(seconds: 6), dismissConfirmation);
    }
  }

  void dismissConfirmation() {
    _confirmTimer?.cancel();
    if (mounted) state = state.copyWith(clearConfirmed: true);
  }

  @override
  void dispose() {
    for (final s in _subs) {
      s.cancel();
    }
    _bannerTimer?.cancel();
    _confirmTimer?.cancel();
    _alarm.stopAll();
    super.dispose();
  }
}

final alarmServiceProvider = Provider<AlarmService>((ref) => AlarmService());

final alertControllerProvider = StateNotifierProvider.autoDispose<AlertController, AlertUiState>((ref) {
  return AlertController(
    ref,
    ref.watch(apiServiceProvider),
    ref.watch(alarmServiceProvider),
    ref.watch(wsServiceProvider),
  );
});
