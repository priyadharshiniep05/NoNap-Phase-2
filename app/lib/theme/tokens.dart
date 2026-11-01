import 'package:flutter/material.dart';

/// NoNap design tokens. Widgets read colours, spacing, radii, glows and motion
/// from here and never hard-code them.
///
/// Contrast (WCAG 2.1, measured on [AppColors.background] #0F172A):
///   textPrimary 17.1:1 · textSecondary 12.0:1 · textMuted 6.9:1 (all AA, muted also AA on surface)
class AppColors {
  AppColors._();

  // Backgrounds
  static const Color background = Color(0xFF0F172A);
  static const Color backgroundDeep = Color(0xFF0A1022);
  static const Color surface = Color(0xFF1E293B);
  static const Color surfaceGlass = Color(0xB31E293B); // surface @ 70%
  static const Color surfaceRaised = Color(0xFF263449);
  static const Color border = Color(0x14FFFFFF); // white @ 8%
  static const Color borderStrong = Color(0x29FFFFFF); // white @ 16%

  // Brand + semantic
  static const Color primary = Color(0xFF22D3EE);
  static const Color primaryDeep = Color(0xFF0891B2);
  static const Color warning = Color(0xFFF59E0B);
  static const Color danger = Color(0xFFEF4444);
  static const Color dangerDeep = Color(0xFF7F1D1D);
  static const Color success = Color(0xFF10B981);

  // Text
  static const Color textPrimary = Color(0xFFF8FAFC);
  static const Color textSecondary = Color(0xFFCBD5E1);
  static const Color textMuted = Color(0xFF94A3B8);
  static const Color onPrimary = Color(0xFF04131A);

  /// Colour for an alert level 0-3.
  static Color forLevel(int level) {
    if (level >= 2) return danger;
    if (level == 1) return warning;
    return primary;
  }
}

class AppSpace {
  AppSpace._();
  static const double xs = 4;
  static const double s = 8;
  static const double m = 12;
  static const double l = 16;
  static const double xl = 24;
  static const double xxl = 32;
  static const double xxxl = 48;

  /// Horizontal page gutter.
  static const double gutter = 20;
}

class AppRadii {
  AppRadii._();
  static const double card = 20;
  static const double button = 14;
  static const double chip = 999;
  static const double small = 10;

  static const BorderRadius cardR = BorderRadius.all(Radius.circular(card));
  static const BorderRadius buttonR = BorderRadius.all(Radius.circular(button));
  static const BorderRadius pillR = BorderRadius.all(Radius.circular(chip));
}

class AppMotion {
  AppMotion._();
  static const Duration fast = Duration(milliseconds: 200);
  static const Duration medium = Duration(milliseconds: 300);
  static const Duration slow = Duration(milliseconds: 400);
  static const Curve curve = Curves.easeOutCubic;

  /// True when the user asked iOS to reduce motion.
  static bool reduced(BuildContext context) => MediaQuery.maybeDisableAnimationsOf(context) ?? false;

  /// [d], or zero when reduced motion is on.
  static Duration of(BuildContext context, Duration d) => reduced(context) ? Duration.zero : d;
}

class AppGlow {
  AppGlow._();

  /// Soft coloured glow instead of a grey drop shadow.
  static List<BoxShadow> of(Color color, {double opacity = 0.25, double blur = 32}) => [
        BoxShadow(color: color.withValues(alpha: opacity), blurRadius: blur, spreadRadius: -6),
      ];

  static const LinearGradient primaryButton = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFF22D3EE), Color(0xFF0EA5E9)],
  );

  static const LinearGradient dangerButton = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFFF87171), Color(0xFFDC2626)],
  );

  static const RadialGradient pageBackground = RadialGradient(
    center: Alignment(0, -0.9),
    radius: 1.4,
    colors: [Color(0xFF16233D), AppColors.background, AppColors.backgroundDeep],
    stops: [0, 0.55, 1],
  );
}
