import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/fleet_overview.dart';
import '../models/alert_item.dart';
import '../services/api_service.dart';
import 'auth_provider.dart';

class FleetDataState {
  final FleetOverview? overview;
  final List<AlertItem> alerts;
  final Map<String, dynamic>? thresholds;
  final bool isLoading;
  final String? error;

  FleetDataState({
    this.overview,
    this.alerts = const [],
    this.thresholds,
    this.isLoading = false,
    this.error,
  });

  FleetDataState copyWith({
    FleetOverview? overview,
    List<AlertItem>? alerts,
    Map<String, dynamic>? thresholds,
    bool? isLoading,
    String? error,
  }) {
    return FleetDataState(
      overview: overview ?? this.overview,
      alerts: alerts ?? this.alerts,
      thresholds: thresholds ?? this.thresholds,
      isLoading: isLoading ?? this.isLoading,
      error: error,
    );
  }
}

class FleetDataNotifier extends StateNotifier<FleetDataState> {
  final ApiService _api;

  FleetDataNotifier(this._api) : super(FleetDataState()) {
    refresh();
  }

  Future<void> refresh() async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final overviewFuture = _api.getFleetOverview();
      final alertsFuture = _api.getFleetAlerts(limit: 50);
      final thresholdsFuture = _api.getFleetThresholds();

      final results = await Future.wait([overviewFuture, alertsFuture, thresholdsFuture]);

      state = state.copyWith(
        overview: results[0] as FleetOverview,
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
      final updated = await _api.updateFleetThresholds(data);
      state = state.copyWith(thresholds: updated);
    } catch (e) {
      state = state.copyWith(error: 'Failed to update fleet thresholds');
    }
  }
}

final fleetDataProvider =
    StateNotifierProvider<FleetDataNotifier, FleetDataState>((ref) {
  final api = ref.watch(apiServiceProvider);
  return FleetDataNotifier(api);
});
