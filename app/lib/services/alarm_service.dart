import 'dart:async';

import 'package:audio_session/audio_session.dart' as session;
import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:torch_light/torch_light.dart';
import 'package:vibration/vibration.dart';

/// Everything the phone does physically when the driver is drowsy:
/// sound, vibration, flashlight strobe and a spoken warning.
///
/// The iOS audio session uses the *playback* category, so the alarm plays
/// even with the ring/silent switch on silent.
class AlarmService {
  static final AlarmService _instance = AlarmService._internal();
  factory AlarmService() => _instance;
  AlarmService._internal();

  final AudioPlayer _alarm = AudioPlayer(playerId: 'nonap_alarm');
  final AudioPlayer _chime = AudioPlayer(playerId: 'nonap_chime');
  final FlutterTts _tts = FlutterTts();

  Timer? _vibeTimer;
  Timer? _torchTimer;
  Timer? _speakTimer;
  bool _torchOn = false;
  bool _torchAvailable = false;
  bool _critical = false;
  bool _ready = false;

  bool get isActive => _critical;

  Future<void> init() async {
    if (_ready) return;
    _ready = true;
    try {
      final s = await session.AudioSession.instance;
      await s.configure(const session.AudioSessionConfiguration(
        avAudioSessionCategory: session.AVAudioSessionCategory.playback,
        avAudioSessionCategoryOptions: session.AVAudioSessionCategoryOptions.duckOthers,
        avAudioSessionMode: session.AVAudioSessionMode.defaultMode,
      ));
      await AudioPlayer.global.setAudioContext(AudioContext(
        iOS: AudioContextIOS(
          category: AVAudioSessionCategory.playback,
          options: const {AVAudioSessionOptions.duckOthers},
        ),
      ));
      await _alarm.setReleaseMode(ReleaseMode.loop);
      await _alarm.setSource(AssetSource('sounds/alarm.wav'));
      await _chime.setReleaseMode(ReleaseMode.stop);

      await _tts.setSharedInstance(true);
      await _tts.setIosAudioCategory(
        IosTextToSpeechAudioCategory.playback,
        [IosTextToSpeechAudioCategoryOptions.duckOthers, IosTextToSpeechAudioCategoryOptions.mixWithOthers],
        IosTextToSpeechAudioMode.spokenAudio,
      );
      final langs = (await _tts.getLanguages as List?)?.cast<String>() ?? const [];
      await _tts.setLanguage(langs.contains('en-IN') ? 'en-IN' : 'en-US');
      await _tts.setSpeechRate(0.47);
      await _tts.setVolume(1.0);
      _tts.setStartHandler(() => _alarm.setVolume(0.3));
      _tts.setCompletionHandler(() {
        if (_critical) _alarm.setVolume(1.0);
      });
      _torchAvailable = await TorchLight.isTorchAvailable();
    } catch (e) {
      debugPrint('AlarmService init: $e');
    }
  }

  /// Level 1: soft chime + a short double haptic.
  Future<void> chime() async {
    await init();
    if (_critical) return;
    try {
      await _chime.stop();
      await _chime.play(AssetSource('sounds/chime.wav'), volume: 0.9);
    } catch (_) {}
    HapticFeedback.mediumImpact();
    Future.delayed(const Duration(milliseconds: 160), HapticFeedback.mediumImpact);
  }

  /// Levels 2-3: looping alarm, continuous vibration, torch strobe and a
  /// spoken warning repeated every 8 s until [stopAll].
  Future<void> startCritical(String spoken) async {
    await init();
    final wasActive = _critical;
    _critical = true;
    if (!wasActive) {
      try {
        await _chime.stop();
        await _alarm.setVolume(1.0);
        await _alarm.resume();
      } catch (_) {}
      _startVibration();
      _startStrobe();
    }
    _speakTimer?.cancel();
    if (spoken.isNotEmpty) {
      _speak(spoken);
      _speakTimer = Timer.periodic(const Duration(seconds: 8), (_) => _speak(spoken));
    }
  }

  void _speak(String text) {
    if (!_critical) return;
    _tts.stop().then((_) => _tts.speak(text));
  }

  void _startVibration() {
    _vibeTimer?.cancel();
    Future<void> pulse() async {
      try {
        if (await Vibration.hasVibrator()) {
          await Vibration.vibrate(duration: 700, amplitude: 255, sharpness: 0.9);
        } else {
          HapticFeedback.heavyImpact();
        }
      } catch (_) {
        HapticFeedback.heavyImpact();
      }
    }

    pulse();
    _vibeTimer = Timer.periodic(const Duration(milliseconds: 1100), (_) => pulse());
  }

  void _startStrobe() {
    _torchTimer?.cancel();
    if (!_torchAvailable) return;
    _torchTimer = Timer.periodic(const Duration(milliseconds: 300), (_) async {
      try {
        _torchOn = !_torchOn;
        _torchOn ? await TorchLight.enableTorch() : await TorchLight.disableTorch();
      } catch (_) {
        _torchTimer?.cancel();
      }
    });
  }

  /// Stop everything immediately ("I'm awake").
  Future<void> stopAll() async {
    _critical = false;
    _vibeTimer?.cancel();
    _torchTimer?.cancel();
    _speakTimer?.cancel();
    await Future.wait([
      _safe(_alarm.pause()),
      _safe(_alarm.seek(Duration.zero)),
      _safe(_tts.stop()),
      _safe(Vibration.cancel()),
      if (_torchOn || _torchAvailable) _safe(TorchLight.disableTorch()),
    ]);
    _torchOn = false;
  }

  Future<void> _safe(Future f) async {
    try {
      await f;
    } catch (_) {}
  }
}
