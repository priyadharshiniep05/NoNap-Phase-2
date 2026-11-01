import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/alert_item.dart';
import '../services/api_service.dart';
import 'auth_provider.dart';

class DriverDataState {
  final Map<String, dynamic>? stats;
  final List<AlertItem> alerts;
  final Map<String, dynamic>? thresholds;
  final bool isLoading;
  final bool loaded;
  final String? error;

  const DriverDataState({
    this.stats,
    this.alerts = const [],
    this.thresholds,
    this.isLoading = false,
    this.loaded = false,
    this.error,
  });

  DriverDataState copyWith({
    Map<String, dynamic>? stats,
    List<AlertItem>? alerts,
    Map<String, dynamic>? thresholds,
    bool? isLoading,
    bool? loaded,
    String? error,
  }) {
    return DriverDataState(
      stats: stats ?? this.stats,
      alerts: alerts ?? this.alerts,
      thresholds: thresholds ?? this.thresholds,
      isLoading: isLoading ?? this.isLoading,
      loaded: loaded ?? this.loaded,
      error: error,
    );
  }

  double get earThreshold => (thresholds?['ear_threshold'] as num?)?.toDouble() ?? 0.21;
  double get marThreshold => (thresholds?['mar_threshold'] as num?)?.toDouble() ?? 0.60;
}

/// Insert or replace an alert by id, newest first (pure, unit-tested).
List<AlertItem> upsertAlert(List<AlertItem> list, AlertItem a, {int cap = 200}) {
  final rest = list.where((x) => x.id != a.id);
  final merged = [a, ...rest]..sort((x, y) => y.detectedAt.compareTo(x.detectedAt));
  return merged.take(cap).toList();
}

class DriverDataNotifier extends StateNotifier<DriverDataState> {
  final ApiService _api;

  DriverDataNotifier(this._api) : super(const DriverDataState()) {
    refresh();
  }

  Future<void> refresh() async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final results = await Future.wait([
        _api.getDriverStats(),
        _api.getDriverAlerts(limit: 150),
        _api.getDriverThresholds(),
      ]);
      state = state.copyWith(
        stats: results[0] as Map<String, dynamic>,
        alerts: results[1] as List<AlertItem>,
        thresholds: results[2] as Map<String, dynamic>,
        isLoading: false,
        loaded: true,
      );
    } catch (e) {
      state = state.copyWith(isLoading: false, error: friendlyError(e));
    }
  }

  void upsert(AlertItem a) => state = state.copyWith(alerts: upsertAlert(state.alerts, a));

  Future<String?> updateThresholds(Map<String, dynamic> data) async {
    try {
      final updated = await _api.updateDriverThresholds(data);
      state = state.copyWith(thresholds: updated);
      return null;
    } catch (e) {
      return friendlyError(e);
    }
  }

  Future<void> reloadThresholds() async {
    try {
      state = state.copyWith(thresholds: await _api.getDriverThresholds());
    } catch (_) {}
  }
}

final driverDataProvider = StateNotifierProvider.autoDispose<DriverDataNotifier, DriverDataState>((ref) {
  return DriverDataNotifier(ref.watch(apiServiceProvider));
});
