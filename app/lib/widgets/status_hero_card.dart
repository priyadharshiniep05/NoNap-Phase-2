import 'package:flutter/material.dart';
import '../theme/app_colors.dart';

class StatusHeroCard extends StatefulWidget {
  final String status; // alert, drowsy, yawning, accident, no_face, offline
  final String message;
  final String timestamp;
  final double confidence;

  const StatusHeroCard({
    super.key,
    required this.status,
    required this.message,
    required this.timestamp,
    required this.confidence,
  });

  @override
  State<StatusHeroCard> createState() => _StatusHeroCardState();
}

class _StatusHeroCardState extends State<StatusHeroCard>
    with SingleTickerProviderStateMixin {
  late AnimationController _animController;
  late Animation<double> _pulseAnimation;

  @override
  void initState() {
    super.initState();
    _animController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat(reverse: true);

    _pulseAnimation = Tween<double>(begin: 0.95, end: 1.05).animate(
      CurvedAnimation(parent: _animController, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _animController.dispose();
    super.dispose();
  }

  Color _getStatusColor() {
    switch (widget.status.toLowerCase()) {
      case 'drowsy':
        return AppColors.drowsyRed;
      case 'yawning':
        return AppColors.yawnAmber;
      case 'accident':
        return AppColors.accidentDarkRed;
      case 'no_face':
        return AppColors.textMuted;
      case 'alert':
      default:
        return AppColors.alertGreen;
    }
  }

  IconData _getStatusIcon() {
    switch (widget.status.toLowerCase()) {
      case 'drowsy':
        return Icons.warning_amber_rounded;
      case 'yawning':
        return Icons.bedtime_rounded;
      case 'accident':
        return Icons.emergency_rounded;
      case 'no_face':
        return Icons.visibility_off_rounded;
      case 'alert':
      default:
        return Icons.check_circle_outline_rounded;
    }
  }

  String _getTitle() {
    switch (widget.status.toLowerCase()) {
      case 'drowsy':
        return 'DROWSINESS ALERT';
      case 'yawning':
        return 'FATIGUE DETECTED';
      case 'accident':
        return 'CRITICAL ACCIDENT SOS';
      case 'no_face':
        return 'NO FACE IN VIEW';
      case 'alert':
      default:
        return 'DRIVER ALERT';
    }
  }

  @override
  Widget build(BuildContext context) {
    final statusColor = _getStatusColor();
    final isDanger = widget.status == 'drowsy' || widget.status == 'accident';

    return AnimatedBuilder(
      animation: _pulseAnimation,
      builder: (context, child) {
        final scale = isDanger ? _pulseAnimation.value : 1.0;
        return Transform.scale(
          scale: scale,
          child: Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  statusColor.withValues(alpha: 0.20),
                  AppColors.surfaceSubtle,
                ],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(
                color: statusColor.withValues(alpha: isDanger ? 0.9 : 0.4),
                width: isDanger ? 2.5 : 1.5,
              ),
              boxShadow: [
                BoxShadow(
                  color: statusColor.withValues(alpha: isDanger ? 0.35 : 0.1),
                  blurRadius: isDanger ? 24 : 12,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: statusColor.withValues(alpha: 0.15),
                    border: Border.all(color: statusColor, width: 2),
                  ),
                  child: Icon(
                    _getStatusIcon(),
                    color: statusColor,
                    size: 40,
                  ),
                ),
                const SizedBox(height: 16),
                Text(
                  _getTitle(),
                  style: TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.w800,
                    color: statusColor,
                    letterSpacing: 1.2,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  widget.message.isNotEmpty
                      ? widget.message
                      : 'Real-time eye and facial monitoring active.',
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    fontSize: 15,
                    color: AppColors.textPrimary,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                if (widget.timestamp.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: AppColors.surfaceElevated.withValues(alpha: 0.6),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Text(
                      'Live update: ${widget.timestamp}',
                      style: const TextStyle(
                        fontSize: 11,
                        color: AppColors.textSecondary,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),
        );
      },
    );
  }
}
