import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../core/ist.dart';
import '../../models/alert_item.dart';
import '../../providers/driver_provider.dart';
import '../../theme/tokens.dart';
import '../../theme/typography.dart';
import '../../widgets/alert_timeline.dart';
import '../../widgets/ui.dart';

/// Alerts per IST hour of day (pure, unit-tested).
List<int> alertsByHour(Iterable<AlertItem> alerts) {
  final counts = List<int>.filled(24, 0);
  for (final a in alerts) {
    counts[Ist.hour(a.detectedAt)]++;
  }
  return counts;
}

/// Group alerts (newest first) under "Today", "Yesterday", "Mon, 19 Oct"...
List<MapEntry<String, List<AlertItem>>> groupByDay(List<AlertItem> alerts) {
  final groups = <String, List<AlertItem>>{};
  for (final a in alerts) {
    groups.putIfAbsent(Ist.dayLabel(a.detectedAt), () => []).add(a);
  }
  return groups.entries.toList();
}

class DriverHistoryScreen extends ConsumerStatefulWidget {
  const DriverHistoryScreen({super.key});

  @override
  ConsumerState<DriverHistoryScreen> createState() => _DriverHistoryScreenState();
}

class _DriverHistoryScreenState extends ConsumerState<DriverHistoryScreen> {
  String _filter = 'all'; // all | serious | yawning

  @override
  Widget build(BuildContext context) {
    final data = ref.watch(driverDataProvider);
    final all = data.alerts.where((a) => a.type != 'accident').toList();
    final shown = switch (_filter) {
      'serious' => all.where((a) => a.effectiveLevel >= 2).toList(),
      'yawning' => all.where((a) => a.type == 'yawning').toList(),
      _ => all,
    };
    final timed = all.where((a) => a.responseTimeMs != null).toList();
    final avg = timed.isEmpty ? null : timed.map((a) => a.responseTimeMs!).reduce((x, y) => x + y) / timed.length;
    final todayCount = all.where((a) => Ist.dayLabel(a.detectedAt) == 'Today').length;

    Widget body;
    if (!data.loaded && data.isLoading) {
      body = const Padding(padding: EdgeInsets.all(AppSpace.gutter), child: SkeletonList(count: 6));
    } else if (!data.loaded && data.error != null) {
      body = ErrorState(message: data.error!, onRetry: () => ref.read(driverDataProvider.notifier).refresh());
    } else {
      final groups = groupByDay(shown);
      body = ListView(
        padding: const EdgeInsets.fromLTRB(AppSpace.gutter, AppSpace.s, AppSpace.gutter, AppSpace.xxxl),
        children: [
          Row(children: [
            Expanded(child: StatTile(label: 'Today', value: '$todayCount', icon: PhosphorIconsRegular.calendarBlank)),
            const SizedBox(width: AppSpace.m),
            Expanded(child: StatTile(label: 'All alerts', value: '${all.length}', icon: PhosphorIconsRegular.bellRinging, color: AppColors.warning)),
            const SizedBox(width: AppSpace.m),
            Expanded(
              child: StatTile(label: 'Avg. response', value: Ist.duration(avg), icon: PhosphorIconsRegular.timer, color: AppColors.success),
            ),
          ]),
          const SectionHeader('When you get drowsy'),
          _HourChart(counts: alertsByHour(all)),
          SectionHeader('Timeline', trailing: _Filters(value: _filter, onChanged: (v) => setState(() => _filter = v))),
          if (shown.isEmpty)
            EmptyState(
              icon: PhosphorIconsRegular.sealCheck,
              message: all.isEmpty ? 'No alerts yet' : 'Nothing in this filter',
              detail: all.isEmpty ? 'Drowsiness alerts will appear here. Drive safe.' : null,
            )
          else
            for (final g in groups) ...[
              Padding(
                padding: const EdgeInsets.only(top: AppSpace.s, bottom: AppSpace.s),
                child: Text(g.key, style: AppText.label(color: AppColors.textSecondary)),
              ),
              for (var i = 0; i < g.value.length; i++)
                AlertTimelineEntry(alert: g.value[i], last: i == g.value.length - 1)
                    .animate()
                    .fadeIn(duration: AppMotion.of(context, AppMotion.medium), delay: AppMotion.of(context, Duration(milliseconds: 30 * i.clamp(0, 8)))),
            ],
        ],
      );
    }

    return Scaffold(
      appBar: AppBar(title: const Text('Alert history')),
      extendBodyBehindAppBar: false,
      backgroundColor: AppColors.background,
      body: PageBackground(
        child: RefreshIndicator(
          color: AppColors.primary,
          backgroundColor: AppColors.surface,
          onRefresh: () => ref.read(driverDataProvider.notifier).refresh(),
          child: body,
        ),
      ),
    );
  }
}

class _Filters extends StatelessWidget {
  final String value;
  final ValueChanged<String> onChanged;
  const _Filters({required this.value, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    Widget chip(String id, String label) {
      final on = value == id;
      return Padding(
        padding: const EdgeInsets.only(left: 6),
        child: ChoiceChip(
          label: Text(label, style: AppText.caption(color: on ? AppColors.onPrimary : AppColors.textSecondary)),
          selected: on,
          showCheckmark: false,
          selectedColor: AppColors.primary,
          backgroundColor: AppColors.surface,
          side: BorderSide(color: on ? AppColors.primary : AppColors.border),
          shape: const StadiumBorder(),
          visualDensity: VisualDensity.compact,
          onSelected: (_) => onChanged(id),
        ),
      );
    }

    return Row(mainAxisSize: MainAxisSize.min, children: [chip('all', 'All'), chip('serious', 'Level 2+'), chip('yawning', 'Yawns')]);
  }
}

class _HourChart extends StatelessWidget {
  final List<int> counts;
  const _HourChart({required this.counts});

  @override
  Widget build(BuildContext context) {
    final maxC = counts.reduce((a, b) => a > b ? a : b);
    final peak = maxC == 0 ? -1 : counts.indexOf(maxC);
    return GlassCard(
      padding: const EdgeInsets.fromLTRB(AppSpace.m, AppSpace.l, AppSpace.m, AppSpace.s),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: AppSpace.xs),
          child: Text(
            peak < 0 ? 'No alerts recorded yet' : 'Most alerts around ${peak.toString().padLeft(2, '0')}:00 IST',
            style: AppText.label(),
          ),
        ),
        const SizedBox(height: AppSpace.m),
        SizedBox(
          height: 120,
          child: BarChart(
            BarChartData(
              maxY: (maxC == 0 ? 1 : maxC).toDouble() * 1.15,
              alignment: BarChartAlignment.spaceBetween,
              gridData: const FlGridData(show: false),
              borderData: FlBorderData(show: false),
              barTouchData: BarTouchData(
                touchTooltipData: BarTouchTooltipData(
                  getTooltipColor: (_) => AppColors.surfaceRaised,
                  getTooltipItem: (g, _, r, _) => BarTooltipItem(
                    '${g.x.toString().padLeft(2, '0')}:00 · ${r.toY.toInt()}',
                    AppText.caption(color: AppColors.textPrimary),
                  ),
                ),
              ),
              titlesData: FlTitlesData(
                leftTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                bottomTitles: AxisTitles(
                  sideTitles: SideTitles(
                    showTitles: true,
                    reservedSize: 20,
                    getTitlesWidget: (v, _) => v.toInt() % 6 == 0
                        ? Text(v.toInt().toString().padLeft(2, '0'), style: AppText.caption().copyWith(fontSize: 10))
                        : const SizedBox.shrink(),
                  ),
                ),
              ),
              barGroups: [
                for (var h = 0; h < 24; h++)
                  BarChartGroupData(x: h, barRods: [
                    BarChartRodData(
                      toY: counts[h].toDouble(),
                      width: 7,
                      borderRadius: const BorderRadius.vertical(top: Radius.circular(3)),
                      gradient: LinearGradient(
                        begin: Alignment.bottomCenter,
                        end: Alignment.topCenter,
                        colors: h == peak
                            ? [AppColors.warning.withValues(alpha: 0.5), AppColors.warning]
                            : [AppColors.primary.withValues(alpha: 0.35), AppColors.primary],
                      ),
                      backDrawRodData: BackgroundBarChartRodData(
                        show: true,
                        toY: (maxC == 0 ? 1 : maxC).toDouble() * 1.15,
                        color: AppColors.surfaceRaised.withValues(alpha: 0.35),
                      ),
                    ),
                  ]),
              ],
            ),
          ),
        ),
      ]),
    );
  }
}
