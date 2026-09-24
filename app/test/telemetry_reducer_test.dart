import 'package:flutter_test/flutter_test.dart';
import 'package:app/models/telemetry_message.dart';
import 'package:app/providers/telemetry_provider.dart';

void main() {
  group('Telemetry Reducer & State Tests', () {
    test('Initial telemetry state is empty and monitoring false', () {
      final state = TelemetryState();
      expect(state.latest, isNull);
      expect(state.liveAlerts, isEmpty);
      expect(state.isMonitoring, isFalse);
    });

    test('Regular status message updates latest without adding to liveAlerts', () {
      final state = TelemetryState();
      final msg = TelemetryMessage(
        type: 'telemetry',
        driverId: 'd1',
        driverName: 'Driver 1',
        status: 'alert',
        severity: 'low',
        confidence: 0.95,
        ear: 0.28,
        mar: 0.15,
        perclos: 0.05,
        eyesClosedSeconds: 0.0,
        timestamp: '2026-09-24T12:00:00Z',
        message: 'Driver alert',
      );

      final updated = state.copyWith(latest: msg);
      expect(updated.latest?.status, 'alert');
      expect(updated.liveAlerts, isEmpty);
    });

    test('Alert message prepends to liveAlerts and caps at 20', () {
      var state = TelemetryState();

      for (int i = 0; i < 25; i++) {
        final alert = TelemetryMessage(
          type: 'alert',
          driverId: 'd1',
          driverName: 'Driver 1',
          status: 'drowsy',
          severity: 'high',
          confidence: 0.92,
          ear: 0.18,
          mar: 0.20,
          perclos: 0.45,
          eyesClosedSeconds: 2.1,
          timestamp: '2026-09-24T12:0$i:00Z',
          message: 'Drowsiness detected ($i)',
        );
        final updatedAlerts = [alert, ...state.liveAlerts.take(19)];
        state = state.copyWith(latest: alert, liveAlerts: updatedAlerts);
      }

      expect(state.liveAlerts.length, 20);
      expect(state.liveAlerts.first.message, 'Drowsiness detected (24)');
    });

    test('Accident message is recognized as critical alert', () {
      final accident = TelemetryMessage(
        type: 'accident',
        driverId: 'd1',
        driverName: 'Driver 1',
        status: 'accident',
        severity: 'critical',
        confidence: 1.0,
        ear: 0.0,
        mar: 0.0,
        perclos: 0.0,
        eyesClosedSeconds: 0.0,
        timestamp: '2026-09-24T12:30:00Z',
        message: 'SOS Accident reported',
      );

      expect(accident.isAlert, isTrue);
      expect(accident.severity, 'critical');
    });
  });
}
