import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../providers/auth_provider.dart';
import '../screens/auth/login_screen.dart';
import '../screens/auth/signup_screen.dart';
import '../screens/driver/driver_dashboard_screen.dart';
import '../screens/driver/driver_history_screen.dart';
import '../screens/driver/driver_settings_screen.dart';
import '../screens/fleet/fleet_dashboard_screen.dart';
import '../screens/fleet/fleet_driver_detail_screen.dart';
import '../screens/fleet/fleet_settings_screen.dart';

final routerProvider = Provider<GoRouter>((ref) {
  return GoRouter(
    initialLocation: '/login',
    refreshListenable: GoRouterRefreshStream(ref.watch(authProvider.notifier)),
    redirect: (context, state) {
      final authState = ref.read(authProvider);
      final isLoggedIn = authState.isAuthenticated;
      final isAuthRoute = state.matchedLocation == '/login' || state.matchedLocation == '/signup';

      if (!isLoggedIn) {
        return isAuthRoute ? null : '/login';
      }

      // STRICT ROLE SEPARATION GUARDS
      final isDriver = authState.isDriver;
      final isFleetManager = authState.isFleetManager;

      if (isAuthRoute) {
        return isDriver ? '/driver' : '/fleet';
      }

      // Driver attempting to access Fleet routes -> block and redirect to /driver
      if (isDriver && state.matchedLocation.startsWith('/fleet')) {
        return '/driver';
      }

      // Fleet Manager attempting to access Driver routes -> block and redirect to /fleet
      if (isFleetManager && state.matchedLocation.startsWith('/driver')) {
        return '/fleet';
      }

      return null;
    },
    routes: [
      GoRoute(
        path: '/login',
        builder: (context, state) => const LoginScreen(),
      ),
      GoRoute(
        path: '/signup',
        builder: (context, state) => const SignupScreen(),
      ),
      // Driver Routes
      GoRoute(
        path: '/driver',
        builder: (context, state) => const DriverDashboardScreen(),
        routes: [
          GoRoute(
            path: 'history',
            builder: (context, state) => const DriverHistoryScreen(),
          ),
          GoRoute(
            path: 'settings',
            builder: (context, state) => const DriverSettingsScreen(),
          ),
        ],
      ),
      // Fleet Manager Routes
      GoRoute(
        path: '/fleet',
        builder: (context, state) => const FleetDashboardScreen(),
        routes: [
          GoRoute(
            path: 'driver/:driverId',
            builder: (context, state) {
              final driverId = state.pathParameters['driverId'] ?? '';
              return FleetDriverDetailScreen(driverId: driverId);
            },
          ),
          GoRoute(
            path: 'settings',
            builder: (context, state) => const FleetSettingsScreen(),
          ),
        ],
      ),
    ],
  );
});

class GoRouterRefreshStream extends ChangeNotifier {
  GoRouterRefreshStream(StateNotifier notifier) {
    notifier.addListener((_) {
      notifyListeners();
    });
  }
}
