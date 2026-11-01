import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../core/ist.dart';
import '../../models/alert_item.dart';
import '../../models/session_info.dart';
import '../../providers/alert_controller.dart';
import '../../providers/auth_provider.dart';
import '../../providers/driver_live_provider.dart';
import '../../providers/driver_provider.dart';
import '../../services/ws_service.dart';
import '../../theme/tokens.dart';
import '../../theme/typography.dart';
import '../../widgets/live_video_preview.dart';
import '../../widgets/metric_card.dart';
import '../../widgets/status_ring.dart';
import '../../widgets/ui.dart';

class DriverDashboardScreen extends ConsumerStatefulWidget {
  const DriverDashboardScreen({super.key});

  @override
  ConsumerState<DriverDashboardScreen> createState() => _DriverDashboardScreenState();
}

class _DriverDashboardScreenState extends ConsumerState<DriverDashboardScreen> {
  bool _showCamera = false;

  Future<void> _toggleSession(bool active) async {
    final live = ref.read(driverLiveProvider.notifier);
    final err = active ? await live.endSession() : await live.startSession();
    if (!mounted) return;
    if (err != null) {
      showToast(context, err, error: true);
    } else {
      showToast(context, active ? 'Session ended. Drive safe.' : 'Driving mode on. The screen stays awake.');
    }
  }

  Future<void> _sos() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Send emergency SOS?'),
        content: const Text('Your fleet manager is alerted immediately as a critical emergency.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: Text('Send SOS', style: AppText.label(color: AppColors.danger)),
          ),
        ],
      ),
    );
    if (ok != true || !mounted) return;
    try {
      await ref.read(apiServiceProvider).reportAccidentSos(driverId: ref.read(authProvider).user?.id);
      if (mounted) showToast(context, 'SOS sent to your fleet manager.');
    } catch (_) {
      if (mounted) showToast(context, "Couldn't send SOS. Check the connection.", error: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(authProvider).user;
    final live = ref.watch(driverLiveProvider);
    final data = ref.watch(driverDataProvider);
    final ws = ref.watch(wsStatusProvider).valueOrNull ?? WsStatus.connecting;
    final alertUi = ref.watch(alertControllerProvider);

    // Session counters move when an alert is raised or acknowledged.
    ref.listen(alertControllerProvider, (prev, next) {
      if (prev?.takeover?.id != next.takeover?.id || prev?.banner?.id != next.banner?.id || next.confirmed != null) {
        ref.read(driverLiveProvider.notifier).refreshSession();
      }
    });

    final t = live.latest;
    final earT = t?.earThreshold ?? data.earThreshold;
    final marT = t?.marThreshold ?? data.marThreshold;
    final level = alertUi.level > 0 ? alertUi.level : (t?.level ?? 0);
    final session = live.session;
    final d = AppMotion.reduced(context) ? Duration.zero : 1.ms;

    // Hero ring
    String word;
    String? sub;
    bool active = true;
    if (!live.cameraOnline && !live.isLive) {
      word = live.videoSource == 'pi' ? 'Camera offline' : 'Camera idle';
      sub = live.videoSource == 'pi' ? 'Check the Pi and its Ethernet cable' : (session.active ? 'Starting the webcam…' : 'Start driving to turn the webcam on');
      active = false;
    } else if (!live.isLive) {
      word = 'Waiting';
      sub = 'Camera is online, waiting for frames';
      active = false;
    } else if (t!.state == 'no_face') {
      word = 'No face detected';
      sub = 'Look towards the camera';
    } else if (level >= 2) {
      word = 'Drowsy';
      sub = 'Level $level alert';
    } else if (level == 1 || t.state == 'drowsy') {
      word = 'Drowsy';
      sub = t.reason == 'yawn' ? 'Yawning detected' : 'Eyes closing · ${t.eyesClosedSeconds.toStringAsFixed(1)} s';
    } else {
      word = 'Alert';
      sub = 'Eyes open · monitoring';
    }
    final risk = riskOf(level: level, eyesClosedSeconds: t?.eyesClosedSeconds ?? 0);

    return Scaffold(
      body: PageBackground(
        child: SafeArea(
          bottom: false,
          child: RefreshIndicator(
            color: AppColors.primary,
            backgroundColor: AppColors.surface,
            onRefresh: () async {
              await Future.wait([
                ref.read(driverLiveProvider.notifier).refresh(),
                ref.read(driverDataProvider.notifier).refresh(),
              ]);
            },
            child: ListView(
              padding: const EdgeInsets.fromLTRB(AppSpace.gutter, AppSpace.l, AppSpace.gutter, AppSpace.xxxl),
              children: [
                // Header
                Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text('${Ist.greeting()},', style: AppText.body(color: AppColors.textMuted)),
                      Text(firstNameOf(user?.fullName ?? 'Driver'), style: AppText.headline()),
                      const SizedBox(height: 2),
                      Text('${Ist.hm(DateTime.now())} IST · ${Ist.dayLabel(DateTime.now())}',
                          style: AppText.caption(color: AppColors.textSecondary)),
                    ]),
                  ),
                  _RoundIcon(icon: PhosphorIconsRegular.clockCounterClockwise, label: 'Alert history', onTap: () => context.push('/driver/history')),
                  const SizedBox(width: AppSpace.s),
                  _RoundIcon(icon: PhosphorIconsRegular.gearSix, label: 'Settings', onTap: () => context.push('/driver/settings')),
                ]),
                const SizedBox(height: AppSpace.l),
                // Connection chips
                Wrap(spacing: AppSpace.s, runSpacing: AppSpace.s, children: [
                  ConnectionChip(
                    label: ws == WsStatus.connected ? 'Backend' : (ws == WsStatus.reconnecting ? 'Reconnecting' : 'Connecting'),
                    tone: ws == WsStatus.connected ? ChipTone.ok : (ws == WsStatus.disconnected ? ChipTone.bad : ChipTone.warn),
                    icon: PhosphorIconsRegular.broadcast,
                  ),
                  if (live.videoSource == 'pi')
                    ConnectionChip(
                      label: 'Pi Camera',
                      detail: live.device?.online == true
                          ? [
                              if (live.device!.fps != null) '${live.device!.fps!.toStringAsFixed(1)} fps',
                              if (live.device!.cpuTempC != null) '${live.device!.cpuTempC!.round()}°C',
                            ].join(' · ')
                          : 'offline',
                      tone: live.device?.online == true ? ChipTone.ok : ChipTone.bad,
                      icon: PhosphorIconsRegular.camera,
                    )
                  else
                    ConnectionChip(
                      label: 'MacBook cam',
                      tone: live.isLive ? ChipTone.ok : ChipTone.idle,
                      icon: PhosphorIconsRegular.camera,
                    ),
                  ConnectionChip(
                    label: live.isLive ? 'Live' : 'Idle',
                    tone: live.isLive ? ChipTone.ok : ChipTone.idle,
                    icon: PhosphorIconsRegular.pulse,
                  ),
                ]),
                const SizedBox(height: AppSpace.xl),
                // Hero
                Center(
                  child: StatusRing(word: word, sub: sub, risk: risk, active: active, size: 264),
                ).animate().fadeIn(duration: d * 500).scaleXY(begin: 0.96, end: 1, curve: AppMotion.curve, duration: d * 500),
                const SizedBox(height: AppSpace.xl),
                // Metrics
                Row(children: [
                  Expanded(
                    child: MetricCard(
                      label: 'EAR',
                      hint: 'eye openness',
                      value: live.isLive && t!.hasFace ? t.ear : null,
                      threshold: earT,
                      series: live.ear,
                      lowIsBad: true,
                      floorMax: 0.40,
                    ),
                  ),
                  const SizedBox(width: AppSpace.m),
                  Expanded(
                    child: MetricCard(
                      label: 'MAR',
                      hint: 'mouth',
                      value: live.isLive && t!.hasFace ? t.mar : null,
                      threshold: marT,
                      series: live.mar,
                      lowIsBad: false,
                      floorMax: 0.90,
                    ),
                  ),
                ]),
                const SizedBox(height: AppSpace.m),
                // Session
                _SessionCard(session: session),
                const SizedBox(height: AppSpace.m),
                // Camera preview
                GlassCard(
                  padding: EdgeInsets.zero,
                  child: Column(children: [
                    ListTile(
                      onTap: () => setState(() => _showCamera = !_showCamera),
                      leading: Icon(PhosphorIconsRegular.camera, color: AppColors.textSecondary),
                      title: Text('Camera view', style: AppText.label()),
                      subtitle: Text('Frames stay in memory, nothing is recorded', style: AppText.caption()),
                      trailing: AnimatedRotation(
                        turns: _showCamera ? 0.25 : 0,
                        duration: AppMotion.of(context, AppMotion.fast),
                        child: Icon(PhosphorIconsRegular.caretRight, color: AppColors.textMuted),
                      ),
                    ),
                    AnimatedSize(
                      duration: AppMotion.of(context, AppMotion.medium),
                      curve: AppMotion.curve,
                      child: _showCamera
                          ? Padding(
                              padding: const EdgeInsets.fromLTRB(AppSpace.m, 0, AppSpace.m, AppSpace.m),
                              child: LiveVideoPreview(source: live.videoSource),
                            )
                          : const SizedBox(width: double.infinity),
                    ),
                  ]),
                ),
                const SizedBox(height: AppSpace.m),
                Row(children: [
                  Expanded(
                    child: GhostButton(
                      label: 'Calibrate',
                      icon: PhosphorIconsRegular.target,
                      color: AppColors.primary,
                      onPressed: () => context.push('/driver/calibration'),
                    ),
                  ),
                  const SizedBox(width: AppSpace.m),
                  Expanded(
                    child: GhostButton(label: 'SOS', icon: PhosphorIconsRegular.siren, color: AppColors.danger, onPressed: _sos),
                  ),
                ]),
                const SizedBox(height: AppSpace.l),
                GradientButton(
                  label: session.active ? 'End session' : 'Start driving',
                  icon: session.active ? PhosphorIconsFill.stopCircle : PhosphorIconsFill.steeringWheel,
                  gradient: session.active ? AppGlow.dangerButton : AppGlow.primaryButton,
                  foreground: session.active ? AppColors.textPrimary : AppColors.onPrimary,
                  loading: live.sessionBusy,
                  height: 60,
                  onPressed: () => _toggleSession(session.active),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _RoundIcon extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  const _RoundIcon({required this.icon, required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: label,
      child: Material(
        color: AppColors.surface.withValues(alpha: 0.6),
        shape: const CircleBorder(side: BorderSide(color: AppColors.border)),
        child: InkWell(
          customBorder: const CircleBorder(),
          onTap: onTap,
          child: Padding(padding: const EdgeInsets.all(11), child: Icon(icon, size: 20, color: AppColors.textPrimary)),
        ),
      ),
    );
  }
}

class _SessionCard extends StatelessWidget {
  final SessionInfo session;
  const _SessionCard({required this.session});

  @override
  Widget build(BuildContext context) {
    final started = session.startedAt;
    final active = session.active;
    final seconds = active && started != null ? DateTime.now().difference(started).inSeconds : session.drivingSeconds;
    return GlassCard(
      glow: active ? AppColors.primary : null,
      padding: const EdgeInsets.all(AppSpace.l),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Text('SESSION', style: AppText.overline(color: AppColors.textSecondary)),
          const SizedBox(width: AppSpace.s),
          if (active)
            const Pill('Driving', color: AppColors.success)
          else
            const Pill('Not driving', color: AppColors.textMuted),
          const Spacer(),
          if (started != null) Text('since ${Ist.hmIst(started)}', style: AppText.caption()),
        ]),
        const SizedBox(height: AppSpace.m),
        Row(children: [
          _SessionStat(label: 'Driving time', value: active || seconds > 0 ? Ist.clockSpan(seconds) : '—'),
          _SessionStat(label: 'Alerts', value: active || session.alerts > 0 ? '${session.alerts}' : '—'),
          _SessionStat(label: 'Avg. response', value: Ist.duration(session.avgAckMs)),
        ]),
      ]),
    );
  }
}

class _SessionStat extends StatelessWidget {
  final String label;
  final String value;
  const _SessionStat({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(value, style: AppText.metric(size: 22)),
        const SizedBox(height: 4),
        Text(label, style: AppText.caption()),
      ]),
    );
  }
}
