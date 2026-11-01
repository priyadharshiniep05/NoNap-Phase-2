// UI tour on a simulator against scripts/e2e_alert_flow.py --serve.
//
//   server/.venv/bin/python scripts/e2e_alert_flow.py --serve        (repo root)
//   cd app && flutter drive --driver=test_driver/integration_test.dart \
//       --target=integration_test/ui_tour_test.dart -d <simulator> \
//       --dart-define=API_BASE_URL=http://127.0.0.1:8100
//
// Walks login -> driving -> level 1 -> level 2 -> level 3 -> "I'm awake"
// -> history -> fleet dashboard, saving a screenshot at each step.
import 'dart:io';

import 'package:app/main.dart' as app;
import 'package:app/widgets/ui.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

const base = String.fromEnvironment('API_BASE_URL', defaultValue: 'http://127.0.0.1:8100');

Future<void> eyes(String state) async {
  final c = HttpClient();
  final req = await c.postUrl(Uri.parse('$base/__e2e/eyes/$state'));
  await (await req.close()).drain<void>();
  c.close();
}

void main() {
  final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  binding.framePolicy = LiveTestWidgetsFlutterBindingFramePolicy.fullyLive;

  Future<void> wait(WidgetTester t, int ms) async {
    final end = DateTime.now().add(Duration(milliseconds: ms));
    while (DateTime.now().isBefore(end)) {
      await t.pump(const Duration(milliseconds: 100));
    }
  }

  Future<void> shot(WidgetTester t, String name) async {
    await t.pump(const Duration(milliseconds: 50));
    await binding.takeScreenshot(name);
  }

  Future<void> login(WidgetTester t, String email) async {
    await t.enterText(find.byType(TextField).at(0), email);
    await t.enterText(find.byType(TextField).at(1), 'NoNap@123');
    FocusManager.instance.primaryFocus?.unfocus();
    await wait(t, 400);
    await t.tap(find.widgetWithText(GradientButton, 'Sign in'));
    await wait(t, 3000);
  }

  testWidgets('NoNap UI tour', (t) async {
    await eyes('open');
    await eyes('pi_on');
    GoogleFonts.config.allowRuntimeFetching = false;
    await const FlutterSecureStorage().deleteAll(); // keychain outlives reinstalls
    await t.pumpWidget(const ProviderScope(child: app.NoNapApp()));
    await wait(t, 3000);
    await shot(t, '01_login');

    await login(t, 'driver1@nonap.demo');
    await wait(t, 2500);
    await shot(t, '02_driver_dashboard');

    await t.drag(find.byType(ListView).first, const Offset(0, -2000));
    await wait(t, 500);
    if (find.text('End session').evaluate().isNotEmpty) {
      await t.tap(find.text('End session'));
      await wait(t, 1500);
    }
    await t.tap(find.text('Start driving'));
    await t.drag(find.byType(ListView).first, const Offset(0, 2000));
    await wait(t, 2500);
    await shot(t, '03_driving');

    await eyes('yawn');
    await wait(t, 2200);
    await shot(t, '04_level1_banner');
    await eyes('open');
    await wait(t, 7000); // banner dismisses, episode ends, cooldown passes

    await eyes('closed');
    await wait(t, 3200);
    await shot(t, '05_level2_takeover');
    await eyes('open');
    await wait(t, 11500);
    await shot(t, '06_level3_takeover');

    await t.tap(find.text("I'm awake"));
    await wait(t, 1500);
    await shot(t, '07_stay_safe');
    await t.tap(find.text('Okay'));
    await wait(t, 800);

    await t.drag(find.byType(ListView).first, const Offset(0, -500));
    await wait(t, 800);
    await shot(t, '08_dashboard_scrolled');

    await t.drag(find.byType(ListView).first, const Offset(0, 2000));
    await wait(t, 600);
    await t.tap(find.bySemanticsLabel('Alert history'));
    await wait(t, 2500);
    await shot(t, '09_history');
    await t.pageBack();
    await wait(t, 800);

    await t.tap(find.bySemanticsLabel('Settings'));
    await wait(t, 1500);
    await shot(t, '10_settings');
    await t.tap(find.text('Sign out'));
    await wait(t, 2000);

    await login(t, 'manager@nonap.demo');
    await wait(t, 2500);
    await shot(t, '11_fleet_dashboard');
    await eyes('closed');
    await wait(t, 3500);
    await shot(t, '12_fleet_live_alert');
    await eyes('open');
    await wait(t, 9000);
    await shot(t, '13_fleet_level3');
    await t.drag(find.byType(ListView).first, const Offset(0, -700));
    await wait(t, 800);
    await shot(t, '14_fleet_feed');

    await eyes('pi_off');
    await wait(t, 14000);
    await t.drag(find.byType(ListView).first, const Offset(0, 900));
    await wait(t, 800);
    await shot(t, '15_fleet_pi_offline');
    await eyes('pi_on');
  }, timeout: const Timeout(Duration(minutes: 4)));
}
