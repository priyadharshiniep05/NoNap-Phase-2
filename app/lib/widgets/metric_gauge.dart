import 'package:flutter/material.dart';
import '../theme/app_colors.dart';

class MetricGauge extends StatelessWidget {
  final String label;
  final double value;
  final double threshold;
  final double max;
  final String unit;
  final bool inverted; // If true, lower than threshold is bad (e.g. EAR). If false, higher is bad (e.g. MAR, PERCLOS)

  const MetricGauge({
    super.key,
    required this.label,
    required this.value,
    required this.threshold,
    this.max = 1.0,
    this.unit = '',
    this.inverted = false,
  });

  bool get isWarning {
    if (inverted) {
      return value < threshold && value > 0.0;
    } else {
      return value > threshold;
    }
  }

  @override
  Widget build(BuildContext context) {
    final progress = (value / max).clamp(0.0, 1.0);
    final indicatorColor = isWarning
        ? (inverted ? AppColors.drowsyRed : AppColors.yawnAmber)
        : AppColors.cyan;

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.surfaceSubtle,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isWarning ? indicatorColor.withValues(alpha: 0.5) : AppColors.border,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                label,
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textSecondary,
                ),
              ),
              Text(
                'Thresh: ${threshold.toStringAsFixed(2)}',
                style: const TextStyle(
                  fontSize: 10,
                  color: AppColors.textMuted,
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Row(
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              Text(
                value.toStringAsFixed(2),
                style: TextStyle(
                  fontSize: 22,
                  fontWeight: FontWeight.w800,
                  color: isWarning ? indicatorColor : AppColors.textPrimary,
                ),
              ),
              if (unit.isNotEmpty) ...[
                const SizedBox(width: 4),
                Text(
                  unit,
                  style: const TextStyle(fontSize: 12, color: AppColors.textMuted),
                ),
              ],
            ],
          ),
          const SizedBox(height: 8),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: progress,
              backgroundColor: AppColors.surfaceElevated,
              valueColor: AlwaysStoppedAnimation<Color>(indicatorColor),
              minHeight: 6,
            ),
          ),
        ],
      ),
    );
  }
}
