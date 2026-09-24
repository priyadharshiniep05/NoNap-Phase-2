import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../providers/fleet_provider.dart';
import '../../theme/app_colors.dart';
import '../../widgets/alert_tile.dart';

class FleetDriverDetailScreen extends ConsumerWidget {
  final String driverId;

  const FleetDriverDetailScreen({super.key, required this.driverId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final fleetData = ref.watch(fleetDataProvider);
    final overview = fleetData.overview;
    final driver = overview?.drivers.firstWhere(
      (d) => d.driverId == driverId,
      orElse: () => overview.drivers.first,
    );

    final driverAlerts = fleetData.alerts.where((a) => a.driverId == driverId).toList();

    return Scaffold(
      appBar: AppBar(
        title: Text(driver?.fullName ?? 'Driver Detail'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Driver Profile Header Card
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppColors.border),
              ),
              child: Column(
                children: [
                  CircleAvatar(
                    radius: 32,
                    backgroundColor: AppColors.cyan.withValues(alpha: 0.15),
                    child: const Icon(Icons.person, color: AppColors.cyan, size: 36),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    driver?.fullName ?? 'Driver',
                    style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    driver?.email ?? '',
                    style: const TextStyle(fontSize: 13, color: AppColors.textSecondary),
                  ),
                  const SizedBox(height: 16),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                    children: [
                      _MiniMetric(
                        label: 'Status',
                        value: driver?.currentStatus.toUpperCase() ?? 'OFFLINE',
                        color: driver?.currentStatus == 'drowsy' ? AppColors.drowsyRed : AppColors.alertGreen,
                      ),
                      _MiniMetric(
                        label: 'Alerts Today',
                        value: '${driver?.alertsToday ?? 0}',
                        color: AppColors.cyan,
                      ),
                      _MiniMetric(
                        label: 'PERCLOS',
                        value: '${((driver?.perclos ?? 0.0) * 100).toInt()}%',
                        color: AppColors.blue,
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),

            Text(
              'HISTORICAL ALERTS (${driverAlerts.length})',
              style: const TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w800,
                letterSpacing: 1.0,
                color: AppColors.textSecondary,
              ),
            ),
            const SizedBox(height: 12),

            if (driverAlerts.isEmpty)
              Container(
                padding: const EdgeInsets.all(32),
                child: const Center(
                  child: Text(
                    'No alerts recorded for this driver.',
                    style: TextStyle(color: AppColors.textMuted),
                  ),
                ),
              )
            else
              ...driverAlerts.map((a) => AlertTile(alert: a)),
          ],
        ),
      ),
    );
  }
}

class _MiniMetric extends StatelessWidget {
  final String label;
  final String value;
  final Color color;

  const _MiniMetric({required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(value, style: TextStyle(fontSize: 14, fontWeight: FontWeight.w800, color: color)),
        const SizedBox(height: 2),
        Text(label, style: const TextStyle(fontSize: 11, color: AppColors.textMuted)),
      ],
    );
  }
}
