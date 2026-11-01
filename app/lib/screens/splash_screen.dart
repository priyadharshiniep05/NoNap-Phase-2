import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../theme/tokens.dart';
import '../widgets/brand.dart';
import '../widgets/ui.dart';

/// Shown while the saved session is checked: animated logo reveal.
class SplashScreen extends StatelessWidget {
  const SplashScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final d = AppMotion.reduced(context) ? Duration.zero : 1.ms;
    return Scaffold(
      body: PageBackground(
        child: Center(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            const NoNapMark(size: 112, glow: true)
                .animate()
                .fadeIn(duration: d * 450, curve: AppMotion.curve)
                .scaleXY(begin: 0.82, end: 1, duration: d * 450, curve: AppMotion.curve),
            const SizedBox(height: AppSpace.xl),
            const NoNapWordmark(size: 36, tagline: true)
                .animate(delay: d * 220)
                .fadeIn(duration: d * 400, curve: AppMotion.curve)
                .slideY(begin: 0.15, end: 0, duration: d * 400, curve: AppMotion.curve),
          ]),
        ),
      ),
    );
  }
}
