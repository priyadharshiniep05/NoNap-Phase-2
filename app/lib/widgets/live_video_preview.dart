import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../providers/auth_provider.dart';
import '../theme/tokens.dart';
import '../theme/typography.dart';

/// What the camera sees (Pi or MacBook webcam), refreshed ~3 times a second.
/// Frames are only held in the server's memory; nothing is recorded.
class LiveVideoPreview extends ConsumerStatefulWidget {
  final String source; // pi | webcam
  const LiveVideoPreview({super.key, required this.source});

  @override
  ConsumerState<LiveVideoPreview> createState() => _LiveVideoPreviewState();
}

class _LiveVideoPreviewState extends ConsumerState<LiveVideoPreview> {
  Timer? _timer;
  int _n = 0;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(milliseconds: 330), (_) {
      if (mounted) setState(() => _n++);
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final api = ref.watch(apiServiceProvider);
    final isPi = widget.source == 'pi';
    return ClipRRect(
      borderRadius: AppRadii.cardR,
      child: AspectRatio(
        aspectRatio: 4 / 3,
        child: Stack(fit: StackFit.expand, children: [
          const ColoredBox(color: Colors.black),
          Image.network(
            '${api.baseUrl}/monitor/preview?t=$_n',
            fit: BoxFit.cover,
            gaplessPlayback: true,
            errorBuilder: (_, _, _) => Center(
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                Icon(PhosphorIconsRegular.cameraSlash, color: AppColors.textMuted, size: 32),
                const SizedBox(height: 8),
                Text('Waiting for the camera', style: AppText.caption()),
              ]),
            ),
          ),
          Positioned(
            top: 10,
            left: 10,
            child: _Badge(
              icon: PhosphorIconsFill.circle,
              iconColor: AppColors.danger,
              text: isPi ? 'PI CAMERA' : 'MACBOOK CAM',
            ),
          ),
          if (!isPi)
            const Positioned(
              top: 10,
              right: 10,
              child: _Badge(icon: PhosphorIconsRegular.flipHorizontal, iconColor: AppColors.primary, text: 'MIRRORED'),
            ),
        ]),
      ),
    );
  }
}

class _Badge extends StatelessWidget {
  final IconData icon;
  final Color iconColor;
  final String text;
  const _Badge({required this.icon, required this.iconColor, required this.text});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(color: Colors.black.withValues(alpha: 0.55), borderRadius: AppRadii.pillR),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(icon, size: 10, color: iconColor),
        const SizedBox(width: 6),
        Text(text, style: AppText.overline(color: AppColors.textPrimary).copyWith(fontSize: 10)),
      ]),
    );
  }
}
