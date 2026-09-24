import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:app/main.dart';

void main() {
  testWidgets('NoNap app smoke test builds correctly', (WidgetTester tester) async {
    await tester.pumpWidget(
      const ProviderScope(
        child: NoNapApp(),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));

    // Verify NoNap title is displayed on login screen
    expect(find.text('NoNap'), findsWidgets);
  });
}
