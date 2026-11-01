import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../core/ist.dart';
import '../../models/alert_item.dart';
import '../../providers/alert_controller.dart';
import '../../providers/auth_provider.dart';
import '../../providers/driver_live_provider.dart';
import '../../providers/driver_provider.dart';
import '../../theme/tokens.dart';
import '../../theme/typography.dart';
import '../../widgets/countdown_ring.dart';
import '../../widgets/ui.dart';

/// Wraps every driver screen: whatever the driver is looking at, a level-1
/// banner or the level 2-3 takeover appears on top of it.
class DriverShell extends ConsumerStatefulWidget {
  final Widget child;
  const DriverShell({super.key, required this.child});

  @override
  ConsumerState<DriverShell> createState() => _DriverShellState();
}

class _DriverShellState extends ConsumerState<DriverShell> with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) ref.read(wsServiceProvider).kick();
  }

  @override
  Widget build(BuildContext context) {
    // Keep the driver's providers alive for as long as the driver is signed in.
    ref.watch(driverDataProvider.select((s) => s.loaded));
    final ackTimeout = ref.watch(driverLiveProvider.select((s) => s.ackTimeoutSeconds));
    final ui = ref.watch(alertControllerProvider);
    final ctrl = ref.read(alertControllerProvider.notifier);
    final dur = AppMotion.of(context, AppMotion.medium);

    return Stack(children: [
      widget.child,
      // Level 1 banner
      Positioned(
        top: 0,
        left: 0,
        right: 0,
        child: SafeArea(
          child: AnimatedSwitcher(
            duration: dur,
            switchInCurve: AppMotion.curve,
            transitionBuilder: (c, a) => SlideTransition(
              position: Tween(begin: const Offset(0, -1.2), end: Offset.zero).animate(a),
              child: FadeTransition(opacity: a, child: c),
            ),
            child: ui.banner == null
                ? const SizedBox.shrink(key: ValueKey('none'))
                : _LevelOneBanner(key: ValueKey(ui.banner!.id), alert: ui.banner!, message: ui.bannerMessage),
          ),
        ),
      ),
      // Level 2-3 takeover
      Positioned.fill(
        child: AnimatedSwitcher(
          duration: dur,
          switchInCurve: AppMotion.curve,
          transitionBuilder: (c, a) => FadeTransition(opacity: a, child: ScaleTransition(scale: Tween(begin: 1.04, end: 1.0).animate(a), child: c)),
          child: ui.takeover == null
              ? const SizedBox.shrink(key: ValueKey('none'))
              : AlertTakeover(
                  key: const ValueKey('takeover'),
                  alert: ui.takeover!,
                  message: ui.takeoverMessage,
                  spoken: ui.spoken,
                  countdownStart: ui.countdownStart ?? DateTime.now(),
                  ackTimeout: Duration(seconds: ackTimeout),
                  acking: ui.acking,
                  error: ui.ackError,
                  onAck: ctrl.acknowledge,
                ),
        ),
      ),
      // "Stay safe" confirmation
      Positioned.fill(
        child: AnimatedSwitcher(
          duration: dur,
          child: ui.confirmed == null
              ? const SizedBox.shrink(key: ValueKey('none'))
              : _StaySafeCard(key: ValueKey('ok-${ui.confirmed!.id}'), alert: ui.confirmed!, onClose: ctrl.dismissConfirmation),
        ),
      ),
    ]);
  }
}

class _LevelOneBanner extends ConsumerWidget {
  final AlertItem alert;
  final String message;
  const _LevelOneBanner({super.key, required this.alert, required this.message});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(AppSpace.m, AppSpace.s, AppSpace.m, 0),
      child: Material(
        type: MaterialType.transparency,
        child: Semantics(
          liveRegion: true,
          label: 'Level 1 alert. $message',
          child: GlassCard(
            glow: AppColors.warning,
            borderColor: AppColors.warning.withValues(alpha: 0.6),
            padding: const EdgeInsets.all(AppSpace.l),
            child: Row(children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(color: AppColors.warning.withValues(alpha: 0.18), shape: BoxShape.circle),
                child: Icon(alert.reason == 'yawn' ? PhosphorIconsFill.smiley : PhosphorIconsFill.eye, color: AppColors.warning, size: 22),
              ),
              const SizedBox(width: AppSpace.m),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Row(children: [
                    Text('Stay focused', style: AppText.title().copyWith(fontSize: 16)),
                    const SizedBox(width: AppSpace.s),
                    const LevelChip(1),
                  ]),
                  const SizedBox(height: 2),
                  Text(message, style: AppText.caption(color: AppColors.textSecondary), maxLines: 2),
                ]),
              ),
            ]),
          ),
        ),
      ),
    );
  }
}

/// Full-screen level 2-3 alert with the "I'm awake" button inside a draining ring.
class AlertTakeover extends StatelessWidget {
  final AlertItem alert;
  final String message;
  final String spoken;
  final DateTime countdownStart;
  final Duration ackTimeout;
  final bool acking;
  final String? error;
  final VoidCallback onAck;

  const AlertTakeover({
    super.key,
    required this.alert,
    required this.message,
    required this.spoken,
    required this.countdownStart,
    required this.ackTimeout,
    required this.acking,
    required this.error,
    required this.onAck,
  });

  @override
  Widget build(BuildContext context) {
    final l3 = alert.effectiveLevel >= 3;
    final reduced = AppMotion.reduced(context);
    final size = MediaQuery.sizeOf(context);
    final ringSize = (size.width * 0.68).clamp(220.0, 300.0);

    Widget bg = DecoratedBox(
      decoration: const BoxDecoration(
        gradient: RadialGradient(
          center: Alignment(0, -0.1),
          radius: 1.1,
          colors: [Color(0xFFDC2626), AppColors.dangerDeep, Color(0xFF1A0508)],
          stops: [0, 0.55, 1],
        ),
      ),
      child: const SizedBox.expand(),
    );
    if (!reduced) {
      bg = bg
          .animate(onPlay: (c) => c.repeat(reverse: true))
          .custom(
            duration: (l3 ? 500 : 800).ms,
            curve: Curves.easeInOut,
            builder: (_, v, child) => Opacity(opacity: 0.72 + 0.28 * v, child: child),
          );
    }

    return Material(
      color: Colors.black,
      child: Semantics(
        liveRegion: true,
        label: 'Level ${alert.effectiveLevel} drowsiness alert. $spoken',
        child: Stack(fit: StackFit.expand, children: [
          bg,
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: AppSpace.xl),
              child: Column(children: [
                const SizedBox(height: AppSpace.l),
                Row(children: [
                  Pill('LEVEL ${alert.effectiveLevel}', color: AppColors.textPrimary, icon: PhosphorIconsFill.warning),
                  const Spacer(),
                  Text(Ist.hmIst(alert.detectedAt), style: AppText.label(color: AppColors.textPrimary.withValues(alpha: 0.85))),
                ]),
                const Spacer(),
                _ClosingEye(reduced: reduced),
                const SizedBox(height: AppSpace.l),
                Text('Wake up!', style: AppText.display().copyWith(fontSize: 52)),
                const SizedBox(height: AppSpace.s),
                Text(
                  spoken.isNotEmpty ? spoken : message,
                  textAlign: TextAlign.center,
                  style: AppText.body(color: AppColors.textPrimary.withValues(alpha: 0.92)).copyWith(fontSize: 17),
                ),
                if (l3) ...[
                  const SizedBox(height: AppSpace.m),
                  Pill('Your fleet manager has been notified', color: AppColors.textPrimary, icon: PhosphorIconsFill.broadcast)
                      .animate(onPlay: (c) => reduced ? null : c.repeat(reverse: true))
                      .fade(begin: 0.7, end: 1, duration: 700.ms),
                ],
                const Spacer(),
                CountdownRing(
                  start: countdownStart,
                  total: ackTimeout,
                  size: ringSize,
                  stroke: 9,
                  color: AppColors.textPrimary,
                  child: _AwakeButton(size: ringSize * 0.74, busy: acking, onTap: onAck),
                ),
                const SizedBox(height: AppSpace.m),
                SizedBox(
                  height: 36,
                  child: error == null
                      ? Text('Tap when you are fully awake', style: AppText.caption(color: AppColors.textPrimary.withValues(alpha: 0.8)))
                      : Text(error!, textAlign: TextAlign.center, style: AppText.caption(color: AppColors.textPrimary)),
                ),
                const SizedBox(height: AppSpace.l),
              ]),
            ),
          ),
        ]),
      ),
    );
  }
}

class _ClosingEye extends StatelessWidget {
  final bool reduced;
  const _ClosingEye({required this.reduced});

  @override
  Widget build(BuildContext context) {
    final box = Container(
      width: 88,
      height: 88,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: Colors.white.withValues(alpha: 0.12),
        border: Border.all(color: Colors.white.withValues(alpha: 0.35)),
      ),
      child: Stack(alignment: Alignment.center, children: [
        Icon(PhosphorIconsBold.eye, size: 44, color: Colors.white)
            .animate(onPlay: (c) => reduced ? null : c.repeat(reverse: true))
            .fade(begin: 1, end: 0, duration: 900.ms, curve: Curves.easeInOut),
        Icon(PhosphorIconsBold.eyeClosed, size: 44, color: Colors.white)
            .animate(onPlay: (c) => reduced ? null : c.repeat(reverse: true))
            .fade(begin: 0, end: 1, duration: 900.ms, curve: Curves.easeInOut),
      ]),
    );
    if (reduced) return box;
    return box.animate(onPlay: (c) => c.repeat(reverse: true)).scaleXY(begin: 0.96, end: 1.06, duration: 900.ms);
  }
}

class _AwakeButton extends StatefulWidget {
  final double size;
  final bool busy;
  final VoidCallback onTap;
  const _AwakeButton({required this.size, required this.busy, required this.onTap});

  @override
  State<_AwakeButton> createState() => _AwakeButtonState();
}

class _AwakeButtonState extends State<_AwakeButton> {
  bool _down = false;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: "I'm awake",
      child: GestureDetector(
        onTapDown: (_) => setState(() => _down = true),
        onTapCancel: () => setState(() => _down = false),
        onTapUp: (_) {
          setState(() => _down = false);
          HapticFeedback.heavyImpact();
          widget.onTap();
        },
        child: AnimatedScale(
          scale: _down ? 0.94 : 1,
          duration: const Duration(milliseconds: 110),
          child: Container(
            width: widget.size,
            height: widget.size,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: Colors.white,
              boxShadow: AppGlow.of(Colors.white, opacity: 0.45, blur: 40),
            ),
            alignment: Alignment.center,
            child: widget.busy
                ? const SizedBox(width: 32, height: 32, child: CircularProgressIndicator(strokeWidth: 3, color: AppColors.danger))
                : Column(mainAxisSize: MainAxisSize.min, children: [
                    Icon(PhosphorIconsFill.handPalm, color: AppColors.danger, size: widget.size * 0.2),
                    const SizedBox(height: 6),
                    Text("I'm awake", style: AppText.headline(color: AppColors.dangerDeep).copyWith(fontSize: widget.size * 0.14)),
                  ]),
          ),
        ),
      ),
    );
  }
}

class _StaySafeCard extends StatelessWidget {
  final AlertItem alert;
  final VoidCallback onClose;
  const _StaySafeCard({super.key, required this.alert, required this.onClose});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.black.withValues(alpha: 0.55),
      child: Center(
        child: Padding(
          padding: const EdgeInsets.all(AppSpace.xl),
          child: GlassCard(
            glow: AppColors.success,
            padding: const EdgeInsets.all(AppSpace.xl),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(shape: BoxShape.circle, color: AppColors.success.withValues(alpha: 0.14)),
                child: Icon(PhosphorIconsFill.coffee, size: 36, color: AppColors.success),
              ).animate().scaleXY(begin: 0.6, end: 1, duration: AppMotion.of(context, AppMotion.slow), curve: Curves.easeOutBack),
              const SizedBox(height: AppSpace.l),
              Text('Stay safe — consider a break', textAlign: TextAlign.center, style: AppText.title()),
              const SizedBox(height: AppSpace.s),
              Text(
                alert.responseTimeMs != null
                    ? 'You responded in ${Ist.duration(alert.responseTimeMs)}. A short stop and some water help more than pushing on.'
                    : 'A short stop and some water help more than pushing on.',
                textAlign: TextAlign.center,
                style: AppText.body(),
              ),
              const SizedBox(height: AppSpace.xl),
              SizedBox(width: double.infinity, child: GradientButton(label: 'Okay', height: 50, onPressed: onClose)),
            ]),
          ),
        ),
      ),
    );
  }
}
