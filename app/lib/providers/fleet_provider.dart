import 'dart:async';

import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/alert_item.dart';
import '../models/device_status.dart';
import '../models/fleet_overview.dart';
import '../models/telemetry_message.dart';
import '../services/api_service.dart';
import '../services/notification_service.dart';
import '../services/ws_service.dart';
import 'auth_provider.dart';
import 'driver_provider.dart' show upsertAlert;

class FleetDataState {
  final FleetOverview? overview;
  final List<AlertItem> alerts;
  final Map<String, dynamic>? thresholds;
  final bool isLoading;
  final String? error;

  /// Ids of feed items that arrived live (for the slide-in animation).
  final Set<String> freshIds;

  const FleetDataState({
    this.overview,
    this.alerts = const [],
    this.thresholds,
    this.isLoading = false,
    this.error,
    this.freshIds = const {},
  });

  FleetDataState copyWith({
    FleetOverview? overview,
    List<AlertItem>? alerts,
    Map<String, dynamic>? thresholds,
    bool? isLoading,
    String? error,
    Set<String>? freshIds,
  }) {
    return FleetDataState(
      overview: overview ?? this.overview,
      alerts: alerts ?? this.alerts,
      thresholds: thresholds ?? this.thresholds,
      isLoading: isLoading ?? this.isLoading,
      error: error,
      freshIds: freshIds ?? this.freshIds,
    );
  }

  /// Drivers in an active alert first (level 3 before 2 before 1), then online, then by name.
  List<FleetDriverItem> get sortedDrivers {
    final list = [...?overview?.drivers];
    int rank(FleetDriverItem d) => d.inActiveAlert ? 10 - d.activeAlert!.effectiveLevel : (d.online ? 20 : 30);
    list.sort((a, b) {
      final r = rank(a).compareTo(rank(b));
      return r != 0 ? r : a.displayName.compareTo(b.displayName);
    });
    return list;
  }
}

/// Apply one alert_event to the fleet state (pure, unit-tested).
FleetDataState applyFleetAlertEvent(FleetDataState s, String event, AlertItem a) {
  final o = s.overview;
  if (o == null) return s;
  final isNew = event == 'raised';
  final drivers = o.drivers.map((d) {
    if (d.driverId != a.driverId) return d;
    switch (event) {
      case 'raised':
      case 'upgraded':
      case 'escalated':
        return d.copyWith(
          activeAlert: a,
          currentStatus: a.type == 'yawning' ? 'yawning' : 'drowsy',
          lastAlertAt: a.detectedAt,
          alertsToday: d.alertsToday + (isNew ? 1 : 0),
        );
      case 'acknowledged':
      case 'resolved':
        return d.activeAlert?.id == a.id ? d.copyWith(clearActiveAlert: true, currentStatus: 'alert') : d;
    }
    return d;
  }).toList();

  final alertsToday = o.alertsToday + (isNew ? 1 : 0);
  double? avg = o.avgResponseMsToday;
  if (event == 'acknowledged' && a.responseTimeMs != null) {
    // Running mean over today's acknowledged alerts in the feed.
    final acked = [
      ...s.alerts.where((x) => x.id != a.id && x.responseTimeMs != null && _isToday(x.detectedAt)),
      a,
    ];
    avg = acked.map((x) => x.responseTimeMs!).reduce((p, q) => p + q) / acked.length;
  }

  return s.copyWith(
    overview: o.withDrivers(drivers, alertsToday: alertsToday, avgResponseMsToday: avg),
    alerts: upsertAlert(s.alerts, a, cap: 100),
    freshIds: isNew ? {...s.freshIds, a.id} : s.freshIds,
  );
}

bool _isToday(DateTime t) {
  final ist = t.toUtc().add(const Duration(hours: 5, minutes: 30));
  final now = DateTime.now().toUtc().add(const Duration(hours: 5, minutes: 30));
  return ist.year == now.year && ist.month == now.month && ist.day == now.day;
}

class FleetDataNotifier extends StateNotifier<FleetDataState> {
  final ApiService _api;
  final List<StreamSubscription> _subs = [];

  FleetDataNotifier(this._api, WebSocketService ws) : super(const FleetDataState(isLoading: true)) {
    _subs.add(ws.events.listen(_onEvent));
    _subs.add(ws.statusStream.listen((s) {
      if (s == WsStatus.connected && state.overview != null) refresh(silent: true);
    }));
    refresh();
  }

  void _onEvent(Map<String, dynamic> m) {
    switch (m['type']) {
      case 'alert_event':
        final raw = m['alert'];
        if (raw is! Map) return;
        final a = AlertItem.fromJson(raw.cast<String, dynamic>());
        final event = m['event'] as String? ?? '';
        state = applyFleetAlertEvent(state, event, a);
        if (event == 'escalated') {
          HapticFeedback.heavyImpact();
          NotificationService().showIfBackground(
            title: '${a.displayDriverName} is not responding',
            body: m['message'] as String? ?? 'Level 3 drowsiness alert, unacknowledged.',
            id: a.id.hashCode,
          );
        }
        break;
      case 'telemetry':
        _onTelemetry(TelemetryMessage.fromJson(m));
        break;
      case 'device_status':
        final d = m['device'];
        if (d is Map<String, dynamic>) _onDevice(DeviceStatus.fromJson(d));
        break;
    }
  }

  void _onTelemetry(TelemetryMessage t) {
    final o = state.overview;
    if (o == null) return;
    var changed = false;
    final drivers = o.drivers.map((d) {
      if (d.driverId != t.driverId) return d;
      final status = d.inActiveAlert ? d.currentStatus : t.status;
      if (status == d.currentStatus && d.online && (t.ear - d.ear).abs() < 0.01) return d;
      changed = true;
      return d.copyWith(currentStatus: status, ear: t.hasFace ? t.ear : d.ear, online: true);
    }).toList();
    if (changed) state = state.copyWith(overview: o.withDrivers(drivers));
  }

  void _onDevice(DeviceStatus dev) {
    final o = state.overview;
    if (o == null || dev.driverId == null) return;
    final drivers = o.drivers.map((d) {
      if (d.driverId != dev.driverId) return d;
      return d.copyWith(
        deviceId: dev.deviceId,
        deviceOnline: dev.online,
        online: dev.online,
        vehicle: dev.vehicle,
        fps: dev.fps,
        cpuTempC: dev.cpuTempC,
        currentStatus: dev.online ? (d.currentStatus == 'offline' ? 'alert' : d.currentStatus) : 'offline',
      );
    }).toList();
    state = state.copyWith(overview: o.withDrivers(drivers));
  }

  Future<void> refresh({bool silent = false}) async {
    if (!silent) state = state.copyWith(isLoading: true, error: null);
    try {
      final results = await Future.wait([_api.getFleetOverview(), _api.getFleetAlerts(limit: 60), _api.getFleetThresholds()]);
      state = state.copyWith(
        overview: results[0] as FleetOverview,
        alerts: results[1] as List<AlertItem>,
        thresholds: results[2] as Map<String, dynamic>,
        isLoading: false,
        freshIds: const {},
      );
    } catch (e) {
      state = state.copyWith(isLoading: false, error: friendlyError(e));
    }
  }

  Future<String?> updateThresholds(Map<String, dynamic> data) async {
    try {
      state = state.copyWith(thresholds: await _api.updateFleetThresholds(data));
      return null;
    } catch (e) {
      return friendlyError(e);
    }
  }

  @override
  void dispose() {
    for (final s in _subs) {
      s.cancel();
    }
    super.dispose();
  }
}

final fleetDataProvider = StateNotifierProvider.autoDispose<FleetDataNotifier, FleetDataState>((ref) {
  return FleetDataNotifier(ref.watch(apiServiceProvider), ref.watch(wsServiceProvider));
});

/// One driver's alert timeline for the detail screen.
final fleetDriverAlertsProvider = FutureProvider.autoDispose.family<List<AlertItem>, String>((ref, driverId) {
  return ref.watch(apiServiceProvider).getFleetDriverAlerts(driverId);
});
