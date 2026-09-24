import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/services.dart';

class AlertPlayer {
  static final AlertPlayer _instance = AlertPlayer._internal();
  factory AlertPlayer() => _instance;
  AlertPlayer._internal();

  final AudioPlayer _player = AudioPlayer();
  DateTime _lastPlayed = DateTime.fromMillisecondsSinceEpoch(0);

  Future<void> playAlert({bool isCritical = false}) async {
    final now = DateTime.now();
    // 3 second cooldown between audible alerts to prevent screeching
    if (now.difference(_lastPlayed).inSeconds < 3) return;
    _lastPlayed = now;

    try {
      // Trigger strong haptic feedback
      if (isCritical) {
        await HapticFeedback.heavyImpact();
        await Future.delayed(const Duration(milliseconds: 150));
        await HapticFeedback.heavyImpact();
      } else {
        await HapticFeedback.vibrate();
      }

      // Play pulsing alert alarm
      await _player.stop();
      await _player.play(AssetSource('sounds/alarm.wav'), volume: isCritical ? 1.0 : 0.8);
    } catch (e) {
      // Audio fallback
    }
  }

  Future<void> stop() async {
    try {
      await _player.stop();
    } catch (_) {}
  }
}
