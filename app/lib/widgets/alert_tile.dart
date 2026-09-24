import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../models/alert_item.dart';
import '../theme/app_colors.dart';

class AlertTile extends StatelessWidget {
  final AlertItem alert;
  final bool showDriverName;

  const AlertTile({
    super.key,
    required this.alert,
    this.showDriverName = false,
  });

  Color _getTypeColor() {
    switch (alert.type.toLowerCase()) {
      case 'drowsy':
        return AppColors.drowsyRed;
      case 'yawning':
        return AppColors.yawnAmber;
      case 'accident':
        return AppColors.accidentDarkRed;
      default:
        return AppColors.cyan;
    }
  }

  IconData _getTypeIcon() {
    switch (alert.type.toLowerCase()) {
      case 'drowsy':
        return Icons.warning_amber_rounded;
      case 'yawning':
        return Icons.bedtime_outlined;
      case 'accident':
        return Icons.emergency_outlined;
      default:
        return Icons.info_outline;
    }
  }

  @override
  Widget build(BuildContext context) {
    final typeColor = _getTypeColor();
    final timeStr = DateFormat('MMM d, HH:mm').format(alert.detectedAt.toLocal());

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.border),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: typeColor.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(
              _getTypeIcon(),
              color: typeColor,
              size: 22,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      showDriverName && alert.driverName != null
                          ? alert.driverName!
                          : alert.type.toUpperCase(),
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                        color: typeColor,
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                        color: typeColor.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        alert.severity.toUpperCase(),
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w800,
                          color: typeColor,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  showDriverName
                      ? '${alert.type.toUpperCase()} at $timeStr'
                      : 'You were ${alert.type} at ${DateFormat('HH:mm').format(alert.detectedAt.toLocal())}',
                  style: const TextStyle(
                    fontSize: 12,
                    color: AppColors.textPrimary,
                  ),
                ),
                const SizedBox(height: 4),
                Row(
                  children: [
                    Text(
                      'EAR: ${alert.ear.toStringAsFixed(2)}  •  MAR: ${alert.mar.toStringAsFixed(2)}  •  PERCLOS: ${alert.perclos.toStringAsFixed(2)}',
                      style: const TextStyle(
                        fontSize: 11,
                        color: AppColors.textMuted,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
