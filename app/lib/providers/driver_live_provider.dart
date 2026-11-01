import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:wakelock_plus/wakelock_plus.dart';

import '../models/device_status.dart';
import '../models/session_info.dart';
import '../models/telemetry_message.dart';
import '../services/api_service.dart';
import '../services/notification_service.dart';
import '../services/ws_service.dart';
import 'auth_provider.dart';

/// One sample on a sparkline (time in ms since epoch).
class SeriesPoint {
  final int t;
  final double v;
  const SeriesPoint(this.t, this.v);
}

class CalibrationState {
  final bool running;
  final double progress; // 0..1
  final double remaining;
  final Map<String, dynamic>? result;
  final String? error;

  const CalibrationState({this.running = false, this.progress = 0, this.remaining = 0, this.result, this.error});
}

class DriverLiveState {
  final TelemetryMessage? latest;
  final DateTime? latestAt;
  final List<SeriesPoint> ear;
  final List<SeriesPoint> mar;
  final DeviceStatus? device;
  final String videoSource; // pi | webcam
  final SessionInfo session;
  final bool sessionBusy;
  final CalibrationState calibration;
  final int ackTimeoutSeconds;

  const DriverLiveState({
    this.latest,
    this.latestAt,
    this.ear = const [],
    this.mar = const [],
    this.device,
    this.videoSource = 'pi',
    this.session = const SessionInfo(),
    this.sessionBusy = false,
    this.calibration = const CalibrationState(),
    this.ackTimeoutSeconds = 10,
  });

  /// Telemetry is "live" if a frame result arrived in the last 5 s.
  bool get isLive => latestAt != null && DateTime.now().difference(latestAt!) < const Duration(seconds: 5);

  bool get cameraOnline => videoSource == 'webcam' ? isLive : (device?.online ?? false);

  DriverLiveState copyWith({
    TelemetryMessage? latest,
    DateTime? latestAt,
    List<SeriesPoint>? ear,
    List<SeriesPoint>? mar,
    DeviceStatus? device,
    String? videoSource,
    SessionInfo? session,
    bool? sessionBusy,
    CalibrationState? calibration,
    int? ackTimeoutSeconds,
  }) {
    return DriverLiveState(
      latest: latest ?? this.latest,
      latestAt: latestAt ?? this.latestAt,
      ear: ear ?? this.ear,
      mar: mar ?? this.mar,
      device: device ?? this.device,
      videoSource: videoSource ?? this.videoSource,
      session: session ?? this.session,
      sessionBusy: sessionBusy ?? this.sessionBusy,
      calibration: calibration ?? this.calibration,
      ackTimeoutSeconds: ackTimeoutSeconds ?? this.ackTimeoutSeconds,
    );
  }
}

/// Keep only the last [windowMs] of samples (pure, unit-tested).
List<SeriesPoint> appendWindowed(List<SeriesPoint> series, SeriesPoint p, {int windowMs = 60000}) {
  final cutoff = p.t - windowMs;
  return [...series.where((s) => s.t >= cutoff), p];
}

class DriverLiveNotifier extends StateNotifier<DriverLiveState> {
  final ApiService _api;
  final WebSocketService _ws;
  final List<StreamSubscription> _subs = [];
  Timer? _tick;

  DriverLiveNotifier(this._api, this._ws) : super(const DriverLiveState()) {
    _subs.add(_ws.events.listen(_onEvent));
    _subs.add(_ws.statusStream.listen((s) {
      if (s == WsStatus.connected) refresh();
    }));
    // Re-evaluate "live" and session clock once a second.
    _tick = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) state = state.copyWith();
    });
    refresh();
  }

  Future<void> refresh() async {
    try {
      final results = await Future.wait([_api.getMyDevice(), _api.getSession(), _api.getSystem()]);
      final (source, device) = results[0] as (String, DeviceStatus?);
      final session = results[1] as SessionInfo;
      final system = results[2] as Map<String, dynamic>;
      if (!mounted) return;
      state = state.copyWith(
        videoSource: source,
        device: device,
        session: session,
        ackTimeoutSeconds: (system['ack_timeout_seconds'] as num?)?.round() ?? 10,
      );
      _applyWakelock(session.active);
    } catch (_) {
      // Indicators show the disconnected state; WS reconnect triggers another refresh.
    }
  }

  void _onEvent(Map<String, dynamic> m) {
    switch (m['type']) {
      case 'telemetry':
        final t = TelemetryMessage.fromJson(m);
        final now = DateTime.now().millisecondsSinceEpoch;
        state = state.copyWith(
          latest: t,
          latestAt: DateTime.now(),
          ear: t.hasFace ? appendWindowed(state.ear, SeriesPoint(now, t.ear)) : state.ear,
          mar: t.hasFace ? appendWindowed(state.mar, SeriesPoint(now, t.mar)) : state.mar,
        );
        break;
      case 'device_status':
        final d = m['device'];
        if (d is Map<String, dynamic>) state = state.copyWith(device: DeviceStatus.fromJson(d));
        break;
      case 'snapshot':
        final devices = (m['devices'] as List?) ?? const [];
        if (devices.isNotEmpty) {
          final list = devices.cast<Map<String, dynamic>>().map(DeviceStatus.fromJson).toList()
            ..sort((a, b) => (b.lastSeenAt ?? DateTime(0)).compareTo(a.lastSeenAt ?? DateTime(0)));
          state = state.copyWith(device: list.first);
        }
        break;
      case 'calibration_progress':
        state = state.copyWith(
          calibration: CalibrationState(
            running: true,
            progress: (m['progress'] as num?)?.toDouble() ?? 0,
            remaining: (m['remaining_seconds'] as num?)?.toDouble() ?? 0,
          ),
        );
        break;
      case 'calibration_complete':
        state = state.copyWith(calibration: CalibrationState(progress: 1, result: m));
        break;
    }
  }

  Future<String?> startSession() {
    NotificationService().requestPermission();
    return _session(_api.startSession);
  }

  Future<String?> endSession() => _session(_api.endSession);

  Future<String?> _session(Future<SessionInfo> Function() call) async {
    state = state.copyWith(sessionBusy: true);
    try {
      final s = await call();
      state = state.copyWith(session: s, sessionBusy: false);
      _applyWakelock(s.active);
      return null;
    } catch (e) {
      state = state.copyWith(sessionBusy: false);
      return friendlyError(e);
    }
  }

  Future<void> refreshSession() async {
    try {
      final s = await _api.getSession();
      if (mounted) state = state.copyWith(session: s);
    } catch (_) {}
  }

  Future<String?> startCalibration() async {
    state = state.copyWith(calibration: const CalibrationState(running: true));
    try {
      await _api.startCalibration(duration: 10);
      return null;
    } catch (e) {
      final msg = friendlyError(e);
      state = state.copyWith(calibration: CalibrationState(error: msg));
      return msg;
    }
  }

  void resetCalibration() => state = state.copyWith(calibration: const CalibrationState());

  void _applyWakelock(bool driving) {
    // Keep the screen on while driving mode is active.
    (driving ? WakelockPlus.enable() : WakelockPlus.disable()).catchError((_) {});
  }

  @override
  void dispose() {
    for (final s in _subs) {
      s.cancel();
    }
    _tick?.cancel();
    WakelockPlus.disable().catchError((_) {});
    super.dispose();
  }
}

final driverLiveProvider = StateNotifierProvider.autoDispose<DriverLiveNotifier, DriverLiveState>((ref) {
  return DriverLiveNotifier(ref.watch(apiServiceProvider), ref.watch(wsServiceProvider));
});
