import 'alert_item.dart';

class FleetDriverItem {
  final String driverId;
  final String fullName;
  final String email;
  final bool isActive;
  final String currentStatus; // alert, drowsy, yawning, no_face, offline
  final DateTime? lastAlertAt;
  final int alertsToday;
  final double perclos;
  final double ear;
  final bool online;
  final String? deviceId;
  final bool deviceOnline;
  final String? vehicle;
  final double? fps;
  final double? cpuTempC;
  final AlertItem? activeAlert;
  final double? avgResponseMs;

  const FleetDriverItem({
    required this.driverId,
    required this.fullName,
    required this.email,
    this.isActive = true,
    this.currentStatus = 'offline',
    this.lastAlertAt,
    this.alertsToday = 0,
    this.perclos = 0,
    this.ear = 0,
    this.online = false,
    this.deviceId,
    this.deviceOnline = false,
    this.vehicle,
    this.fps,
    this.cpuTempC,
    this.activeAlert,
    this.avgResponseMs,
  });

  factory FleetDriverItem.fromJson(Map<String, dynamic> json) {
    final active = json['active_alert'] as Map<String, dynamic>?;
    return FleetDriverItem(
      driverId: json['driver_id'] as String,
      fullName: json['full_name'] as String,
      email: json['email'] as String? ?? '',
      isActive: json['is_active'] as bool? ?? true,
      currentStatus: json['current_status'] as String? ?? 'offline',
      lastAlertAt: _parse(json['last_alert_at']),
      alertsToday: (json['alerts_today'] as num?)?.toInt() ?? 0,
      perclos: (json['perclos'] as num?)?.toDouble() ?? 0.0,
      ear: (json['ear'] as num?)?.toDouble() ?? 0.0,
      online: json['online'] as bool? ?? false,
      deviceId: json['device_id'] as String?,
      deviceOnline: json['device_online'] as bool? ?? false,
      vehicle: json['vehicle'] as String?,
      fps: (json['fps'] as num?)?.toDouble(),
      cpuTempC: (json['cpu_temp_c'] as num?)?.toDouble(),
      activeAlert: active != null ? AlertItem.fromJson(active) : null,
      avgResponseMs: (json['avg_response_ms'] as num?)?.toDouble(),
    );
  }

  static DateTime? _parse(Object? v) {
    if (v is! String) return null;
    final hasZone = RegExp(r'(Z|[+-]\d{2}:?\d{2})$').hasMatch(v);
    return DateTime.tryParse(hasZone ? v : '$v+05:30')?.toUtc();
  }

  FleetDriverItem copyWith({
    String? currentStatus,
    DateTime? lastAlertAt,
    int? alertsToday,
    double? perclos,
    double? ear,
    bool? online,
    String? deviceId,
    bool? deviceOnline,
    String? vehicle,
    double? fps,
    double? cpuTempC,
    AlertItem? activeAlert,
    bool clearActiveAlert = false,
    double? avgResponseMs,
  }) {
    return FleetDriverItem(
      driverId: driverId,
      fullName: fullName,
      email: email,
      isActive: isActive,
      currentStatus: currentStatus ?? this.currentStatus,
      lastAlertAt: lastAlertAt ?? this.lastAlertAt,
      alertsToday: alertsToday ?? this.alertsToday,
      perclos: perclos ?? this.perclos,
      ear: ear ?? this.ear,
      online: online ?? this.online,
      deviceId: deviceId ?? this.deviceId,
      deviceOnline: deviceOnline ?? this.deviceOnline,
      vehicle: vehicle ?? this.vehicle,
      fps: fps ?? this.fps,
      cpuTempC: cpuTempC ?? this.cpuTempC,
      activeAlert: clearActiveAlert ? null : (activeAlert ?? this.activeAlert),
      avgResponseMs: avgResponseMs ?? this.avgResponseMs,
    );
  }

  bool get isSimulated => fullName.contains('[Simulated]') || email.contains('simulated');
  String get displayName => cleanName(fullName);
  bool get inActiveAlert => activeAlert != null && !activeAlert!.acknowledged;
}

class FleetOverview {
  final String fleetId;
  final String fleetName;
  final int totalDrivers;
  final int driversOnline;
  final int activeAlerts;
  final int alertsToday;
  final double? avgResponseMsToday;
  final List<FleetDriverItem> drivers;

  const FleetOverview({
    required this.fleetId,
    required this.fleetName,
    required this.totalDrivers,
    this.driversOnline = 0,
    this.activeAlerts = 0,
    this.alertsToday = 0,
    this.avgResponseMsToday,
    required this.drivers,
  });

  factory FleetOverview.fromJson(Map<String, dynamic> json) {
    final drivers = (json['drivers'] as List<dynamic>? ?? [])
        .map((d) => FleetDriverItem.fromJson(d as Map<String, dynamic>))
        .toList();
    return FleetOverview(
      fleetId: json['fleet_id'] as String,
      fleetName: json['fleet_name'] as String,
      totalDrivers: (json['total_drivers'] as num?)?.toInt() ?? drivers.length,
      driversOnline: (json['drivers_online'] as num?)?.toInt() ?? 0,
      activeAlerts: (json['active_alerts'] as num?)?.toInt() ?? 0,
      alertsToday: (json['alerts_today'] as num?)?.toInt() ?? 0,
      avgResponseMsToday: (json['avg_response_ms_today'] as num?)?.toDouble(),
      drivers: drivers,
    );
  }

  /// Recompute the summary tiles from the driver list after a live update.
  FleetOverview withDrivers(List<FleetDriverItem> drivers, {int? alertsToday, double? avgResponseMsToday}) {
    return FleetOverview(
      fleetId: fleetId,
      fleetName: fleetName,
      totalDrivers: drivers.length,
      driversOnline: drivers.where((d) => d.online).length,
      activeAlerts: drivers.where((d) => d.inActiveAlert).length,
      alertsToday: alertsToday ?? this.alertsToday,
      avgResponseMsToday: avgResponseMsToday ?? this.avgResponseMsToday,
      drivers: drivers,
    );
  }
}
