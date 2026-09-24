import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../providers/auth_provider.dart';
import '../../providers/fleet_provider.dart';
import '../../theme/app_colors.dart';
import '../../models/fleet_overview.dart';
import '../../widgets/alert_tile.dart';

class FleetDashboardScreen extends ConsumerWidget {
  const FleetDashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final fleetData = ref.watch(fleetDataProvider);
    final overview = fleetData.overview;

    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: AppColors.blue.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AppColors.blue.withValues(alpha: 0.4)),
              ),
              child: const Text(
                'FLEET MANAGEMENT',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w800,
                  color: AppColors.blue,
                  letterSpacing: 0.8,
                ),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                overview?.fleetName ?? 'Apex Logistics',
                style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.tune_rounded, color: AppColors.textSecondary),
            tooltip: 'Fleet Thresholds',
            onPressed: () => context.push('/fleet/settings'),
          ),
          IconButton(
            icon: const Icon(Icons.logout_rounded, color: AppColors.textMuted),
            tooltip: 'Sign Out',
            onPressed: () => ref.read(authProvider.notifier).logout(),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () => ref.read(fleetDataProvider.notifier).refresh(),
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // 1. High-Level Metrics
              Row(
                children: [
                  Expanded(
                    child: _MetricCard(
                      label: 'Active Drivers',
                      value: '${overview?.activeDrivers ?? 0}/${overview?.totalDrivers ?? 0}',
                      icon: Icons.directions_car_filled_rounded,
                      color: AppColors.cyan,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: _MetricCard(
                      label: 'Drowsy Today',
                      value: '${overview?.drowsyCountToday ?? 0}',
                      icon: Icons.bedtime_rounded,
                      color: AppColors.drowsyRed,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: _MetricCard(
                      label: 'Critical / SOS',
                      value: '${overview?.criticalAlertsToday ?? 0}',
                      icon: Icons.emergency_rounded,
                      color: AppColors.accidentDarkRed,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 24),

              // 2. Active Driver Fleet Grid / List
              const Text(
                'MONITORED DRIVERS',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 1.0,
                  color: AppColors.textSecondary,
                ),
              ),
              const SizedBox(height: 12),

              if (overview == null || overview.drivers.isEmpty)
                Container(
                  padding: const EdgeInsets.all(24),
                  decoration: BoxDecoration(
                    color: AppColors.surface,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppColors.border),
                  ),
                  child: const Center(
                    child: Text('No drivers registered in fleet.', style: TextStyle(color: AppColors.textMuted)),
                  ),
                )
              else
                ...overview.drivers.map((d) => _DriverCard(
                      driver: d,
                      onTap: () => context.push('/fleet/driver/${d.driverId}'),
                    )),

              const SizedBox(height: 24),

              // 3. Real-Time Fleet Alert Feed
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text(
                    'RECENT FLEET ALERTS',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 1.0,
                      color: AppColors.textSecondary,
                    ),
                  ),
                  Text(
                    '${fleetData.alerts.length} total',
                    style: const TextStyle(fontSize: 11, color: AppColors.textMuted),
                  ),
                ],
              ),
              const SizedBox(height: 12),

              if (fleetData.alerts.isEmpty)
                Container(
                  padding: const EdgeInsets.all(24),
                  decoration: BoxDecoration(
                    color: AppColors.surface,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppColors.border),
                  ),
                  child: const Center(
                    child: Text('No recent fleet alerts logged.', style: TextStyle(color: AppColors.textMuted)),
                  ),
                )
              else
                ...fleetData.alerts.take(15).map((a) => AlertTile(alert: a, showDriverName: true)),
            ],
          ),
        ),
      ),
    );
  }
}

class _MetricCard extends StatelessWidget {
  final String label;
  final String value;
  final IconData icon;
  final Color color;

  const _MetricCard({
    required this.label,
    required this.value,
    required this.icon,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 12),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color, size: 20),
          const SizedBox(height: 8),
          Text(value, style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900, color: color)),
          const SizedBox(height: 2),
          Text(label, style: const TextStyle(fontSize: 10, color: AppColors.textSecondary)),
        ],
      ),
    );
  }
}

class _DriverCard extends StatelessWidget {
  final FleetDriverItem driver;
  final VoidCallback onTap;

  const _DriverCard({required this.driver, required this.onTap});

  Color _getStatusColor() {
    switch (driver.currentStatus.toLowerCase()) {
      case 'drowsy':
        return AppColors.drowsyRed;
      case 'yawning':
        return AppColors.yawnAmber;
      case 'accident':
        return AppColors.accidentDarkRed;
      case 'offline':
        return AppColors.textMuted;
      case 'alert':
      default:
        return AppColors.alertGreen;
    }
  }

  @override
  Widget build(BuildContext context) {
    final statusColor = _getStatusColor();

    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: driver.currentStatus == 'drowsy'
                ? AppColors.drowsyRed
                : AppColors.border,
            width: driver.currentStatus == 'drowsy' ? 2 : 1,
          ),
        ),
        child: Row(
          children: [
            CircleAvatar(
              backgroundColor: statusColor.withValues(alpha: 0.15),
              radius: 20,
              child: Icon(Icons.person, color: statusColor, size: 22),
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
                        driver.fullName,
                        style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: statusColor.withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(6),
                          border: Border.all(color: statusColor.withValues(alpha: 0.4)),
                        ),
                        child: Text(
                          driver.currentStatus.toUpperCase(),
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w800,
                            color: statusColor,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Row(
                    children: [
                      Text(
                        'PERCLOS: ${(driver.perclos * 100).toInt()}%  •  EAR: ${driver.ear.toStringAsFixed(2)}  •  ${driver.alertsToday} alerts today',
                        style: const TextStyle(fontSize: 11, color: AppColors.textSecondary),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            const Icon(Icons.chevron_right_rounded, color: AppColors.textMuted),
          ],
        ),
      ),
    );
  }
}
