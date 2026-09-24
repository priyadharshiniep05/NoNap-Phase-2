import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/auth_provider.dart';
import '../theme/app_colors.dart';

class LiveVideoPreview extends ConsumerStatefulWidget {
  const LiveVideoPreview({super.key});

  @override
  ConsumerState<LiveVideoPreview> createState() => _LiveVideoPreviewState();
}

class _LiveVideoPreviewState extends ConsumerState<LiveVideoPreview> {
  Timer? _refreshTimer;
  int _counter = 0;

  @override
  void initState() {
    super.initState();
    // Refresh preview frame at 3 fps for smooth responsive mobile feed
    _refreshTimer = Timer.periodic(const Duration(milliseconds: 330), (_) {
      if (mounted) {
        setState(() {
          _counter++;
        });
      }
    });
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final api = ref.watch(apiServiceProvider);
    final previewUrl = '${api.baseUrl}/monitor/preview?t=$_counter';

    return Container(
      height: 200,
      width: double.infinity,
      decoration: BoxDecoration(
        color: Colors.black,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(16),
        child: Stack(
          fit: StackFit.expand,
          children: [
            Image.network(
              previewUrl,
              fit: BoxFit.cover,
              gaplessPlayback: true,
              errorBuilder: (context, error, stackTrace) {
                return Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: const [
                      Icon(Icons.videocam_off_rounded, color: AppColors.textMuted, size: 36),
                      SizedBox(height: 8),
                      Text(
                        'Webcam feed connecting...',
                        style: TextStyle(color: AppColors.textMuted, fontSize: 12),
                      ),
                    ],
                  ),
                );
              },
            ),
            Positioned(
              top: 10,
              left: 10,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: Colors.black.withValues(alpha: 0.6),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: const [
                    CircleAvatar(radius: 4, backgroundColor: AppColors.drowsyRed),
                    SizedBox(width: 6),
                    Text(
                      'LIVE MACBOOK CAM',
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                        color: Colors.white,
                        letterSpacing: 0.8,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
