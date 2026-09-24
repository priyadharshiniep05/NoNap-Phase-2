import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../providers/auth_provider.dart';
import '../../providers/telemetry_provider.dart';
import '../../providers/driver_provider.dart';
import '../../theme/app_colors.dart';
import '../../widgets/metric_gauge.dart';
import '../../widgets/status_hero_card.dart';
import '../../widgets/alert_tile.dart';
import '../../widgets/live_video_preview.dart';

class DriverDashboardScreen extends ConsumerStatefulWidget {
  const DriverDashboardScreen({super.key});

  @override
  ConsumerState<DriverDashboardScreen> createState() => _DriverDashboardScreenState();
}

class _DriverDashboardScreenState extends ConsumerState<DriverDashboardScreen> {
  bool _isCameraActive = true;

  @override
  void initState() {
    super.initState();
    // Auto-start webcam monitoring for driver on load
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _startMonitoring();
    });
  }

  Future<void> _startMonitoring() async {
    try {
      final user = ref.read(authProvider).user;
      await ref.read(apiServiceProvider).startMonitoring(driverId: user?.id);
      ref.read(telemetryProvider.notifier).setMonitoring(true);
      setState(() => _isCameraActive = true);
    } catch (_) {}
  }

  Future<void> _stopMonitoring() async {
    try {
      await ref.read(apiServiceProvider).stopMonitoring();
      ref.read(telemetryProvider.notifier).setMonitoring(false);
      setState(() => _isCameraActive = false);
    } catch (_) {}
  }

  Future<void> _triggerSos() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: const Text('Confirm Emergency SOS', style: TextStyle(color: AppColors.drowsyRed)),
        content: const Text(
          'This will immediately log a critical accident alert and notify the fleet manager and emergency dispatch.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel', style: TextStyle(color: AppColors.textMuted)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.drowsyRed),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('TRIGGER SOS'),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      final user = ref.read(authProvider).user;
      await ref.read(apiServiceProvider).reportAccidentSos(driverId: user?.id);
      ref.read(driverDataProvider.notifier).refresh();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            backgroundColor: AppColors.accidentDarkRed,
            content: Text('CRITICAL ACCIDENT SOS BROADCASTED!'),
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authProvider);
    final telemetry = ref.watch(telemetryProvider);
    final driverData = ref.watch(driverDataProvider);

    final latest = telemetry.latest;
    final currentStatus = latest?.status ?? 'alert';
    final currentMsg = latest?.message ?? 'Monitoring system active. Focused driving.';
    final currentTimestamp = latest?.timestamp ?? '';
    final ear = latest?.ear ?? 0.28;
    final mar = latest?.mar ?? 0.15;
    final perclos = latest?.perclos ?? 0.04;

    // Threshold references
    final earThresh = (driverData.thresholds?['ear_threshold'] as num?)?.toDouble() ?? 0.21;
    final marThresh = (driverData.thresholds?['mar_threshold'] as num?)?.toDouble() ?? 0.60;
    final perclosThresh = (driverData.thresholds?['perclos_threshold'] as num?)?.toDouble() ?? 0.40;

    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: AppColors.cyan.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AppColors.cyan.withValues(alpha: 0.4)),
              ),
              child: const Text(
                'DRIVER MODE',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w800,
                  color: AppColors.cyan,
                  letterSpacing: 0.8,
                ),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                authState.user?.fullName ?? 'Driver',
                style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.tune_rounded, color: AppColors.textSecondary),
            tooltip: 'Threshold Settings',
            onPressed: () => context.push('/driver/settings'),
          ),
          IconButton(
            icon: const Icon(Icons.history_rounded, color: AppColors.textSecondary),
            tooltip: 'Alert History',
            onPressed: () => context.push('/driver/history'),
          ),
          IconButton(
            icon: const Icon(Icons.logout_rounded, color: AppColors.textMuted),
            tooltip: 'Sign Out',
            onPressed: () => ref.read(authProvider.notifier).logout(),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          await ref.read(driverDataProvider.notifier).refresh();
        },
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // 1. Prominent Status Hero Card
              StatusHeroCard(
                status: currentStatus,
                message: currentMsg,
                timestamp: currentTimestamp,
                confidence: latest?.confidence ?? 0.95,
              ),
              const SizedBox(height: 16),

              // 2. Live Video Preview (MacBook Webcam via USB-C/LAN)
              if (_isCameraActive) ...[
                const LiveVideoPreview(),
                const SizedBox(height: 16),
              ],

              // 3. Real-Time Telemetry Gauges (EAR, MAR, PERCLOS)
              Row(
                children: [
                  Expanded(
                    child: MetricGauge(
                      label: 'EAR (Eyes)',
                      value: ear,
                      threshold: earThresh,
                      max: 0.45,
                      inverted: true, // Low EAR indicates closed eyes
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: MetricGauge(
                      label: 'MAR (Mouth)',
                      value: mar,
                      threshold: marThresh,
                      max: 1.20,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: MetricGauge(
                      label: 'PERCLOS',
                      value: perclos,
                      threshold: perclosThresh,
                      max: 1.0,
                      unit: '%',
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),

              // 4. Action Controls: Monitoring Toggle & SOS Accident Button
              Row(
                children: [
                  Expanded(
                    child: ElevatedButton.icon(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: _isCameraActive ? AppColors.surfaceElevated : AppColors.cyan,
                        foregroundColor: _isCameraActive ? Colors.white : AppColors.background,
                        padding: const EdgeInsets.symmetric(vertical: 14),
                      ),
                      onPressed: _isCameraActive ? _stopMonitoring : _startMonitoring,
                      icon: Icon(_isCameraActive ? Icons.videocam_off_rounded : Icons.videocam_rounded, size: 20),
                      label: Text(_isCameraActive ? 'Pause Camera' : 'Start Camera', style: const TextStyle(fontSize: 13)),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: ElevatedButton.icon(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.drowsyRed,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 14),
                      ),
                      onPressed: _triggerSos,
                      icon: const Icon(Icons.emergency_rounded, size: 20),
                      label: const Text('EMERGENCY SOS', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w900)),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 24),

              // 5. Recent Alerts & Notifications Feed
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text(
                    'RECENT NOTIFICATIONS',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 1.0,
                      color: AppColors.textSecondary,
                    ),
                  ),
                  TextButton(
                    onPressed: () => context.push('/driver/history'),
                    child: const Text('View All', style: TextStyle(fontSize: 12, color: AppColors.cyan)),
                  ),
                ],
              ),
              const SizedBox(height: 8),

              if (driverData.alerts.isEmpty)
                Container(
                  padding: const EdgeInsets.all(24),
                  decoration: BoxDecoration(
                    color: AppColors.surfaceSubtle,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppColors.border),
                  ),
                  child: const Center(
                    child: Text(
                      'No drowsiness alerts recorded. Great driving!',
                      style: TextStyle(color: AppColors.textMuted, fontSize: 13),
                    ),
                  ),
                )
              else
                ...driverData.alerts.take(5).map((a) => AlertTile(alert: a)),
            ],
          ),
        ),
      ),
    );
  }
}
