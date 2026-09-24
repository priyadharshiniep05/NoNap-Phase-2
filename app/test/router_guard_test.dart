import 'package:flutter_test/flutter_test.dart';
import 'package:app/models/user.dart';

void main() {
  group('Role Guard Logic Tests', () {
    String? computeRedirect({
      required bool isAuthenticated,
      required User? user,
      required String matchedLocation,
    }) {
      final isAuthRoute = matchedLocation == '/login' || matchedLocation == '/signup';
      if (!isAuthenticated) {
        return isAuthRoute ? null : '/login';
      }

      final isDriver = user?.isDriver ?? false;
      final isFleetManager = user?.isFleetManager ?? false;

      if (isAuthRoute) {
        return isDriver ? '/driver' : '/fleet';
      }

      // Driver attempting to access Fleet routes -> block and redirect to /driver
      if (isDriver && matchedLocation.startsWith('/fleet')) {
        return '/driver';
      }

      // Fleet Manager attempting to access Driver routes -> block and redirect to /fleet
      if (isFleetManager && matchedLocation.startsWith('/driver')) {
        return '/fleet';
      }

      return null;
    }

    test('Unauthenticated user is redirected to /login when visiting /driver', () {
      final redirect = computeRedirect(
        isAuthenticated: false,
        user: null,
        matchedLocation: '/driver',
      );
      expect(redirect, '/login');
    });

    test('Unauthenticated user is redirected to /login when visiting /fleet', () {
      final redirect = computeRedirect(
        isAuthenticated: false,
        user: null,
        matchedLocation: '/fleet',
      );
      expect(redirect, '/login');
    });

    test('Unauthenticated user is allowed to access /login and /signup', () {
      expect(
        computeRedirect(isAuthenticated: false, user: null, matchedLocation: '/login'),
        isNull,
      );
      expect(
        computeRedirect(isAuthenticated: false, user: null, matchedLocation: '/signup'),
        isNull,
      );
    });

    test('Driver is redirected away from /fleet to /driver', () {
      final driver = User(
        id: 'd1',
        fullName: 'Test Driver',
        email: 'driver@test.com',
        role: 'driver',
      );
      final redirect = computeRedirect(
        isAuthenticated: true,
        user: driver,
        matchedLocation: '/fleet/dashboard',
      );
      expect(redirect, '/driver');
    });

    test('Fleet manager is redirected away from /driver to /fleet', () {
      final manager = User(
        id: 'm1',
        fullName: 'Test Manager',
        email: 'manager@test.com',
        role: 'fleet_manager',
      );
      final redirect = computeRedirect(
        isAuthenticated: true,
        user: manager,
        matchedLocation: '/driver/history',
      );
      expect(redirect, '/fleet');
    });

    test('Logged in driver on /login is redirected to /driver', () {
      final driver = User(
        id: 'd1',
        fullName: 'Test Driver',
        email: 'driver@test.com',
        role: 'driver',
      );
      final redirect = computeRedirect(
        isAuthenticated: true,
        user: driver,
        matchedLocation: '/login',
      );
      expect(redirect, '/driver');
    });

    test('Logged in manager on /login is redirected to /fleet', () {
      final manager = User(
        id: 'm1',
        fullName: 'Test Manager',
        email: 'manager@test.com',
        role: 'fleet_manager',
      );
      final redirect = computeRedirect(
        isAuthenticated: true,
        user: manager,
        matchedLocation: '/login',
      );
      expect(redirect, '/fleet');
    });
  });
}
