import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../providers/auth_provider.dart';
import '../../providers/fleet_provider.dart';
import '../../theme/tokens.dart';
import '../../theme/typography.dart';
import '../../widgets/server_config_dialog.dart';
import '../../widgets/ui.dart';

class FleetSettingsScreen extends ConsumerStatefulWidget {
  const FleetSettingsScreen({super.key});

  @override
  ConsumerState<FleetSettingsScreen> createState() => _FleetSettingsScreenState();
}

class _FleetSettingsScreenState extends ConsumerState<FleetSettingsScreen> {
  double? _ear;
  double? _mar;
  bool _saving = false;

  Future<void> _save() async {
    setState(() => _saving = true);
    final err = await ref.read(fleetDataProvider.notifier).updateThresholds({
      if (_ear != null) 'ear_threshold': double.parse(_ear!.toStringAsFixed(3)),
      if (_mar != null) 'mar_threshold': double.parse(_mar!.toStringAsFixed(3)),
    });
    if (!mounted) return;
    setState(() => _saving = false);
    showToast(context, err ?? 'Fleet defaults saved', error: err != null);
  }

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(authProvider).user;
    final t = ref.watch(fleetDataProvider).thresholds;
    final api = ref.watch(apiServiceProvider);
    final ear = _ear ?? (t?['ear_threshold'] as num?)?.toDouble() ?? 0.21;
    final mar = _mar ?? (t?['mar_threshold'] as num?)?.toDouble() ?? 0.60;

    Widget slider(String label, double v, double min, double max, ValueChanged<double> on) => Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Expanded(child: Text(label, style: AppText.label())),
              Text(v.toStringAsFixed(2), style: AppText.metric(size: 20, color: AppColors.primary)),
            ]),
            Slider(value: v.clamp(min, max), min: min, max: max, divisions: ((max - min) * 100).round(), onChanged: on),
          ],
        );

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
                  const Pill('Fleet manager', color: AppColors.primary),
                ]),
              ),
            ]),
          ),
          const SectionHeader('Fleet default thresholds'),
          GlassCard(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              slider('Eye closed below (EAR)', ear, 0.10, 0.35, (v) => setState(() => _ear = v)),
              const SizedBox(height: AppSpace.s),
              slider('Yawn above (MAR)', mar, 0.40, 1.20, (v) => setState(() => _mar = v)),
              const SizedBox(height: AppSpace.s),
              Text("Fleet-level defaults. A driver's own calibration always takes priority.", style: AppText.caption()),
              const SizedBox(height: AppSpace.l),
              GradientButton(label: 'Save', height: 52, loading: _saving, onPressed: (_ear == null && _mar == null) ? null : _save),
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
