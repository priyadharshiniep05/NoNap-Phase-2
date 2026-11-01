import 'dart:math';

import 'package:flutter/material.dart';

import '../theme/tokens.dart';
import '../theme/typography.dart';

/// 0 (calm) .. 1 (level 2+) driver risk, for the ring colour.
double riskOf({required int level, required double eyesClosedSeconds, double l1Seconds = 1.0}) {
  if (level >= 2) return 1.0;
  if (level == 1) return 0.7;
  return (eyesClosedSeconds / l1Seconds).clamp(0.0, 1.0) * 0.5;
}

/// Cyan -> amber -> red as risk rises.
Color riskColor(double risk) {
  if (risk <= 0.5) return Color.lerp(AppColors.primary, AppColors.warning, risk / 0.5)!;
  return Color.lerp(AppColors.warning, AppColors.danger, (risk - 0.5) / 0.5)!;
}

/// The hero: a breathing ring whose colour and pace follow the driver's risk.
class StatusRing extends StatefulWidget {
  final String word;
  final String? sub;
  final double risk;
  final bool active; // false = not driving / camera offline: dim and still
  final double size;

  const StatusRing({super.key, required this.word, this.sub, required this.risk, this.active = true, this.size = 260});

  @override
  State<StatusRing> createState() => _StatusRingState();
}

class _StatusRingState extends State<StatusRing> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: _period(widget.risk));

  Duration _period(double risk) {
    // Calm 4 s breath, faster as risk rises (0.9 s at level 2+).
    final ms = 4000 - (3100 * risk);
    return Duration(milliseconds: ms.round());
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _sync();
  }

  @override
  void didUpdateWidget(StatusRing old) {
    super.didUpdateWidget(old);
    if ((old.risk - widget.risk).abs() > 0.05 || old.active != widget.active) {
      _c.duration = _period(widget.risk);
      _sync();
    }
  }

  void _sync() {
    if (!widget.active || AppMotion.reduced(context)) {
      _c.stop();
      _c.value = 0.5;
    } else {
      _c.repeat(reverse: true);
    }
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final target = widget.active ? riskColor(widget.risk) : AppColors.textMuted;
    return Semantics(
      label: 'Driver status: ${widget.word}. ${widget.sub ?? ''}',
      liveRegion: true,
      child: TweenAnimationBuilder<Color?>(
        tween: ColorTween(end: target),
        duration: AppMotion.of(context, AppMotion.slow),
        curve: AppMotion.curve,
        builder: (context, color, _) {
          final c = color ?? target;
          return AnimatedBuilder(
            animation: _c,
            builder: (context, _) {
              final t = Curves.easeInOut.transform(_c.value);
              return SizedBox(
                width: widget.size,
                height: widget.size,
                child: CustomPaint(
                  painter: _RingPainter(color: c, breath: t, active: widget.active),
                  child: Center(
                    child: Padding(
                      padding: EdgeInsets.all(widget.size * 0.16),
                      child: Column(mainAxisSize: MainAxisSize.min, children: [
                        AnimatedSwitcher(
                          duration: AppMotion.of(context, AppMotion.medium),
                          child: FittedBox(
                            key: ValueKey(widget.word),
                            fit: BoxFit.scaleDown,
                            child: Text(widget.word, style: AppText.headline(color: AppColors.textPrimary).copyWith(fontSize: 34)),
                          ),
                        ),
                        if (widget.sub != null) ...[
                          const SizedBox(height: 6),
                          Text(widget.sub!, textAlign: TextAlign.center, maxLines: 2,
                              style: AppText.caption(color: AppColors.textSecondary)),
                        ],
                      ]),
                    ),
                  ),
                ),
              );
            },
          );
        },
      ),
    );
  }
}

class _RingPainter extends CustomPainter {
  final Color color;
  final double breath; // 0..1
  final bool active;
  _RingPainter({required this.color, required this.breath, required this.active});

  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    final radius = size.width / 2;

    // Outer halo that breathes
    final haloR = radius * (0.86 + 0.12 * breath);
    canvas.drawCircle(
      center,
      haloR,
      Paint()
        ..shader = RadialGradient(colors: [
          color.withValues(alpha: active ? 0.22 + 0.10 * breath : 0.06),
          color.withValues(alpha: 0),
        ]).createShader(Rect.fromCircle(center: center, radius: haloR)),
    );

    // Inner disc
    final innerR = radius * 0.70;
    canvas.drawCircle(
      center,
      innerR,
      Paint()
        ..shader = RadialGradient(
          center: const Alignment(-0.3, -0.4),
          colors: [AppColors.surfaceRaised, AppColors.background],
        ).createShader(Rect.fromCircle(center: center, radius: innerR)),
    );

    // Track + sweep ring
    final ringRect = Rect.fromCircle(center: center, radius: radius * 0.74);
    canvas.drawCircle(center, radius * 0.74, Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3
      ..color = color.withValues(alpha: 0.18));
    canvas.drawArc(
      ringRect,
      -pi / 2 + breath * 0.6,
      2 * pi * 0.82,
      false,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeCap = StrokeCap.round
        ..strokeWidth = 6
        ..shader = SweepGradient(
          colors: [color.withValues(alpha: 0.0), color, color],
          stops: const [0.0, 0.6, 1.0],
          transform: GradientRotation(-pi / 2 + breath * 0.6),
        ).createShader(ringRect),
    );
  }

  @override
  bool shouldRepaint(_RingPainter old) => old.color != color || old.breath != breath || old.active != active;
}
