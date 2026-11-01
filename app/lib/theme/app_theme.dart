import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import 'tokens.dart';
import 'typography.dart';

class AppTheme {
  AppTheme._();

  static ThemeData get darkTheme {
    final base = ThemeData(brightness: Brightness.dark, useMaterial3: true);
    return base.copyWith(
      scaffoldBackgroundColor: AppColors.background,
      colorScheme: const ColorScheme.dark(
        primary: AppColors.primary,
        onPrimary: AppColors.onPrimary,
        secondary: AppColors.primary,
        surface: AppColors.surface,
        onSurface: AppColors.textPrimary,
        error: AppColors.danger,
      ),
      textTheme: GoogleFonts.interTextTheme(base.textTheme).apply(
        bodyColor: AppColors.textPrimary,
        displayColor: AppColors.textPrimary,
      ),
      splashFactory: InkSparkle.splashFactory,
      appBarTheme: AppBarTheme(
        backgroundColor: Colors.transparent,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        foregroundColor: AppColors.textPrimary,
        titleTextStyle: AppText.title(),
      ),
      dividerTheme: const DividerThemeData(color: AppColors.border, thickness: 1, space: 1),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        backgroundColor: AppColors.surfaceRaised,
        contentTextStyle: AppText.label(),
        shape: const RoundedRectangleBorder(borderRadius: AppRadii.buttonR),
      ),
      sliderTheme: const SliderThemeData(
        activeTrackColor: AppColors.primary,
        inactiveTrackColor: AppColors.surfaceRaised,
        thumbColor: AppColors.primary,
        overlayColor: Color(0x2222D3EE),
        trackHeight: 4,
      ),
      progressIndicatorTheme: const ProgressIndicatorThemeData(color: AppColors.primary),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.surface.withValues(alpha: 0.6),
        contentPadding: const EdgeInsets.symmetric(horizontal: AppSpace.l, vertical: AppSpace.l),
        border: const OutlineInputBorder(borderRadius: AppRadii.buttonR, borderSide: BorderSide(color: AppColors.border)),
        enabledBorder: const OutlineInputBorder(borderRadius: AppRadii.buttonR, borderSide: BorderSide(color: AppColors.borderStrong)),
        focusedBorder: const OutlineInputBorder(borderRadius: AppRadii.buttonR, borderSide: BorderSide(color: AppColors.primary, width: 1.5)),
        errorBorder: const OutlineInputBorder(borderRadius: AppRadii.buttonR, borderSide: BorderSide(color: AppColors.danger)),
        labelStyle: AppText.body(color: AppColors.textMuted),
        floatingLabelStyle: AppText.label(color: AppColors.primary),
        hintStyle: AppText.body(color: AppColors.textMuted),
        prefixIconColor: AppColors.textMuted,
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(foregroundColor: AppColors.primary, textStyle: AppText.label()),
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: AppColors.surface,
        shape: const RoundedRectangleBorder(borderRadius: AppRadii.cardR),
        titleTextStyle: AppText.title(),
        contentTextStyle: AppText.body(),
      ),
      bottomSheetTheme: const BottomSheetThemeData(
        backgroundColor: AppColors.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadii.card))),
      ),
    );
  }
}
