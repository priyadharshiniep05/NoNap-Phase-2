import '../core/ist.dart';

/// A driving session (Start Driving -> End Session).
class SessionInfo {
  final bool active;
  final String? id;
  final DateTime? startedAt;
  final int drivingSeconds;
  final int alerts;
  final double? avgAckMs;

  const SessionInfo({
    this.active = false,
    this.id,
    this.startedAt,
    this.drivingSeconds = 0,
    this.alerts = 0,
    this.avgAckMs,
  });

  factory SessionInfo.fromJson(Map<String, dynamic> j) => SessionInfo(
        active: j['active'] as bool? ?? false,
        id: j['id'] as String?,
        startedAt: Ist.parse(j['started_at'] as String?),
        drivingSeconds: (j['driving_seconds'] as num?)?.toInt() ?? 0,
        alerts: (j['alerts'] as num?)?.toInt() ?? 0,
        avgAckMs: (j['avg_ack_ms'] as num?)?.toDouble(),
      );
}
