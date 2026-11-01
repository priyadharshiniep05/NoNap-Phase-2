import 'package:app/core/ist.dart';
import 'package:app/models/alert_item.dart';
import 'package:app/models/fleet_overview.dart';
import 'package:app/models/telemetry_message.dart';
import 'package:app/providers/driver_live_provider.dart';
import 'package:app/providers/driver_provider.dart';
import 'package:app/providers/fleet_provider.dart';
import 'package:app/screens/driver/driver_history_screen.dart';
import 'package:app/widgets/status_ring.dart';
import 'package:flutter_test/flutter_test.dart';

AlertItem alert(String id, {String driver = 'd1', int level = 1, String detected = '2026-10-21T14:32:00+05:30',
    bool acked = false, double? ms, String status = 'active'}) {
  return AlertItem.fromJson({
    'id': id,
    'driver_id': driver,
    'driver_name': 'Priyadarshini Prasanna',
    'type': 'drowsy',
    'severity': 'high',
    'level': level,
    'status': status,
    'reason': 'eyes_closed',
    'detected_at': detected,
    'acknowledged': acked,
    'response_time_ms': ms,
    'source': 'pi',
  });
}

void main() {
  group('IST', () {
    test('formats any instant in IST regardless of phone time zone', () {
      final t = DateTime.utc(2026, 10, 21, 9, 2); // 14:32 IST
      expect(Ist.hm(t), '14:32');
      expect(Ist.hmIst(t), '14:32 IST');
      expect(Ist.hour(t), 14);
    });

    test('server values without offset are IST wall-clock', () {
      expect(Ist.parse('2026-10-21T14:32:00')!.toUtc(), DateTime.utc(2026, 10, 21, 9, 2));
      expect(Ist.parse('2026-10-21T14:32:00+05:30')!.toUtc(), DateTime.utc(2026, 10, 21, 9, 2));
      expect(Ist.parse(null), isNull);
    });

    test('durations read naturally', () {
      expect(Ist.duration(3400), '3.4 s');
      expect(Ist.duration(850), '850 ms');
      expect(Ist.duration(null), '—');
    });
  });

  group('AlertItem', () {
    test('history line matches the spec wording', () {
      final a = alert('a', level: 2, acked: true, ms: 3400, status: 'acknowledged');
      expect(a.historyLine, 'You were drowsy at 14:32 IST · Level 2 · Acknowledged in 3.4 s');
    });

    test('legacy rows get a level from severity', () {
      final a = AlertItem.fromJson({'id': 'x', 'driver_id': 'd', 'type': 'drowsy', 'severity': 'critical', 'detected_at': '2026-10-21T10:00:00'});
      expect(a.effectiveLevel, 3);
    });

    test('names and initials drop the [Simulated] tag', () {
      expect(cleanName('Nishant Sharma [Simulated]'), 'Nishant Sharma');
      expect(initialsOf('Priyadarshini Prasanna'), 'PP');
      expect(firstNameOf('Namrata Rao [Simulated]'), 'Namrata');
    });
  });

  group('Live data reducers', () {
    test('sparkline keeps only the last 60 s', () {
      var s = <SeriesPoint>[];
      for (var t = 0; t <= 90000; t += 500) {
        s = appendWindowed(s, SeriesPoint(t, 0.3));
      }
      expect(s.first.t, 30000);
      expect(s.last.t, 90000);
    });

    test('upsert replaces by id and keeps newest first', () {
      var list = [alert('a', detected: '2026-10-21T10:00:00+05:30')];
      list = upsertAlert(list, alert('b', detected: '2026-10-21T11:00:00+05:30'));
      list = upsertAlert(list, alert('a', detected: '2026-10-21T10:00:00+05:30', level: 3));
      expect(list.map((a) => a.id), ['b', 'a']);
      expect(list.last.level, 3);
    });

    test('telemetry message derives state and level', () {
      final t = TelemetryMessage.fromJson({
        'type': 'telemetry',
        'driver_id': 'd1',
        'status': 'drowsy',
        'state': 'drowsy',
        'level': 2,
        'metrics': {'ear': 0.12, 'mar': 0.2, 'ear_threshold': 0.22},
        'frame_id': 'pi-1',
      });
      expect(t.level, 2);
      expect(t.ear, 0.12);
      expect(t.earThreshold, 0.22);
      expect(t.hasFace, isTrue);
      expect(t.frameId, 'pi-1');
    });

    test('risk colour input rises with level', () {
      expect(riskOf(level: 0, eyesClosedSeconds: 0), 0);
      expect(riskOf(level: 0, eyesClosedSeconds: 0.5), closeTo(0.25, 1e-9));
      expect(riskOf(level: 1, eyesClosedSeconds: 0), 0.7);
      expect(riskOf(level: 3, eyesClosedSeconds: 0), 1.0);
    });
  });

  group('History grouping', () {
    test('alerts by IST hour', () {
      final counts = alertsByHour([
        alert('a', detected: '2026-10-21T14:32:00+05:30'),
        alert('b', detected: '2026-10-21T09:05:00Z'), // 14:35 IST
        alert('c', detected: '2026-10-21T02:00:00+05:30'),
      ]);
      expect(counts[14], 2);
      expect(counts[2], 1);
      expect(counts.reduce((a, b) => a + b), 3);
    });
  });

  group('Fleet live updates', () {
    FleetDataState base() => FleetDataState(
          overview: FleetOverview(fleetId: 'f', fleetName: 'Apex', totalDrivers: 2, drivers: const [
            FleetDriverItem(driverId: 'd1', fullName: 'Priyadarshini Prasanna', email: 'p@x', online: true),
            FleetDriverItem(driverId: 'd2', fullName: 'Nishant Sharma [Simulated]', email: 'n@x'),
          ]),
        );

    test('raised alert moves the driver to the top and counts today', () {
      final s = applyFleetAlertEvent(base(), 'raised', alert('x', driver: 'd2', level: 2));
      expect(s.sortedDrivers.first.driverId, 'd2');
      expect(s.overview!.activeAlerts, 1);
      expect(s.overview!.alertsToday, 1);
      expect(s.alerts.first.id, 'x');
      expect(s.freshIds, contains('x'));
    });

    test('escalation keeps one row and shows level 3', () {
      var s = applyFleetAlertEvent(base(), 'raised', alert('x', level: 2));
      s = applyFleetAlertEvent(s, 'escalated', alert('x', level: 3, status: 'unacknowledged'));
      expect(s.alerts.length, 1);
      expect(s.overview!.drivers.firstWhere((d) => d.driverId == 'd1').activeAlert!.effectiveLevel, 3);
      expect(s.overview!.alertsToday, 1);
    });

    test('acknowledgement clears the active alert', () {
      var s = applyFleetAlertEvent(base(), 'raised', alert('x', level: 2));
      s = applyFleetAlertEvent(s, 'acknowledged', alert('x', level: 2, acked: true, ms: 2500, status: 'acknowledged'));
      expect(s.overview!.activeAlerts, 0);
      expect(s.overview!.drivers.first.inActiveAlert, isFalse);
    });
  });
}
