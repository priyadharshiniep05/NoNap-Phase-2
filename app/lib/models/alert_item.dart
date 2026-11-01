import '../core/ist.dart';

/// One alert from DB2, from REST (AlertLogResponse) or a WebSocket alert_event.
class AlertItem {
  final String id;
  final String driverId;
  final String? driverName;
  final String? fleetId;
  final String type; // drowsy, yawning, accident, no_face
  final String severity; // low, medium, high, critical
  final int? level; // 1-3 for level-based alerts; null for legacy / SOS rows
  final String? status; // active, acknowledged, unacknowledged, resolved
  final String? reason; // eyes_closed, yawn, repeated_l1
  final double confidence;
  final double ear;
  final double mar;
  final double perclos;
  final String source; // pi, webcam, simulated
  final String? deviceId;
  final DateTime detectedAt; // UTC instant
  final bool acknowledged;
  final String? acknowledgedBy;
  final DateTime? acknowledgedAt;
  final double? responseTimeMs;
  final DateTime? escalatedAt;

  const AlertItem({
    required this.id,
    required this.driverId,
    this.driverName,
    this.fleetId,
    required this.type,
    required this.severity,
    this.level,
    this.status,
    this.reason,
    this.confidence = 0,
    this.ear = 0,
    this.mar = 0,
    this.perclos = 0,
    this.source = 'pi',
    this.deviceId,
    required this.detectedAt,
    this.acknowledged = false,
    this.acknowledgedBy,
    this.acknowledgedAt,
    this.responseTimeMs,
    this.escalatedAt,
  });

  factory AlertItem.fromJson(Map<String, dynamic> json) {
    double d(String k) => (json[k] as num?)?.toDouble() ?? 0.0;
    return AlertItem(
      id: json['id'] as String,
      driverId: json['driver_id'] as String? ?? '',
      driverName: json['driver_name'] as String?,
      fleetId: json['fleet_id'] as String?,
      type: json['type'] as String? ?? 'drowsy',
      severity: json['severity'] as String? ?? 'medium',
      level: (json['level'] as num?)?.toInt(),
      status: json['status'] as String?,
      reason: json['reason'] as String?,
      confidence: d('confidence'),
      ear: d('ear'),
      mar: d('mar'),
      perclos: d('perclos'),
      source: json['source'] as String? ?? 'pi',
      deviceId: json['device_id'] as String?,
      detectedAt: Ist.parse(json['detected_at'] as String?) ?? DateTime.now().toUtc(),
      acknowledged: json['acknowledged'] as bool? ?? false,
      acknowledgedBy: json['acknowledged_by'] as String?,
      acknowledgedAt: Ist.parse(json['acknowledged_at'] as String?),
      responseTimeMs: (json['response_time_ms'] as num?)?.toDouble(),
      escalatedAt: Ist.parse(json['escalated_at'] as String?),
    );
  }

  /// Level 1-3 (legacy rows are mapped from severity).
  int get effectiveLevel {
    if (level != null) return level!;
    switch (severity) {
      case 'critical':
        return 3;
      case 'high':
        return 2;
      default:
        return 1;
    }
  }

  bool get isOpen => !acknowledged && (status == 'active' || status == 'unacknowledged');
  bool get isUnacknowledgedL3 => effectiveLevel >= 3 && !acknowledged;
  bool get isSimulated => source == 'simulated' || (driverName ?? '').contains('[Simulated]');

  String get displayDriverName => cleanName(driverName ?? 'Driver');

  String get reasonLabel {
    if (type == 'accident') return 'SOS';
    switch (reason) {
      case 'yawn':
        return 'Yawning';
      case 'repeated_l1':
        return 'Repeated drowsiness';
      case 'eyes_closed':
        return 'Eyes closed';
    }
    return type == 'yawning' ? 'Yawning' : 'Drowsy';
  }

  /// "You were drowsy at 14:32 IST · Level 2 · Acknowledged in 3.4 s"
  String get historyLine {
    final what = type == 'yawning' ? 'You were yawning at' : 'You were drowsy at';
    final ack = acknowledged
        ? (responseTimeMs != null ? 'Acknowledged in ${Ist.duration(responseTimeMs)}' : 'Acknowledged')
        : (status == 'resolved' ? 'Cleared' : 'Not acknowledged');
    return '$what ${Ist.hmIst(detectedAt)} · Level $effectiveLevel · $ack';
  }

  AlertItem copyWith({
    int? level,
    String? status,
    bool? acknowledged,
    DateTime? acknowledgedAt,
    double? responseTimeMs,
    DateTime? escalatedAt,
  }) {
    return AlertItem(
      id: id,
      driverId: driverId,
      driverName: driverName,
      fleetId: fleetId,
      type: type,
      severity: severity,
      level: level ?? this.level,
      status: status ?? this.status,
      reason: reason,
      confidence: confidence,
      ear: ear,
      mar: mar,
      perclos: perclos,
      source: source,
      deviceId: deviceId,
      detectedAt: detectedAt,
      acknowledged: acknowledged ?? this.acknowledged,
      acknowledgedBy: acknowledgedBy,
      acknowledgedAt: acknowledgedAt ?? this.acknowledgedAt,
      responseTimeMs: responseTimeMs ?? this.responseTimeMs,
      escalatedAt: escalatedAt ?? this.escalatedAt,
    );
  }
}

/// "Nishant Sharma [Simulated]" -> "Nishant Sharma"
String cleanName(String name) => name.replaceAll('[Simulated]', '').trim();

/// "Priyadarshini Prasanna" -> "PP"
String initialsOf(String name) {
  final parts = cleanName(name).split(RegExp(r'\s+')).where((p) => p.isNotEmpty).toList();
  if (parts.isEmpty) return '?';
  if (parts.length == 1) return parts.first.substring(0, 1).toUpperCase();
  return (parts.first[0] + parts.last[0]).toUpperCase();
}

String firstNameOf(String name) {
  final c = cleanName(name);
  return c.isEmpty ? 'Driver' : c.split(' ').first;
}
