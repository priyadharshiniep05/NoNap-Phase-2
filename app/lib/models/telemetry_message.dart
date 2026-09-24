class TelemetryMessage {
  final String type; // connection_ack, telemetry, alert, ping, pong
  final String driverId;
  final String driverName;
  final String status; // alert, drowsy, yawning, accident, no_face
  final String severity; // low, medium, high, critical
  final double confidence;
  final double ear;
  final double mar;
  final double perclos;
  final double eyesClosedSeconds;
  final String timestamp;
  final String message;

  TelemetryMessage({
    required this.type,
    required this.driverId,
    required this.driverName,
    required this.status,
    required this.severity,
    required this.confidence,
    required this.ear,
    required this.mar,
    required this.perclos,
    required this.eyesClosedSeconds,
    required this.timestamp,
    required this.message,
  });

  bool get isAlert => type == 'alert' || status == 'drowsy' || status == 'accident';

  factory TelemetryMessage.fromJson(Map<String, dynamic> json) {
    final metrics = (json['metrics'] as Map<String, dynamic>?) ?? {};
    return TelemetryMessage(
      type: json['type'] as String? ?? 'telemetry',
      driverId: json['driver_id'] as String? ?? '',
      driverName: json['driver_name'] as String? ?? '',
      status: json['status'] as String? ?? 'alert',
      severity: json['severity'] as String? ?? 'low',
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
      ear: (metrics['ear'] as num?)?.toDouble() ?? 0.0,
      mar: (metrics['mar'] as num?)?.toDouble() ?? 0.0,
      perclos: (metrics['perclos'] as num?)?.toDouble() ?? 0.0,
      eyesClosedSeconds: (metrics['eyes_closed_seconds'] as num?)?.toDouble() ?? 0.0,
      timestamp: json['timestamp'] as String? ?? '',
      message: json['message'] as String? ?? '',
    );
  }
}
