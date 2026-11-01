# app

A new Flutter project.

## Getting Started

This project is a starting point for a Flutter application.

A few resources to get you started if this is your first Flutter project:

- [Lab: Write your first Flutter app](https://docs.flutter.dev/get-started/codelab)
- [Cookbook: Useful Flutter samples](https://docs.flutter.dev/cookbook)

For help getting started with Flutter development, view the
[online documentation](https://docs.flutter.dev/), which offers tutorials,
samples, guidance on mobile development, and a full API reference.

## Alerts and iOS background limits

Driving mode keeps the screen on (`wakelock_plus`), and the alarm plays through the *playback* audio session, so it sounds even with the silent switch on. If NoNap is in the background, a local notification (`flutter_local_notifications`) is the backup alert. **True push to a locked or killed app needs APNs and a paid Apple Developer account**, which this project does not use. Keep NoNap open while driving.

Fonts (Inter, Space Grotesk) are bundled in `assets/google_fonts/` (SIL OFL), so the UI renders correctly without internet access.

Run the app against a server: `flutter run --dart-define=API_BASE_URL=http://<mac-ip>:8000`, or set the address in the app's server sheet. UI tour on a simulator: see `integration_test/ui_tour_test.dart`.
