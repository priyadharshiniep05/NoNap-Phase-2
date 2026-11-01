import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../providers/driver_live_provider.dart';
import '../theme/tokens.dart';
import '../theme/typography.dart';
import 'ui.dart';

/// EAR / MAR card: big number, personal threshold, 60 s sparkline.
class MetricCard extends StatelessWidget {
  final String label;
  final String hint;
  final double? value;
  final double threshold;
  final List<SeriesPoint> series;
  final bool lowIsBad; // EAR: below threshold is bad. MAR: above is bad.
  final double floorMax;

  const MetricCard({
    super.key,
    required this.label,
    required this.hint,
    required this.value,
    required this.threshold,
    required this.series,
    required this.lowIsBad,
    required this.floorMax,
  });

  bool get _bad => value != null && (lowIsBad ? value! < threshold : value! > threshold);

  @override
  Widget build(BuildContext context) {
    final color = _bad ? AppColors.warning : AppColors.primary;
    final now = DateTime.now().millisecondsSinceEpoch;
    final maxSeen = series.isEmpty ? 0.0 : series.map((p) => p.v).reduce((a, b) => a > b ? a : b);
    final maxY = [floorMax, threshold * 1.5, maxSeen * 1.15].reduce((a, b) => a > b ? a : b);

    return GlassCard(
      padding: const EdgeInsets.fromLTRB(AppSpace.l, AppSpace.l, AppSpace.l, AppSpace.m),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Text(label, style: AppText.overline(color: AppColors.textSecondary)),
          const Spacer(),
          Text(hint, style: AppText.caption()),
        ]),
        const SizedBox(height: AppSpace.s),
        Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
          AnimatedDefaultTextStyle(
            duration: AppMotion.of(context, AppMotion.fast),
            style: AppText.metric(color: _bad ? AppColors.warning : AppColors.textPrimary),
            child: Text(value == null ? '—' : value!.toStringAsFixed(2)),
          ),
          const SizedBox(width: AppSpace.s),
          Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Text('limit ${threshold.toStringAsFixed(2)}', style: AppText.caption()),
          ),
        ]),
        const SizedBox(height: AppSpace.m),
        SizedBox(
          height: 56,
          child: series.length < 2
              ? Center(child: Text('Waiting for live data', style: AppText.caption()))
              : LineChart(
                  duration: Duration.zero,
                  LineChartData(
                    // Span the data until a full minute exists, then slide a 60 s window.
                    minX: (series.first.t > now - 60000 ? series.first.t : now - 60000).toDouble(),
                    maxX: now.toDouble(),
                    minY: 0,
                    maxY: maxY,
                    clipData: const FlClipData.all(),
                    gridData: const FlGridData(show: false),
                    borderData: FlBorderData(show: false),
                    titlesData: const FlTitlesData(show: false),
                    lineTouchData: const LineTouchData(enabled: false),
                    extraLinesData: ExtraLinesData(horizontalLines: [
                      HorizontalLine(
                        y: threshold,
                        color: AppColors.textMuted.withValues(alpha: 0.8),
                        strokeWidth: 1,
                        dashArray: [4, 4],
                      ),
                    ]),
                    lineBarsData: [
                      LineChartBarData(
                        spots: [for (final p in series) FlSpot(p.t.toDouble(), p.v)],
                        isCurved: true,
                        curveSmoothness: 0.25,
                        preventCurveOverShooting: true,
                        color: color,
                        barWidth: 2.4,
                        isStrokeCapRound: true,
                        dotData: const FlDotData(show: false),
                        belowBarData: BarAreaData(
                          show: true,
                          gradient: LinearGradient(
                            begin: Alignment.topCenter,
                            end: Alignment.bottomCenter,
                            colors: [color.withValues(alpha: 0.30), color.withValues(alpha: 0.0)],
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
        ),
      ]),
    );
  }
}
