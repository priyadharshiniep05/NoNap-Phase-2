import 'package:app/router/app_router.dart';
import 'package:flutter_test/flutter_test.dart';

String? go(String loc, {bool booting = false, bool auth = true, String role = 'driver'}) => roleRedirect(
      booting: booting,
      isAuthenticated: auth,
      isDriver: auth && role == 'driver',
      isFleetManager: auth && role == 'fleet_manager',
      location: loc,
    );

void main() {
  group('Role guard', () {
    test('splash while the saved session is being checked', () {
      expect(go('/driver', booting: true), '/splash');
      expect(go('/splash', booting: true), isNull);
    });

    test('signed-out users only reach login and signup', () {
      expect(go('/driver', auth: false), '/login');
      expect(go('/fleet', auth: false), '/login');
      expect(go('/driver/history', auth: false), '/login');
      expect(go('/login', auth: false), isNull);
      expect(go('/signup', auth: false), isNull);
    });

    test('drivers can never open fleet screens', () {
      expect(go('/fleet'), '/driver');
      expect(go('/fleet/driver/abc'), '/driver');
      expect(go('/fleet/settings'), '/driver');
      expect(go('/driver/history'), isNull);
      expect(go('/driver/calibration'), isNull);
    });

    test('fleet managers can never open driver screens', () {
      expect(go('/driver', role: 'fleet_manager'), '/fleet');
      expect(go('/driver/settings', role: 'fleet_manager'), '/fleet');
      expect(go('/fleet/driver/abc', role: 'fleet_manager'), isNull);
    });

    test('signed-in users leave auth screens for their own home', () {
      expect(go('/login'), '/driver');
      expect(go('/splash'), '/driver');
      expect(go('/login', role: 'fleet_manager'), '/fleet');
    });
  });
}
