import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../providers/auth_provider.dart';
import '../../providers/driver_provider.dart';
import '../../theme/tokens.dart';
import '../../theme/typography.dart';
import '../../widgets/server_config_dialog.dart';
import '../../widgets/ui.dart';

class DriverSettingsScreen extends ConsumerStatefulWidget {
  const DriverSettingsScreen({super.key});

  @override
  ConsumerState<DriverSettingsScreen> createState() => _DriverSettingsScreenState();
}

class _DriverSettingsScreenState extends ConsumerState<DriverSettingsScreen> {
  double? _ear;
  double? _mar;
  bool _saving = false;

  Future<void> _save() async {
    setState(() => _saving = true);
    final err = await ref.read(driverDataProvider.notifier).updateThresholds({
      if (_ear != null) 'ear_threshold': double.parse(_ear!.toStringAsFixed(3)),
      if (_mar != null) 'mar_threshold': double.parse(_mar!.toStringAsFixed(3)),
    });
    if (!mounted) return;
    setState(() => _saving = false);
    showToast(context, err ?? 'Thresholds saved', error: err != null);
  }

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(authProvider).user;
    final data = ref.watch(driverDataProvider);
    final api = ref.watch(apiServiceProvider);
    final ear = _ear ?? data.earThreshold;
    final mar = _mar ?? data.marThreshold;

    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: PageBackground(
        child: ListView(padding: const EdgeInsets.fromLTRB(AppSpace.gutter, AppSpace.s, AppSpace.gutter, AppSpace.xxxl), children: [
          GlassCard(
            child: Row(children: [
              InitialsAvatar(name: user?.fullName ?? '?', size: 52),
              const SizedBox(width: AppSpace.l),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(user?.fullName ?? '', style: AppText.title()),
                  Text(user?.email ?? '', style: AppText.caption()),
                  const SizedBox(height: 6),
                  const Pill('Driver', color: AppColors.primary),
                ]),
              ),
            ]),
          ),
          const SectionHeader('Personal thresholds'),
          GlassCard(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              _SliderRow(
                label: 'Eye closed below (EAR)',
                value: ear,
                min: 0.10,
                max: 0.35,
                onChanged: (v) => setState(() => _ear = v),
                help: 'Lower = only very closed eyes count',
              ),
              const Divider(height: AppSpace.xl),
              _SliderRow(
                label: 'Yawn above (MAR)',
                value: mar,
                min: 0.40,
                max: 1.20,
                onChanged: (v) => setState(() => _mar = v),
                help: 'Higher = only wide yawns count',
              ),
              const SizedBox(height: AppSpace.m),
              Text(
                'Level 1 after 1 s of closed eyes or a 1 s yawn · Level 2 after 2 s · Level 3 if not acknowledged in 10 s.',
                style: AppText.caption(),
              ),
              const SizedBox(height: AppSpace.l),
              Row(children: [
                Expanded(
                  child: GhostButton(
                    label: 'Recalibrate',
                    icon: PhosphorIconsRegular.target,
                    color: AppColors.primary,
                    onPressed: () => context.push('/driver/calibration'),
                  ),
                ),
                const SizedBox(width: AppSpace.m),
                Expanded(
                  child: GradientButton(
                    label: 'Save',
                    height: 52,
                    loading: _saving,
                    onPressed: (_ear == null && _mar == null) ? null : _save,
                  ),
                ),
              ]),
            ]),
          ),
          const SectionHeader('Connection'),
          GlassCard(
            padding: EdgeInsets.zero,
            child: ListTile(
              leading: Icon(PhosphorIconsRegular.broadcast, color: AppColors.textSecondary),
              title: Text('Server', style: AppText.label()),
              subtitle: Text(api.baseUrl.isEmpty ? 'Not set' : api.baseUrl, style: AppText.caption()),
              trailing: Icon(PhosphorIconsRegular.caretRight, color: AppColors.textMuted),
              onTap: () async {
                await ServerConfigDialog.show(context);
                setState(() {});
              },
            ),
          ),
          const SizedBox(height: AppSpace.xl),
          GhostButton(
            label: 'Sign out',
            icon: PhosphorIconsRegular.signOut,
            color: AppColors.danger,
            onPressed: () => ref.read(authProvider.notifier).logout(),
          ),
        ]),
      ),
    );
  }
}

class _SliderRow extends StatelessWidget {
  final String label;
  final String help;
  final double value;
  final double min;
  final double max;
  final ValueChanged<double> onChanged;
  const _SliderRow({required this.label, required this.help, required this.value, required this.min, required this.max, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Expanded(child: Text(label, style: AppText.label())),
        Text(value.toStringAsFixed(2), style: AppText.metric(size: 20, color: AppColors.primary)),
      ]),
      Slider(value: value.clamp(min, max), min: min, max: max, divisions: ((max - min) * 100).round(), onChanged: onChanged),
      Text(help, style: AppText.caption()),
    ]);
  }
}
