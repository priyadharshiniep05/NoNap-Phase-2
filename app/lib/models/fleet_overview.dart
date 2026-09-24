class FleetDriverItem {
  final String driverId;
  final String fullName;
  final String email;
  final bool isActive;
  final String currentStatus; // alert, drowsy, yawning, offline, no_face
  final DateTime? lastAlertAt;
  final int alertsToday;
  final double perclos;
  final double ear;

  FleetDriverItem({
    required this.driverId,
    required this.fullName,
    required this.email,
    required this.isActive,
    required this.currentStatus,
    this.lastAlertAt,
    required this.alertsToday,
    required this.perclos,
    required this.ear,
  });

  factory FleetDriverItem.fromJson(Map<String, dynamic> json) {
    return FleetDriverItem(
      driverId: json['driver_id'] as String,
      fullName: json['full_name'] as String,
      email: json['email'] as String,
      isActive: json['is_active'] as bool? ?? true,
      currentStatus: json['current_status'] as String? ?? 'alert',
      lastAlertAt: json['last_alert_at'] != null ? DateTime.tryParse(json['last_alert_at'] as String) : null,
      alertsToday: json['alerts_today'] as int? ?? 0,
      perclos: (json['perclos'] as num?)?.toDouble() ?? 0.0,
      ear: (json['ear'] as num?)?.toDouble() ?? 0.0,
    );
  }
}

class FleetOverview {
  final String fleetId;
  final String fleetName;
  final int totalDrivers;
  final int activeDrivers;
  final int drowsyCountToday;
  final int yawnCountToday;
  final int criticalAlertsToday;
  final List<FleetDriverItem> drivers;

  FleetOverview({
    required this.fleetId,
    required this.fleetName,
    required this.totalDrivers,
    required this.activeDrivers,
    required this.drowsyCountToday,
    required this.yawnCountToday,
    required this.criticalAlertsToday,
    required this.drivers,
  });

  factory FleetOverview.fromJson(Map<String, dynamic> json) {
    final driverList = (json['drivers'] as List<dynamic>?)
            ?.map((d) => FleetDriverItem.fromJson(d as Map<String, dynamic>))
            .toList() ??
        [];
    return FleetOverview(
      fleetId: json['fleet_id'] as String,
      fleetName: json['fleet_name'] as String,
      totalDrivers: json['total_drivers'] as int? ?? 0,
      activeDrivers: json['active_drivers'] as int? ?? 0,
      drowsyCountToday: json['drowsy_count_today'] as int? ?? 0,
      yawnCountToday: json['yawn_count_today'] as int? ?? 0,
      criticalAlertsToday: json['critical_alerts_today'] as int? ?? 0,
      drivers: driverList,
    );
  }
}
