class AlertItem {
  final String id;
  final String driverId;
  final String? driverName;
  final String? fleetId;
  final String type; // drowsy, yawning, accident, no_face
  final String severity; // low, medium, high, critical
  final double confidence;
  final double ear;
  final double mar;
  final double perclos;
  final String source;
  final DateTime detectedAt;
  final bool acknowledged;
  final String? acknowledgedBy;

  AlertItem({
    required this.id,
    required this.driverId,
    this.driverName,
    this.fleetId,
    required this.type,
    required this.severity,
    required this.confidence,
    required this.ear,
    required this.mar,
    required this.perclos,
    required this.source,
    required this.detectedAt,
    required this.acknowledged,
    this.acknowledgedBy,
  });

  factory AlertItem.fromJson(Map<String, dynamic> json) {
    return AlertItem(
      id: json['id'] as String,
      driverId: json['driver_id'] as String,
      driverName: json['driver_name'] as String?,
      fleetId: json['fleet_id'] as String?,
      type: json['type'] as String,
      severity: json['severity'] as String,
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
      ear: (json['ear'] as num?)?.toDouble() ?? 0.0,
      mar: (json['mar'] as num?)?.toDouble() ?? 0.0,
      perclos: (json['perclos'] as num?)?.toDouble() ?? 0.0,
      source: json['source'] as String? ?? 'webcam',
      detectedAt: DateTime.tryParse(json['detected_at'] as String? ?? '') ?? DateTime.now(),
      acknowledged: json['acknowledged'] as bool? ?? false,
      acknowledgedBy: json['acknowledged_by'] as String?,
    );
  }
}
