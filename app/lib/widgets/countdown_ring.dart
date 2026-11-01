import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';

import '../theme/tokens.dart';
import '../theme/typography.dart';

/// A ring that drains over [total] from [start], wrapped around [child].
class CountdownRing extends StatefulWidget {
  final DateTime start;
  final Duration total;
  final double size;
  final double stroke;
  final Color color;
  final Widget child;
  final bool showSeconds;

  const CountdownRing({
    super.key,
    required this.start,
    required this.total,
    required this.child,
    this.size = 240,
    this.stroke = 10,
    this.color = AppColors.textPrimary,
    this.showSeconds = true,
  });

  @override
  State<CountdownRing> createState() => _CountdownRingState();
}

class _CountdownRingState extends State<CountdownRing> with SingleTickerProviderStateMixin {
  late final Ticker _ticker;
  double _fraction = 1;

  @override
  void initState() {
    super.initState();
    _ticker = createTicker((_) {
      final elapsed = DateTime.now().difference(widget.start);
      final f = 1 - elapsed.inMilliseconds / widget.total.inMilliseconds;
      setState(() => _fraction = f.clamp(0.0, 1.0));
    })
      ..start();
  }

  @override
  void dispose() {
    _ticker.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final secondsLeft = (widget.total.inMilliseconds * _fraction / 1000).ceil();
    return SizedBox(
      width: widget.size,
      height: widget.size,
      child: Stack(alignment: Alignment.center, children: [
        CustomPaint(
          size: Size.square(widget.size),
          painter: _RingPainter(fraction: _fraction, color: widget.color, stroke: widget.stroke),
        ),
        widget.child,
        if (widget.showSeconds)
          Positioned(
            bottom: widget.stroke + 14,
            child: Text(
              _fraction > 0 ? '${secondsLeft}s' : 'Manager notified',
              style: AppText.caption(color: widget.color.withValues(alpha: 0.85)).copyWith(fontWeight: FontWeight.w700),
            ),
          ),
      ]),
    );
  }
}

class _RingPainter extends CustomPainter {
  final double fraction;
  final Color color;
  final double stroke;
  _RingPainter({required this.fraction, required this.color, required this.stroke});

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Offset.zero & size;
    final r = rect.deflate(stroke / 2);
    final track = Paint()
      ..color = color.withValues(alpha: 0.15)
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke;
    canvas.drawArc(r, 0, 2 * pi, false, track);
    if (fraction <= 0) return;
    final arc = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeWidth = stroke;
    canvas.drawArc(r, -pi / 2, 2 * pi * fraction, false, arc);
  }

  @override
  bool shouldRepaint(_RingPainter old) => old.fraction != fraction || old.color != color;
}

/// A ring that fills from 0 to [progress] (calibration).
class ProgressRing extends StatelessWidget {
  final double progress;
  final double size;
  final Color color;
  final Widget child;
  const ProgressRing({super.key, required this.progress, required this.child, this.size = 220, this.color = AppColors.primary});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: Stack(alignment: Alignment.center, children: [
        TweenAnimationBuilder<double>(
          tween: Tween(end: progress.clamp(0.0, 1.0)),
          duration: AppMotion.of(context, AppMotion.slow),
          curve: AppMotion.curve,
          builder: (_, v, _) => CustomPaint(
            size: Size.square(size),
            painter: _RingPainter(fraction: v, color: color, stroke: 10),
          ),
        ),
        child,
      ]),
    );
  }
}
