/// A live `telemetry` WebSocket message (~2 Hz): EAR/MAR, state, level.
class TelemetryMessage {
  final String type;
  final String driverId;
  final String driverName;
  final String status; // alert, drowsy, yawning, no_face (legacy vocabulary)
  final String state; // awake, drowsy, no_face
  final int level; // severity the driver is currently alerted at, 0-3
  final String? alertId;
  final String severity;
  final double confidence;
  final double ear;
  final double mar;
  final double perclos;
  final double eyesClosedSeconds;
  final double earThreshold;
  final double marThreshold;
  final String timestamp;
  final String timestampIst;
  final String message;
  final String reason;
  final String? frameId;
  final String? deviceId;
  final String? source;
  final String backend;

  const TelemetryMessage({
    required this.type,
    required this.driverId,
    required this.driverName,
    required this.status,
    this.state = 'awake',
    this.level = 0,
    this.alertId,
    required this.severity,
    required this.confidence,
    required this.ear,
    required this.mar,
    required this.perclos,
    required this.eyesClosedSeconds,
    this.earThreshold = 0.21,
    this.marThreshold = 0.60,
    required this.timestamp,
    this.timestampIst = '',
    required this.message,
    this.reason = '',
    this.frameId,
    this.deviceId,
    this.source,
    this.backend = '',
  });

  bool get hasFace => state != 'no_face' && status != 'no_face';

  factory TelemetryMessage.fromJson(Map<String, dynamic> json) {
    final metrics = (json['metrics'] as Map?)?.cast<String, dynamic>() ?? const {};
    double d(String k, [double fallback = 0.0]) =>
        ((json[k] ?? metrics[k]) as num?)?.toDouble() ?? fallback;
    final status = json['status'] as String? ?? 'alert';
    return TelemetryMessage(
      type: json['type'] as String? ?? 'telemetry',
      driverId: json['driver_id'] as String? ?? '',
      driverName: json['driver_name'] as String? ?? '',
      status: status,
      state: json['state'] as String? ??
          (status == 'no_face' ? 'no_face' : (status == 'alert' ? 'awake' : 'drowsy')),
      level: (json['level'] as num?)?.toInt() ?? 0,
      alertId: json['alert_id'] as String?,
      severity: json['severity'] as String? ?? 'low',
      confidence: d('confidence'),
      ear: d('ear'),
      mar: d('mar'),
      perclos: d('perclos'),
      eyesClosedSeconds: d('eyes_closed_seconds'),
      earThreshold: d('ear_threshold', 0.21),
      marThreshold: d('mar_threshold', 0.60),
      timestamp: json['timestamp'] as String? ?? '',
      timestampIst: (json['timestamp_ist'] ?? json['time_ist']) as String? ?? '',
      message: json['message'] as String? ?? '',
      reason: (json['reason'] ?? metrics['reason']) as String? ?? '',
      frameId: json['frame_id'] as String?,
      deviceId: json['device_id'] as String?,
      source: json['source'] as String?,
      backend: metrics['backend'] as String? ?? '',
    );
  }
}
