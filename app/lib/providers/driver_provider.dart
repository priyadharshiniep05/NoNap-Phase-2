import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/alert_item.dart';
import '../services/api_service.dart';
import 'auth_provider.dart';

class DriverDataState {
  final Map<String, dynamic>? stats;
  final List<AlertItem> alerts;
  final Map<String, dynamic>? thresholds;
  final bool isLoading;
  final String? error;

  DriverDataState({
    this.stats,
    this.alerts = const [],
    this.thresholds,
    this.isLoading = false,
    this.error,
  });

  DriverDataState copyWith({
    Map<String, dynamic>? stats,
    List<AlertItem>? alerts,
    Map<String, dynamic>? thresholds,
    bool? isLoading,
    String? error,
  }) {
    return DriverDataState(
      stats: stats ?? this.stats,
      alerts: alerts ?? this.alerts,
      thresholds: thresholds ?? this.thresholds,
      isLoading: isLoading ?? this.isLoading,
      error: error,
    );
  }
}

class DriverDataNotifier extends StateNotifier<DriverDataState> {
  final ApiService _api;

  DriverDataNotifier(this._api) : super(DriverDataState()) {
    refresh();
  }

  Future<void> refresh() async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final statsFuture = _api.getDriverStats();
      final alertsFuture = _api.getDriverAlerts(limit: 40);
      final thresholdsFuture = _api.getDriverThresholds();

      final results = await Future.wait([statsFuture, alertsFuture, thresholdsFuture]);

      state = state.copyWith(
        stats: results[0] as Map<String, dynamic>,
        alerts: results[1] as List<AlertItem>,
        thresholds: results[2] as Map<String, dynamic>,
        isLoading: false,
      );
    } catch (e) {
      state = state.copyWith(isLoading: false, error: e.toString());
    }
  }

  Future<void> updateThresholds(Map<String, dynamic> data) async {
    try {
      final updated = await _api.updateDriverThresholds(data);
      state = state.copyWith(thresholds: updated);
    } catch (e) {
      state = state.copyWith(error: 'Failed to update thresholds');
    }
  }
}

final driverDataProvider =
    StateNotifierProvider<DriverDataNotifier, DriverDataState>((ref) {
  final api = ref.watch(apiServiceProvider);
  return DriverDataNotifier(api);
});
