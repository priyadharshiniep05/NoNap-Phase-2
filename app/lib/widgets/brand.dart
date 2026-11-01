import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';

import '../theme/tokens.dart';
import '../theme/typography.dart';

/// The NoNap icon (eye + crescent + "no" slash) from assets/brand/nonap_icon.svg.
class NoNapMark extends StatelessWidget {
  final double size;
  final bool glow;
  const NoNapMark({super.key, this.size = 40, this.glow = false});

  @override
  Widget build(BuildContext context) {
    final mark = ClipRRect(
      borderRadius: BorderRadius.circular(size * 0.22),
      child: SvgPicture.asset('assets/brand/nonap_icon.svg', width: size, height: size, semanticsLabel: 'NoNap'),
    );
    if (!glow) return mark;
    return DecoratedBox(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(size * 0.22),
        boxShadow: AppGlow.of(AppColors.primary, opacity: 0.35, blur: size * 0.6),
      ),
      child: mark,
    );
  }
}

/// "NoNap" wordmark matching nonap_logo.svg (No in white, Nap in cyan).
class NoNapWordmark extends StatelessWidget {
  final double size;
  final bool tagline;
  const NoNapWordmark({super.key, this.size = 32, this.tagline = false});

  @override
  Widget build(BuildContext context) {
    final base = AppText.headline().copyWith(fontSize: size, fontWeight: FontWeight.w700, letterSpacing: -size * 0.03);
    return Column(mainAxisSize: MainAxisSize.min, children: [
      Text.rich(TextSpan(children: [
        TextSpan(text: 'No', style: base),
        TextSpan(text: 'Nap', style: base.copyWith(color: AppColors.primary)),
      ])),
      if (tagline) ...[
        SizedBox(height: size * 0.15),
        Text('STAY AWAKE. STAY ALIVE.', style: AppText.overline().copyWith(letterSpacing: 3)),
      ],
    ]);
  }
}

/// Icon + wordmark in a row, for app bars.
class NoNapLockup extends StatelessWidget {
  final double size;
  const NoNapLockup({super.key, this.size = 28});

  @override
  Widget build(BuildContext context) {
    return Row(mainAxisSize: MainAxisSize.min, children: [
      NoNapMark(size: size),
      SizedBox(width: size * 0.35),
      NoNapWordmark(size: size * 0.72),
    ]);
  }
}
