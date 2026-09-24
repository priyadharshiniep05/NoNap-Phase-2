import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../providers/driver_provider.dart';
import '../../theme/app_colors.dart';

class DriverSettingsScreen extends ConsumerStatefulWidget {
  const DriverSettingsScreen({super.key});

  @override
  ConsumerState<DriverSettingsScreen> createState() => _DriverSettingsScreenState();
}

class _DriverSettingsScreenState extends ConsumerState<DriverSettingsScreen> {
  double _ear = 0.21;
  double _mar = 0.60;
  double _perclos = 0.40;
  double _eyesClosedSec = 1.5;
  bool _initialized = false;
  bool _saving = false;

  void _loadFromState(Map<String, dynamic>? thresh) {
    if (thresh != null && !_initialized) {
      _ear = (thresh['ear_threshold'] as num?)?.toDouble() ?? 0.21;
      _mar = (thresh['mar_threshold'] as num?)?.toDouble() ?? 0.60;
      _perclos = (thresh['perclos_threshold'] as num?)?.toDouble() ?? 0.40;
      _eyesClosedSec = (thresh['eyes_closed_seconds'] as num?)?.toDouble() ?? 1.5;
      _initialized = true;
    }
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    await ref.read(driverDataProvider.notifier).updateThresholds({
      'ear_threshold': _ear,
      'mar_threshold': _mar,
      'perclos_threshold': _perclos,
      'eyes_closed_seconds': _eyesClosedSec,
    });
    setState(() => _saving = false);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          backgroundColor: AppColors.alertGreen,
          content: Text('Personal sensitivity thresholds saved!'),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final thresh = ref.watch(driverDataProvider).thresholds;
    _loadFromState(thresh);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Detection Sensitivity'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'Personal Calibration',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 6),
            const Text(
              'Adjust detection boundaries based on your individual eye shape and facial habits.',
              style: TextStyle(fontSize: 13, color: AppColors.textSecondary),
            ),
            const SizedBox(height: 24),

            // EAR Slider
            _buildSliderCard(
              title: 'Eye Aspect Ratio (EAR) Threshold',
              subtitle: 'Alert triggers when EAR drops below this value',
              value: _ear,
              min: 0.12,
              max: 0.35,
              divisions: 23,
              displayValue: _ear.toStringAsFixed(2),
              onChanged: (v) => setState(() => _ear = v),
            ),
            const SizedBox(height: 16),

            // MAR Slider
            _buildSliderCard(
              title: 'Mouth Aspect Ratio (MAR) Threshold',
              subtitle: 'Yawn alert triggers when mouth openness exceeds this',
              value: _mar,
              min: 0.40,
              max: 1.00,
              divisions: 30,
              displayValue: _mar.toStringAsFixed(2),
              onChanged: (v) => setState(() => _mar = v),
            ),
            const SizedBox(height: 16),

            // PERCLOS Slider
            _buildSliderCard(
              title: 'PERCLOS Rolling Threshold',
              subtitle: 'Percentage of eye closure over 30 seconds',
              value: _perclos,
              min: 0.20,
              max: 0.70,
              divisions: 25,
              displayValue: '${(_perclos * 100).toInt()}%',
              onChanged: (v) => setState(() => _perclos = v),
            ),
            const SizedBox(height: 16),

            // Duration Slider
            _buildSliderCard(
              title: 'Eyes-Closed Duration Trigger',
              subtitle: 'Continuous seconds of closed eyes before alarm',
              value: _eyesClosedSec,
              min: 1.0,
              max: 4.0,
              divisions: 15,
              displayValue: '${_eyesClosedSec.toStringAsFixed(1)}s',
              onChanged: (v) => setState(() => _eyesClosedSec = v),
            ),
            const SizedBox(height: 28),

            ElevatedButton(
              onPressed: _saving ? null : _save,
              child: _saving
                  ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Text('Save Sensitivity Settings'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSliderCard({
    required String title,
    required String subtitle,
    required double value,
    required double min,
    required double max,
    required int divisions,
    required String displayValue,
    required ValueChanged<double> onChanged,
  }) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: AppColors.cyan.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  displayValue,
                  style: const TextStyle(
                    fontWeight: FontWeight.w800,
                    color: AppColors.cyan,
                    fontSize: 14,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(subtitle, style: const TextStyle(fontSize: 11, color: AppColors.textSecondary)),
          const SizedBox(height: 12),
          SliderTheme(
            data: SliderTheme.of(context).copyWith(
              activeTrackColor: AppColors.cyan,
              inactiveTrackColor: AppColors.surfaceElevated,
              thumbColor: AppColors.cyan,
            ),
            child: Slider(
              value: value,
              min: min,
              max: max,
              divisions: divisions,
              onChanged: onChanged,
            ),
          ),
        ],
      ),
    );
  }
}
