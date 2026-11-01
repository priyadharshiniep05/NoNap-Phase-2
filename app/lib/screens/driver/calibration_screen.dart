import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../providers/driver_live_provider.dart';
import '../../providers/driver_provider.dart';
import '../../theme/tokens.dart';
import '../../theme/typography.dart';
import '../../widgets/countdown_ring.dart';
import '../../widgets/ui.dart';

/// Guided 10-second baseline capture that sets the driver's personal EAR/MAR thresholds.
class CalibrationScreen extends ConsumerStatefulWidget {
  const CalibrationScreen({super.key});

  @override
  ConsumerState<CalibrationScreen> createState() => _CalibrationScreenState();
}

class _CalibrationScreenState extends ConsumerState<CalibrationScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => ref.read(driverLiveProvider.notifier).resetCalibration());
  }

  Future<void> _start() async {
    HapticFeedback.mediumImpact();
    final err = await ref.read(driverLiveProvider.notifier).startCalibration();
    if (err != null && mounted) showToast(context, err, error: true);
  }

  @override
  Widget build(BuildContext context) {
    final live = ref.watch(driverLiveProvider);
    final cal = live.calibration;

    ref.listen(driverLiveProvider.select((s) => s.calibration.result), (prev, next) {
      if (prev == null && next != null) {
        HapticFeedback.heavyImpact();
        ref.read(driverDataProvider.notifier).reloadThresholds();
      }
    });

    final Widget content;
    if (cal.result != null) {
      content = _Done(result: cal.result!, onDone: () => Navigator.of(context).maybePop());
    } else if (cal.running) {
      content = _Running(progress: cal.progress, remaining: cal.remaining, cameraLive: live.isLive);
    } else {
      content = _Intro(cameraOk: live.cameraOnline || live.isLive, onStart: _start, error: cal.error);
    }

    return Scaffold(
      appBar: AppBar(title: const Text('Calibration')),
      body: PageBackground(
        child: SafeArea(
          top: false,
          child: AnimatedSwitcher(
            duration: AppMotion.of(context, AppMotion.slow),
            switchInCurve: AppMotion.curve,
            child: KeyedSubtree(key: ValueKey(cal.result != null ? 'done' : (cal.running ? 'run' : 'intro')), child: content),
          ),
        ),
      ),
    );
  }
}

class _Intro extends StatelessWidget {
  final bool cameraOk;
  final VoidCallback onStart;
  final String? error;
  const _Intro({required this.cameraOk, required this.onStart, this.error});

  @override
  Widget build(BuildContext context) {
    Widget tip(IconData i, String t) => Padding(
          padding: const EdgeInsets.only(bottom: AppSpace.m),
          child: Row(children: [
            Icon(i, color: AppColors.primary, size: 20),
            const SizedBox(width: AppSpace.m),
            Expanded(child: Text(t, style: AppText.body(color: AppColors.textPrimary))),
          ]),
        );
    return ListView(padding: const EdgeInsets.all(AppSpace.gutter), children: [
      const SizedBox(height: AppSpace.l),
      Center(
        child: Container(
          width: 120,
          height: 120,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: AppColors.primary.withValues(alpha: 0.08),
            border: Border.all(color: AppColors.primary.withValues(alpha: 0.3)),
            boxShadow: AppGlow.of(AppColors.primary),
          ),
          child: Icon(PhosphorIconsRegular.scan, size: 56, color: AppColors.primary),
        ),
      ),
      const SizedBox(height: AppSpace.xl),
      Text('Look at the camera normally for 10 seconds', textAlign: TextAlign.center, style: AppText.headline().copyWith(fontSize: 24)),
      const SizedBox(height: AppSpace.s),
      Text(
        'NoNap learns how open your eyes and mouth are when you are alert, and sets your personal thresholds from it.',
        textAlign: TextAlign.center,
        style: AppText.body(color: AppColors.textMuted),
      ),
      const SizedBox(height: AppSpace.xl),
      GlassCard(
        padding: const EdgeInsets.all(AppSpace.l),
        child: Column(children: [
          tip(PhosphorIconsRegular.steeringWheel, 'Sit the way you drive'),
          tip(PhosphorIconsRegular.eye, 'Eyes open, blink normally'),
          tip(PhosphorIconsRegular.smiley, 'Relaxed mouth, no talking'),
          tip(PhosphorIconsRegular.sun, 'Light on your face, not behind you'),
        ]),
      ),
      if (!cameraOk) ...[
        const SizedBox(height: AppSpace.m),
        GlassCard(
          borderColor: AppColors.warning.withValues(alpha: 0.5),
          padding: const EdgeInsets.all(AppSpace.m),
          child: Row(children: [
            Icon(PhosphorIconsRegular.cameraSlash, color: AppColors.warning),
            const SizedBox(width: AppSpace.m),
            Expanded(child: Text('The camera is offline. Start the Pi (or Start driving in webcam mode) first.', style: AppText.caption(color: AppColors.textSecondary))),
          ]),
        ),
      ],
      if (error != null) ...[
        const SizedBox(height: AppSpace.m),
        Text(error!, textAlign: TextAlign.center, style: AppText.caption(color: AppColors.warning)),
      ],
      const SizedBox(height: AppSpace.xl),
      GradientButton(label: 'Start calibration', icon: PhosphorIconsFill.target, onPressed: onStart),
    ]);
  }
}

class _Running extends StatelessWidget {
  final double progress;
  final double remaining;
  final bool cameraLive;
  const _Running({required this.progress, required this.remaining, required this.cameraLive});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        ProgressRing(
          progress: progress,
          size: 240,
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Text(remaining > 0 ? remaining.ceil().toString() : '…', style: AppText.display().copyWith(fontSize: 64)),
            Text(remaining > 0 ? 'seconds' : 'finishing', style: AppText.caption()),
          ]),
        ),
        const SizedBox(height: AppSpace.xl),
        Text('Keep looking at the camera', style: AppText.title()),
        const SizedBox(height: AppSpace.xs),
        Text(cameraLive ? 'Eyes open, mouth relaxed' : 'Waiting for camera frames…', style: AppText.body(color: AppColors.textMuted)),
      ]),
    );
  }
}

class _Done extends StatelessWidget {
  final Map<String, dynamic> result;
  final VoidCallback onDone;
  const _Done({required this.result, required this.onDone});

  @override
  Widget build(BuildContext context) {
    String f(String k) => ((result[k] as num?)?.toDouble() ?? 0).toStringAsFixed(2);
    final d = AppMotion.reduced(context) ? Duration.zero : 1.ms;
    return ListView(padding: const EdgeInsets.all(AppSpace.gutter), children: [
      const SizedBox(height: AppSpace.xl),
      Center(
        child: Container(
          width: 110,
          height: 110,
          decoration: BoxDecoration(shape: BoxShape.circle, color: AppColors.success.withValues(alpha: 0.14), boxShadow: AppGlow.of(AppColors.success)),
          child: Icon(PhosphorIconsFill.checkCircle, size: 64, color: AppColors.success),
        ).animate().scaleXY(begin: 0.4, end: 1, duration: d * 500, curve: Curves.easeOutBack).fadeIn(duration: d * 300),
      ),
      const SizedBox(height: AppSpace.xl),
      Text('Calibrated', textAlign: TextAlign.center, style: AppText.headline()),
      const SizedBox(height: AppSpace.xs),
      Text('Your personal thresholds are saved and used for every alert from now on.',
          textAlign: TextAlign.center, style: AppText.body(color: AppColors.textMuted)),
      const SizedBox(height: AppSpace.xl),
      Row(children: [
        Expanded(child: StatTile(label: 'EAR threshold', value: f('ear_threshold'), icon: PhosphorIconsRegular.eye, sub: 'your open ${f('baseline_mean_ear')}')),
        const SizedBox(width: AppSpace.m),
        Expanded(child: StatTile(label: 'MAR threshold', value: f('mar_threshold'), icon: PhosphorIconsRegular.smiley, color: AppColors.warning, sub: 'rest ${f('baseline_mean_mar')}')),
      ]).animate(delay: d * 200).fadeIn(duration: d * 400).slideY(begin: 0.1, end: 0, curve: AppMotion.curve),
      const SizedBox(height: AppSpace.s),
      Text('${result['samples_count'] ?? 0} frames measured', textAlign: TextAlign.center, style: AppText.caption()),
      const SizedBox(height: AppSpace.xl),
      GradientButton(label: 'Done', onPressed: onDone),
    ]);
  }
}
