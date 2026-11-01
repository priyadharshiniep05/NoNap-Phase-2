import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../core/ist.dart';
import '../../models/fleet_overview.dart';
import '../../providers/fleet_provider.dart';
import '../../theme/tokens.dart';
import '../../theme/typography.dart';
import '../../widgets/alert_timeline.dart';
import '../../widgets/ui.dart';
import 'fleet_dashboard_screen.dart' show statusColor, statusLabel;

class FleetDriverDetailScreen extends ConsumerWidget {
  final String driverId;
  const FleetDriverDetailScreen({super.key, required this.driverId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final fleet = ref.watch(fleetDataProvider);
    final timeline = ref.watch(fleetDriverAlertsProvider(driverId));
    FleetDriverItem? d;
    for (final x in fleet.overview?.drivers ?? const <FleetDriverItem>[]) {
      if (x.driverId == driverId) d = x;
    }

    // Live alerts from the feed take precedence over the fetched copy.
    final live = {for (final a in fleet.alerts.where((a) => a.driverId == driverId)) a.id: a};

    return Scaffold(
      appBar: AppBar(title: Text(d?.displayName ?? 'Driver')),
      body: PageBackground(
        child: RefreshIndicator(
          color: AppColors.primary,
          backgroundColor: AppColors.surface,
          onRefresh: () async => ref.invalidate(fleetDriverAlertsProvider(driverId)),
          child: ListView(padding: const EdgeInsets.fromLTRB(AppSpace.gutter, AppSpace.s, AppSpace.gutter, AppSpace.xxxl), children: [
            if (d == null)
              const Skeleton(height: 120)
            else
              GlassCard(
                glow: d.inActiveAlert ? AppColors.danger : null,
                borderColor: d.inActiveAlert ? AppColors.danger : AppColors.border,
                child: Row(children: [
                  InitialsAvatar(name: d.fullName, size: 60, ring: statusColor(d)),
                  const SizedBox(width: AppSpace.l),
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(d.displayName, style: AppText.title()),
                      Text(d.vehicle ?? 'No vehicle assigned', style: AppText.caption()),
                      const SizedBox(height: AppSpace.s),
                      Row(children: [
                        StatusDot(color: statusColor(d), pulse: d.online),
                        const SizedBox(width: 6),
                        Text(statusLabel(d), style: AppText.caption(color: statusColor(d)).copyWith(fontWeight: FontWeight.w700)),
                      ]),
                    ]),
                  ),
                ]),
              ),
            const SizedBox(height: AppSpace.m),
            if (d != null)
              Row(children: [
                Expanded(child: StatTile(label: 'Alerts today', value: '${d.alertsToday}', icon: PhosphorIconsRegular.calendarBlank, color: AppColors.warning)),
                const SizedBox(width: AppSpace.m),
                Expanded(child: StatTile(label: 'Avg. response', value: Ist.duration(d.avgResponseMs), icon: PhosphorIconsRegular.timer)),
                const SizedBox(width: AppSpace.m),
                Expanded(
                  child: StatTile(
                    label: 'Pi camera',
                    value: d.deviceOnline ? (d.fps != null ? '${d.fps!.toStringAsFixed(1)} fps' : 'On') : 'Off',
                    sub: d.cpuTempC != null && d.deviceOnline ? '${d.cpuTempC!.round()}°C' : null,
                    icon: PhosphorIconsRegular.camera,
                    color: d.deviceOnline ? AppColors.success : AppColors.textMuted,
                  ),
                ),
              ]),
            const SectionHeader('Timeline'),
            timeline.when(
              loading: () => const SkeletonList(count: 4),
              error: (e, _) => ErrorState(
                message: 'Could not load this driver\'s alerts.',
                onRetry: () => ref.invalidate(fleetDriverAlertsProvider(driverId)),
              ),
              data: (alerts) {
                final merged = {for (final a in alerts) a.id: a, ...live}.values.toList()
                  ..sort((a, b) => b.detectedAt.compareTo(a.detectedAt));
                if (merged.isEmpty) {
                  return const EmptyState(icon: PhosphorIconsRegular.sealCheck, message: 'No alerts for this driver');
                }
                final rows = <Widget>[];
                String? day;
                for (var i = 0; i < merged.length; i++) {
                  final label = Ist.dayLabel(merged[i].detectedAt);
                  if (label != day) {
                    day = label;
                    rows.add(Padding(
                      padding: const EdgeInsets.symmetric(vertical: AppSpace.s),
                      child: Text(label, style: AppText.label(color: AppColors.textSecondary)),
                    ));
                  }
                  final nextSameDay = i + 1 < merged.length && Ist.dayLabel(merged[i + 1].detectedAt) == label;
                  rows.add(AlertTimelineEntry(alert: merged[i], last: !nextSameDay, driverView: false));
                }
                return Column(crossAxisAlignment: CrossAxisAlignment.start, children: rows);
              },
            ),
          ]),
        ),
      ),
    );
  }
}
