import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../providers/fleet_provider.dart';
import '../../theme/app_colors.dart';

class FleetSettingsScreen extends ConsumerStatefulWidget {
  const FleetSettingsScreen({super.key});

  @override
  ConsumerState<FleetSettingsScreen> createState() => _FleetSettingsScreenState();
}

class _FleetSettingsScreenState extends ConsumerState<FleetSettingsScreen> {
  double _ear = 0.22;
  double _mar = 0.58;
  double _perclos = 0.38;
  double _eyesClosedSec = 1.4;
  bool _initialized = false;
  bool _saving = false;

  void _loadFromState(Map<String, dynamic>? thresh) {
    if (thresh != null && !_initialized) {
      _ear = (thresh['ear_threshold'] as num?)?.toDouble() ?? 0.22;
      _mar = (thresh['mar_threshold'] as num?)?.toDouble() ?? 0.58;
      _perclos = (thresh['perclos_threshold'] as num?)?.toDouble() ?? 0.38;
      _eyesClosedSec = (thresh['eyes_closed_seconds'] as num?)?.toDouble() ?? 1.4;
      _initialized = true;
    }
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    await ref.read(fleetDataProvider.notifier).updateThresholds({
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
          content: Text('Fleet-wide default thresholds updated!'),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final thresh = ref.watch(fleetDataProvider).thresholds;
    _loadFromState(thresh);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Fleet Thresholds'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'Fleet Default Policy',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 6),
            const Text(
              'These thresholds apply fleet-wide to any driver who has not set individual calibrations.',
              style: TextStyle(fontSize: 13, color: AppColors.textSecondary),
            ),
            const SizedBox(height: 24),

            _buildSlider(
              title: 'Default EAR (Eye Closure)',
              value: _ear,
              min: 0.12,
              max: 0.35,
              divisions: 23,
              display: _ear.toStringAsFixed(2),
              onChanged: (v) => setState(() => _ear = v),
            ),
            const SizedBox(height: 16),

            _buildSlider(
              title: 'Default MAR (Yawn Openness)',
              value: _mar,
              min: 0.40,
              max: 1.00,
              divisions: 30,
              display: _mar.toStringAsFixed(2),
              onChanged: (v) => setState(() => _mar = v),
            ),
            const SizedBox(height: 16),

            _buildSlider(
              title: 'Default PERCLOS Trigger',
              value: _perclos,
              min: 0.20,
              max: 0.70,
              divisions: 25,
              display: '${(_perclos * 100).toInt()}%',
              onChanged: (v) => setState(() => _perclos = v),
            ),
            const SizedBox(height: 16),

            _buildSlider(
              title: 'Default Eyes-Closed Duration',
              value: _eyesClosedSec,
              min: 1.0,
              max: 4.0,
              divisions: 15,
              display: '${_eyesClosedSec.toStringAsFixed(1)}s',
              onChanged: (v) => setState(() => _eyesClosedSec = v),
            ),
            const SizedBox(height: 28),

            ElevatedButton(
              onPressed: _saving ? null : _save,
              child: _saving
                  ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Text('Save Fleet Policy'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSlider({
    required String title,
    required double value,
    required double min,
    required double max,
    required int divisions,
    required String display,
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
              Text(title, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
              Text(display, style: const TextStyle(fontWeight: FontWeight.w800, color: AppColors.blue, fontSize: 14)),
            ],
          ),
          const SizedBox(height: 10),
          SliderTheme(
            data: SliderTheme.of(context).copyWith(
              activeTrackColor: AppColors.blue,
              inactiveTrackColor: AppColors.surfaceElevated,
              thumbColor: AppColors.blue,
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
