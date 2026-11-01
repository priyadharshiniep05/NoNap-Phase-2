import '../core/ist.dart';

/// Pi camera status from heartbeats (`device_status` WS message or REST).
class DeviceStatus {
  final String deviceId;
  final String? driverId;
  final String? vehicle;
  final bool online;
  final String? ip;
  final String? cameraBackend;
  final double? fps;
  final double? cpuTempC;
  final double? uptimeS;
  final double? rttMs;
  final DateTime? lastSeenAt;

  const DeviceStatus({
    required this.deviceId,
    this.driverId,
    this.vehicle,
    required this.online,
    this.ip,
    this.cameraBackend,
    this.fps,
    this.cpuTempC,
    this.uptimeS,
    this.rttMs,
    this.lastSeenAt,
  });

  factory DeviceStatus.fromJson(Map<String, dynamic> j) => DeviceStatus(
        deviceId: j['device_id'] as String? ?? '',
        driverId: j['driver_id'] as String?,
        vehicle: j['vehicle'] as String?,
        online: j['online'] as bool? ?? false,
        ip: j['ip'] as String?,
        cameraBackend: j['camera_backend'] as String?,
        fps: (j['fps'] as num?)?.toDouble(),
        cpuTempC: (j['cpu_temp_c'] as num?)?.toDouble(),
        uptimeS: (j['uptime_s'] as num?)?.toDouble(),
        rttMs: (j['rtt_ms'] as num?)?.toDouble(),
        lastSeenAt: Ist.parse(j['last_seen_at'] as String?),
      );
}
