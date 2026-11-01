import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../providers/auth_provider.dart';
import '../theme/tokens.dart';
import '../theme/typography.dart';
import 'ui.dart';

/// Bottom sheet to set the backend address (the MacBook's IP on the shared Wi-Fi).
/// No addresses are built in; recently used ones are remembered on the phone.
class ServerConfigDialog extends ConsumerStatefulWidget {
  const ServerConfigDialog({super.key});

  static Future<void> show(BuildContext context) {
    return showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (_) => const ServerConfigDialog(),
    );
  }

  @override
  ConsumerState<ServerConfigDialog> createState() => _ServerConfigDialogState();
}

enum _Test { idle, testing, ok, fail }

class _ServerConfigDialogState extends ConsumerState<ServerConfigDialog> {
  late final TextEditingController _controller;
  _Test _test = _Test.idle;
  List<String> _recent = const [];

  @override
  void initState() {
    super.initState();
    final api = ref.read(apiServiceProvider);
    _controller = TextEditingController(text: api.baseUrl.isEmpty ? 'http://' : api.baseUrl);
    api.recentServers().then((r) {
      if (mounted) setState(() => _recent = r);
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<bool> _check([String? url]) async {
    setState(() => _test = _Test.testing);
    final ok = await ref.read(apiServiceProvider).checkHealth(url ?? _controller.text);
    if (mounted) setState(() => _test = ok ? _Test.ok : _Test.fail);
    return ok;
  }

  Future<void> _save() async {
    final url = _controller.text.trim();
    if (url.isEmpty || url == 'http://') return;
    await ref.read(apiServiceProvider).setBaseUrl(url);
    if (!mounted) return;
    Navigator.of(context).pop();
    showToast(context, 'Server set to ${ref.read(apiServiceProvider).baseUrl}');
  }

  @override
  Widget build(BuildContext context) {
    final bottom = MediaQuery.viewInsetsOf(context).bottom;
    return Padding(
      padding: EdgeInsets.fromLTRB(AppSpace.xl, AppSpace.m, AppSpace.xl, AppSpace.xl + bottom),
      child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
        Center(
          child: Container(width: 40, height: 4, decoration: BoxDecoration(color: AppColors.borderStrong, borderRadius: AppRadii.pillR)),
        ),
        const SizedBox(height: AppSpace.l),
        Text('NoNap server', style: AppText.headline().copyWith(fontSize: 24)),
        const SizedBox(height: AppSpace.xs),
        Text(
          "The MacBook running the backend. On the Mac run `ipconfig getifaddr en0` and enter http://<that-ip>:8000. The iPhone must be on the same Wi-Fi.",
          style: AppText.body(color: AppColors.textMuted),
        ),
        const SizedBox(height: AppSpace.l),
        TextField(
          controller: _controller,
          keyboardType: TextInputType.url,
          autocorrect: false,
          style: AppText.body(color: AppColors.textPrimary),
          decoration: InputDecoration(
            labelText: 'Server address',
            hintText: 'http://192.168.1.10:8000',
            prefixIcon: Icon(PhosphorIconsRegular.broadcast),
            suffixIcon: switch (_test) {
              _Test.testing => const Padding(
                  padding: EdgeInsets.all(14),
                  child: SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)),
                ),
              _Test.ok => Icon(PhosphorIconsFill.checkCircle, color: AppColors.success),
              _Test.fail => Icon(PhosphorIconsFill.warningCircle, color: AppColors.warning),
              _ => null,
            },
          ),
          onChanged: (_) {
            if (_test != _Test.idle) setState(() => _test = _Test.idle);
          },
          onSubmitted: (_) => _check(),
        ),
        const SizedBox(height: AppSpace.s),
        AnimatedSwitcher(
          duration: AppMotion.of(context, AppMotion.fast),
          child: switch (_test) {
            _Test.ok => Text('Connected. The server is reachable.', key: const ValueKey('ok'), style: AppText.caption(color: AppColors.success)),
            _Test.fail => Text(
                "Can't reach it. Check the IP, that the server is running, and the Mac firewall.",
                key: const ValueKey('fail'),
                style: AppText.caption(color: AppColors.warning),
              ),
            _ => const SizedBox(height: 16, key: ValueKey('idle')),
          },
        ),
        if (_recent.isNotEmpty) ...[
          const SizedBox(height: AppSpace.m),
          Text('RECENT', style: AppText.overline()),
          const SizedBox(height: AppSpace.s),
          Wrap(spacing: 8, runSpacing: 8, children: [
            for (final r in _recent)
              ActionChip(
                label: Text(r.replaceFirst(RegExp(r'^https?://'), ''), style: AppText.caption(color: AppColors.textPrimary)),
                backgroundColor: AppColors.surfaceRaised,
                side: const BorderSide(color: AppColors.border),
                shape: const StadiumBorder(),
                onPressed: () {
                  _controller.text = r;
                  _check(r);
                },
              ),
          ]),
        ],
        const SizedBox(height: AppSpace.xl),
        Row(children: [
          Expanded(child: GhostButton(label: 'Test', icon: PhosphorIconsRegular.plugsConnected, onPressed: () => _check())),
          const SizedBox(width: AppSpace.m),
          Expanded(child: GradientButton(label: 'Save', height: 52, onPressed: _save)),
        ]),
      ]),
    );
  }
}
