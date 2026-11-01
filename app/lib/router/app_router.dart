import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../providers/auth_provider.dart';
import '../screens/auth/login_screen.dart';
import '../screens/auth/signup_screen.dart';
import '../screens/driver/calibration_screen.dart';
import '../screens/driver/driver_dashboard_screen.dart';
import '../screens/driver/driver_history_screen.dart';
import '../screens/driver/driver_settings_screen.dart';
import '../screens/driver/driver_shell.dart';
import '../screens/fleet/fleet_dashboard_screen.dart';
import '../screens/fleet/fleet_driver_detail_screen.dart';
import '../screens/fleet/fleet_settings_screen.dart';
import '../screens/splash_screen.dart';
import '../theme/tokens.dart';

/// Role guard (pure, unit-tested). Drivers never reach /fleet, managers never reach /driver.
String? roleRedirect({
  required bool booting,
  required bool isAuthenticated,
  required bool isDriver,
  required bool isFleetManager,
  required String location,
}) {
  if (booting) return location == '/splash' ? null : '/splash';
  final isAuthRoute = location == '/login' || location == '/signup';
  if (!isAuthenticated) return isAuthRoute ? null : '/login';
  if (isAuthRoute || location == '/splash') return isDriver ? '/driver' : '/fleet';
  if (isDriver && location.startsWith('/fleet')) return '/driver';
  if (isFleetManager && location.startsWith('/driver')) return '/fleet';
  return null;
}

CustomTransitionPage<void> _fade(GoRouterState state, Widget child) {
  return CustomTransitionPage(
    key: state.pageKey,
    child: child,
    transitionDuration: AppMotion.medium,
    transitionsBuilder: (context, animation, _, child) {
      if (AppMotion.reduced(context)) return child;
      final curved = CurvedAnimation(parent: animation, curve: AppMotion.curve);
      return FadeTransition(
        opacity: curved,
        child: SlideTransition(
          position: Tween(begin: const Offset(0, 0.02), end: Offset.zero).animate(curved),
          child: child,
        ),
      );
    },
  );
}

final routerProvider = Provider<GoRouter>((ref) {
  return GoRouter(
    initialLocation: '/splash',
    refreshListenable: GoRouterRefreshStream(ref.watch(authProvider.notifier)),
    redirect: (context, state) {
      final auth = ref.read(authProvider);
      return roleRedirect(
        booting: auth.booting,
        isAuthenticated: auth.isAuthenticated,
        isDriver: auth.isDriver,
        isFleetManager: auth.isFleetManager,
        location: state.matchedLocation,
      );
    },
    routes: [
      GoRoute(path: '/splash', pageBuilder: (c, s) => _fade(s, const SplashScreen())),
      GoRoute(path: '/login', pageBuilder: (c, s) => _fade(s, const LoginScreen())),
      GoRoute(path: '/signup', builder: (c, s) => const SignupScreen()),
      // Driver: every screen sits inside the shell that owns the full-screen alert.
      ShellRoute(
        builder: (context, state, child) => DriverShell(child: child),
        routes: [
          GoRoute(
            path: '/driver',
            pageBuilder: (c, s) => _fade(s, const DriverDashboardScreen()),
            routes: [
              GoRoute(path: 'history', builder: (c, s) => const DriverHistoryScreen()),
              GoRoute(path: 'settings', builder: (c, s) => const DriverSettingsScreen()),
              GoRoute(path: 'calibration', builder: (c, s) => const CalibrationScreen()),
            ],
          ),
        ],
      ),
      // Fleet manager
      GoRoute(
        path: '/fleet',
        pageBuilder: (c, s) => _fade(s, const FleetDashboardScreen()),
        routes: [
          GoRoute(
            path: 'driver/:driverId',
            builder: (c, s) => FleetDriverDetailScreen(driverId: s.pathParameters['driverId'] ?? ''),
          ),
          GoRoute(path: 'settings', builder: (c, s) => const FleetSettingsScreen()),
        ],
      ),
    ],
  );
});

class GoRouterRefreshStream extends ChangeNotifier {
  GoRouterRefreshStream(StateNotifier notifier) {
    notifier.addListener((_) => notifyListeners());
  }
}
