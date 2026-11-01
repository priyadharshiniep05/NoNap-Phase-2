import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import 'tokens.dart';

/// Type scale. Inter for UI text, Space Grotesk for headings and big numbers.
/// Live metrics use tabular figures so digits don't jitter as values change.
class AppText {
  AppText._();

  static const List<FontFeature> _tabular = [FontFeature.tabularFigures()];

  static TextStyle display({Color color = AppColors.textPrimary}) => GoogleFonts.spaceGrotesk(
        fontSize: 44, height: 1.05, fontWeight: FontWeight.w600, letterSpacing: -1.2, color: color,
        fontFeatures: _tabular,
      );

  static TextStyle headline({Color color = AppColors.textPrimary}) => GoogleFonts.spaceGrotesk(
        fontSize: 28, height: 1.15, fontWeight: FontWeight.w600, letterSpacing: -0.6, color: color,
      );

  static TextStyle title({Color color = AppColors.textPrimary}) => GoogleFonts.inter(
        fontSize: 18, height: 1.3, fontWeight: FontWeight.w600, letterSpacing: -0.2, color: color,
      );

  static TextStyle body({Color color = AppColors.textSecondary}) => GoogleFonts.inter(
        fontSize: 15, height: 1.45, fontWeight: FontWeight.w400, color: color,
      );

  static TextStyle label({Color color = AppColors.textPrimary}) => GoogleFonts.inter(
        fontSize: 13, height: 1.3, fontWeight: FontWeight.w600, letterSpacing: 0.1, color: color,
      );

  static TextStyle caption({Color color = AppColors.textMuted}) => GoogleFonts.inter(
        fontSize: 12, height: 1.35, fontWeight: FontWeight.w500, color: color, fontFeatures: _tabular,
      );

  static TextStyle overline({Color color = AppColors.textMuted}) => GoogleFonts.inter(
        fontSize: 11, height: 1.2, fontWeight: FontWeight.w700, letterSpacing: 1.2, color: color,
      );

  /// Big live numbers (EAR / MAR / tiles).
  static TextStyle metric({Color color = AppColors.textPrimary, double size = 34}) => GoogleFonts.spaceGrotesk(
        fontSize: size, height: 1.0, fontWeight: FontWeight.w600, letterSpacing: -0.8, color: color,
        fontFeatures: _tabular,
      );

  static TextStyle button({Color color = AppColors.onPrimary}) => GoogleFonts.inter(
        fontSize: 16, height: 1.2, fontWeight: FontWeight.w700, letterSpacing: 0.1, color: color,
      );
}
