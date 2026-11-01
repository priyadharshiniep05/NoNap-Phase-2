import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../core/ist.dart';
import '../../models/alert_item.dart';
import '../../models/fleet_overview.dart';
import '../../providers/auth_provider.dart';
import '../../providers/fleet_provider.dart';
import '../../services/notification_service.dart';
import '../../services/ws_service.dart';
import '../../theme/tokens.dart';
import '../../theme/typography.dart';
import '../../widgets/brand.dart';
import '../../widgets/ui.dart';

class FleetDashboardScreen extends ConsumerStatefulWidget {
  const FleetDashboardScreen({super.key});

  @override
  ConsumerState<FleetDashboardScreen> createState() => _FleetDashboardScreenState();
}

class _FleetDashboardScreenState extends ConsumerState<FleetDashboardScreen> with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    NotificationService().requestPermission(); // for level-3 alerts while in the background
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
    final user = ref.watch(authProvider).user;
    final fleet = ref.watch(fleetDataProvider);
    final ws = ref.watch(wsStatusProvider).valueOrNull ?? WsStatus.connecting;
    final o = fleet.overview;

    final List<Widget> children;
    if (o == null && fleet.isLoading) {
      children = const [
        Row(children: [Expanded(child: Skeleton(height: 112)), SizedBox(width: AppSpace.m), Expanded(child: Skeleton(height: 112))]),
        SizedBox(height: AppSpace.m),
        Row(children: [Expanded(child: Skeleton(height: 112)), SizedBox(width: AppSpace.m), Expanded(child: Skeleton(height: 112))]),
        SizedBox(height: AppSpace.xl),
        SkeletonList(count: 4, itemHeight: 92),
      ];
    } else if (o == null) {
      children = [ErrorState(message: fleet.error ?? 'Could not load your fleet.', onRetry: () => ref.read(fleetDataProvider.notifier).refresh())];
    } else {
      final drivers = fleet.sortedDrivers;
      children = [
        GridView.count(
          crossAxisCount: 2,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          mainAxisSpacing: AppSpace.m,
          crossAxisSpacing: AppSpace.m,
          childAspectRatio: 1.45,
          children: [
            StatTile(label: 'Drivers online', value: '${o.driversOnline}', sub: 'of ${o.totalDrivers}', icon: PhosphorIconsRegular.users, color: AppColors.success),
            StatTile(
              label: 'Active alerts',
              value: '${o.activeAlerts}',
              icon: PhosphorIconsRegular.bellRinging,
              color: o.activeAlerts > 0 ? AppColors.danger : AppColors.textMuted,
            ),
            StatTile(label: 'Alerts today', value: '${o.alertsToday}', icon: PhosphorIconsRegular.calendarBlank, color: AppColors.warning),
            StatTile(label: 'Avg. response today', value: Ist.duration(o.avgResponseMsToday), icon: PhosphorIconsRegular.timer),
          ],
        ),
        SectionHeader('Drivers', trailing: Text('${drivers.length}', style: AppText.caption())),
        if (drivers.isEmpty)
          const EmptyState(icon: PhosphorIconsRegular.users, message: 'No drivers yet', detail: 'Drivers appear here once they are assigned to your fleet.')
        else
          for (final d in drivers)
            Padding(
              padding: const EdgeInsets.only(bottom: AppSpace.m),
              child: _DriverCard(key: ValueKey(d.driverId), driver: d, onTap: () => context.push('/fleet/driver/${d.driverId}')),
            ),
        const SectionHeader('Live alert feed'),
        if (fleet.alerts.isEmpty)
          const EmptyState(icon: PhosphorIconsRegular.sealCheck, message: 'All quiet', detail: 'New alerts slide in here the moment they happen.')
        else
          for (final a in fleet.alerts.take(20))
            _FeedItem(key: ValueKey(a.id), alert: a, fresh: fleet.freshIds.contains(a.id)),
      ];
    }

    return Scaffold(
      body: PageBackground(
        child: SafeArea(
          bottom: false,
          child: RefreshIndicator(
            color: AppColors.primary,
            backgroundColor: AppColors.surface,
            onRefresh: () => ref.read(fleetDataProvider.notifier).refresh(silent: true),
            child: ListView(
              padding: const EdgeInsets.fromLTRB(AppSpace.gutter, AppSpace.l, AppSpace.gutter, AppSpace.xxxl),
              children: [
                Row(children: [
                  const NoNapMark(size: 40),
                  const SizedBox(width: AppSpace.m),
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(o?.fleetName ?? 'Your fleet', style: AppText.title(), overflow: TextOverflow.ellipsis),
                      Text('${Ist.greeting()}, ${firstNameOf(user?.fullName ?? '')} · ${Ist.hm(DateTime.now())} IST',
                          style: AppText.caption()),
                    ]),
                  ),
                  ConnectionChip(
                    label: ws == WsStatus.connected ? 'Live' : 'Offline',
                    tone: ws == WsStatus.connected ? ChipTone.ok : (ws == WsStatus.reconnecting ? ChipTone.warn : ChipTone.bad),
                    icon: PhosphorIconsRegular.broadcast,
                  ),
                  const SizedBox(width: AppSpace.s),
                  IconButton(
                    tooltip: 'Settings',
                    icon: Icon(PhosphorIconsRegular.gearSix, color: AppColors.textPrimary),
                    onPressed: () => context.push('/fleet/settings'),
                  ),
                ]),
                const SizedBox(height: AppSpace.xl),
                ...children,
              ],
            ),
          ),
        ),
      ),
    );
  }
}

String statusLabel(FleetDriverItem d) {
  if (d.inActiveAlert) {
    return d.activeAlert!.effectiveLevel >= 3 ? 'Not responding' : 'Drowsy · level ${d.activeAlert!.effectiveLevel}';
  }
  if (!d.online) return 'Offline';
  return switch (d.currentStatus) {
    'drowsy' => 'Drowsy',
    'yawning' => 'Yawning',
    'no_face' => 'No face in view',
    _ => 'Alert',
  };
}

Color statusColor(FleetDriverItem d) {
  if (d.inActiveAlert) return AppColors.forLevel(d.activeAlert!.effectiveLevel);
  if (!d.online) return AppColors.textMuted;
  return switch (d.currentStatus) {
    'drowsy' || 'yawning' => AppColors.warning,
    'no_face' => AppColors.warning,
    _ => AppColors.success,
  };
}

class _DriverCard extends StatelessWidget {
  final FleetDriverItem driver;
  final VoidCallback onTap;
  const _DriverCard({super.key, required this.driver, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final d = driver;
    final alerting = d.inActiveAlert;
    final color = statusColor(d);
    final l3 = alerting && d.activeAlert!.effectiveLevel >= 3;

    Widget card = GlassCard(
      onTap: onTap,
      borderColor: alerting ? AppColors.danger : AppColors.border,
      borderWidth: alerting ? 2 : 1,
      padding: const EdgeInsets.all(AppSpace.l),
      child: Row(children: [
        InitialsAvatar(name: d.fullName, ring: color),
        const SizedBox(width: AppSpace.m),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Flexible(child: Text(d.displayName, style: AppText.label().copyWith(fontSize: 15), overflow: TextOverflow.ellipsis)),
              if (d.isSimulated) ...[const SizedBox(width: 6), const Pill('Simulated', color: AppColors.textMuted)],
            ]),
            const SizedBox(height: 2),
            Text(
              [d.vehicle ?? 'No vehicle', if (d.lastAlertAt != null) 'last alert ${Ist.hmIst(d.lastAlertAt!)}'].join(' · '),
              style: AppText.caption(),
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: AppSpace.s),
            Row(children: [
              StatusDot(color: color, pulse: alerting || d.online),
              const SizedBox(width: 6),
              Text(statusLabel(d), style: AppText.caption(color: color).copyWith(fontWeight: FontWeight.w700)),
              if (l3) ...[const SizedBox(width: AppSpace.s), const Pill('Unacknowledged', color: AppColors.danger, solid: true)],
            ]),
          ]),
        ),
        Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
          Icon(
            d.deviceOnline ? PhosphorIconsFill.camera : PhosphorIconsRegular.cameraSlash,
            size: 18,
            color: d.deviceOnline ? AppColors.success : AppColors.textMuted,
          ),
          const SizedBox(height: 4),
          Text(d.deviceOnline ? 'online' : 'offline', style: AppText.caption()),
        ]),
      ]),
    );

    if (alerting && !AppMotion.reduced(context)) {
      card = card
          .animate(onPlay: (c) => c.repeat(reverse: true))
          .boxShadow(
            begin: BoxShadow(color: AppColors.danger.withValues(alpha: 0.10), blurRadius: 8),
            end: BoxShadow(color: AppColors.danger.withValues(alpha: 0.55), blurRadius: 28),
            borderRadius: AppRadii.cardR,
            duration: (l3 ? 500 : 900).ms,
          );
    }
    return Semantics(label: '${d.displayName}, ${statusLabel(d)}', child: card);
  }
}

class _FeedItem extends StatelessWidget {
  final AlertItem alert;
  final bool fresh;
  const _FeedItem({super.key, required this.alert, required this.fresh});

  @override
  Widget build(BuildContext context) {
    final a = alert;
    final lvl = a.effectiveLevel;
    final color = a.type == 'accident' ? AppColors.danger : AppColors.forLevel(lvl);
    final item = Padding(
      padding: const EdgeInsets.only(bottom: AppSpace.s),
      child: GlassCard(
        blur: false,
        padding: const EdgeInsets.symmetric(horizontal: AppSpace.l, vertical: AppSpace.m),
        child: Row(children: [
          Container(width: 4, height: 38, decoration: BoxDecoration(color: color, borderRadius: AppRadii.pillR)),
          const SizedBox(width: AppSpace.m),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Flexible(child: Text(a.displayDriverName, style: AppText.label(), overflow: TextOverflow.ellipsis)),
                if (a.isSimulated) ...[const SizedBox(width: 6), const Pill('Simulated', color: AppColors.textMuted)],
              ]),
              const SizedBox(height: 2),
              Text(
                a.type == 'accident' ? 'Emergency SOS' : '${a.reasonLabel} · ${_ackText(a)}',
                style: AppText.caption(),
                overflow: TextOverflow.ellipsis,
              ),
            ]),
          ),
          const SizedBox(width: AppSpace.s),
          Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
            Text(Ist.hm(a.detectedAt), style: AppText.metric(size: 16)),
            const SizedBox(height: 4),
            if (lvl >= 3 && !a.acknowledged && a.type != 'accident')
              const Pill('Unacknowledged', color: AppColors.danger, solid: true)
            else if (a.type == 'accident')
              const Pill('SOS', color: AppColors.danger, solid: true)
            else
              LevelChip(lvl),
          ]),
        ]),
      ),
    );
    if (!fresh || AppMotion.reduced(context)) return item;
    return item.animate().fadeIn(duration: 350.ms).slideY(begin: -0.4, end: 0, curve: AppMotion.curve, duration: 350.ms);
  }

  static String _ackText(AlertItem a) {
    if (a.acknowledged) {
      return a.responseTimeMs != null ? 'acknowledged in ${Ist.duration(a.responseTimeMs)}' : 'acknowledged';
    }
    if (a.status == 'resolved') return 'cleared';
    return 'waiting for driver';
  }
}
