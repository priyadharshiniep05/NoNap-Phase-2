import 'dart:io';

import 'package:integration_test/integration_test_driver_extended.dart';

/// Saves screenshots from integration_test/ui_tour_test.dart into
/// build/screenshots/ (override with SCREENSHOT_DIR).
Future<void> main() async {
  final dir = Platform.environment['SCREENSHOT_DIR'] ?? 'build/screenshots';
  await integrationDriver(
    onScreenshot: (name, bytes, [args]) async {
      final f = File('$dir/$name.png');
      await f.create(recursive: true);
      await f.writeAsBytes(bytes);
      return true;
    },
  );
}
