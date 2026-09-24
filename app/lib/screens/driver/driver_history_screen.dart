import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../providers/driver_provider.dart';
import '../../theme/app_colors.dart';
import '../../widgets/alert_tile.dart';

class DriverHistoryScreen extends ConsumerStatefulWidget {
  const DriverHistoryScreen({super.key});

  @override
  ConsumerState<DriverHistoryScreen> createState() => _DriverHistoryScreenState();
}

class _DriverHistoryScreenState extends ConsumerState<DriverHistoryScreen> {
  String _selectedFilter = 'all';

  @override
  Widget build(BuildContext context) {
    final driverData = ref.watch(driverDataProvider);
    final stats = driverData.stats ?? {};
    final alerts = driverData.alerts;

    final filteredAlerts = alerts.where((a) {
      if (_selectedFilter == 'all') return true;
      return a.type == _selectedFilter;
    }).toList();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Alert History & Stats'),
      ),
      body: RefreshIndicator(
        onRefresh: () => ref.read(driverDataProvider.notifier).refresh(),
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Summary Stats Row
              Row(
                children: [
                  Expanded(
                    child: _StatCard(
                      label: 'Total Alerts',
                      value: '${stats['total_alerts'] ?? alerts.length}',
                      color: AppColors.cyan,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: _StatCard(
                      label: 'Drowsy',
                      value: '${stats['drowsy_alerts'] ?? alerts.where((a) => a.type == 'drowsy').length}',
                      color: AppColors.drowsyRed,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: _StatCard(
                      label: 'Yawning',
                      value: '${stats['yawn_alerts'] ?? alerts.where((a) => a.type == 'yawning').length}',
                      color: AppColors.yawnAmber,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: _StatCard(
                      label: 'Accident',
                      value: '${stats['accident_alerts'] ?? alerts.where((a) => a.type == 'accident').length}',
                      color: AppColors.accidentDarkRed,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 20),

              // Filter Chips
              SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Row(
                  children: [
                    _FilterChip(
                      label: 'All (${alerts.length})',
                      isSelected: _selectedFilter == 'all',
                      onTap: () => setState(() => _selectedFilter = 'all'),
                    ),
                    const SizedBox(width: 8),
                    _FilterChip(
                      label: 'Drowsy',
                      isSelected: _selectedFilter == 'drowsy',
                      onTap: () => setState(() => _selectedFilter = 'drowsy'),
                    ),
                    const SizedBox(width: 8),
                    _FilterChip(
                      label: 'Yawning',
                      isSelected: _selectedFilter == 'yawning',
                      onTap: () => setState(() => _selectedFilter = 'yawning'),
                    ),
                    const SizedBox(width: 8),
                    _FilterChip(
                      label: 'Accident',
                      isSelected: _selectedFilter == 'accident',
                      onTap: () => setState(() => _selectedFilter = 'accident'),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),

              // Alerts List
              if (filteredAlerts.isEmpty)
                Container(
                  padding: const EdgeInsets.all(32),
                  child: const Center(
                    child: Text(
                      'No matching alerts found.',
                      style: TextStyle(color: AppColors.textMuted, fontSize: 14),
                    ),
                  ),
                )
              else
                ...filteredAlerts.map((a) => AlertTile(alert: a)),
            ],
          ),
        ),
      ),
    );
  }
}

class _StatCard extends StatelessWidget {
  final String label;
  final String value;
  final Color color;

  const _StatCard({required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 8),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        children: [
          Text(value, style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: color)),
          const SizedBox(height: 2),
          Text(label, style: const TextStyle(fontSize: 10, color: AppColors.textSecondary), textAlign: TextAlign.center),
        ],
      ),
    );
  }
}

class _FilterChip extends StatelessWidget {
  final String label;
  final bool isSelected;
  final VoidCallback onTap;

  const _FilterChip({required this.label, required this.isSelected, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: isSelected ? AppColors.cyan : AppColors.surfaceSubtle,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: isSelected ? AppColors.cyan : AppColors.border),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.bold,
            color: isSelected ? AppColors.background : AppColors.textSecondary,
          ),
        ),
      ),
    );
  }
}
