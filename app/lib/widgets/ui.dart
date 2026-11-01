import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../models/alert_item.dart';
import '../theme/tokens.dart';
import '../theme/typography.dart';

/// Navy radial gradient behind every screen.
class PageBackground extends StatelessWidget {
  final Widget child;
  const PageBackground({super.key, required this.child});

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(gradient: AppGlow.pageBackground),
      child: child,
    );
  }
}

/// Frosted glass card: surface @70%, 1 px white @8% border, 20 px blur.
class GlassCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  final Color? glow;
  final Color? borderColor;
  final double borderWidth;
  final VoidCallback? onTap;
  final bool blur;

  const GlassCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(AppSpace.l),
    this.glow,
    this.borderColor,
    this.borderWidth = 1,
    this.onTap,
    this.blur = true,
  });

  @override
  Widget build(BuildContext context) {
    Widget content = Container(
      padding: padding,
      decoration: BoxDecoration(
        color: AppColors.surfaceGlass,
        borderRadius: AppRadii.cardR,
        border: Border.all(color: borderColor ?? AppColors.border, width: borderWidth),
      ),
      child: child,
    );
    if (onTap != null) {
      content = Material(
        type: MaterialType.transparency,
        child: InkWell(borderRadius: AppRadii.cardR, onTap: onTap, child: content),
      );
    }
    final clipped = ClipRRect(
      borderRadius: AppRadii.cardR,
      child: blur ? BackdropFilter(filter: ImageFilter.blur(sigmaX: 20, sigmaY: 20), child: content) : content,
    );
    if (glow == null) return clipped;
    return DecoratedBox(
      decoration: BoxDecoration(borderRadius: AppRadii.cardR, boxShadow: AppGlow.of(glow!)),
      child: clipped,
    );
  }
}

class SectionHeader extends StatelessWidget {
  final String title;
  final Widget? trailing;
  const SectionHeader(this.title, {super.key, this.trailing});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: AppSpace.xl, bottom: AppSpace.m),
      child: Row(
        children: [
          Expanded(child: Text(title.toUpperCase(), style: AppText.overline())),
          ?trailing,
        ],
      ),
    );
  }
}

/// Small coloured pill, e.g. "Level 2".
class Pill extends StatelessWidget {
  final String text;
  final Color color;
  final IconData? icon;
  final bool solid;
  const Pill(this.text, {super.key, required this.color, this.icon, this.solid = false});

  @override
  Widget build(BuildContext context) {
    final fg = solid ? AppColors.onPrimary : color;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: solid ? color : color.withValues(alpha: 0.14),
        borderRadius: AppRadii.pillR,
        border: Border.all(color: color.withValues(alpha: solid ? 1 : 0.35)),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        if (icon != null) ...[Icon(icon, size: 12, color: fg), const SizedBox(width: 4)],
        Text(text, style: AppText.caption(color: fg).copyWith(fontWeight: FontWeight.w700)),
      ]),
    );
  }
}

class LevelChip extends StatelessWidget {
  final int level;
  const LevelChip(this.level, {super.key});

  @override
  Widget build(BuildContext context) => Pill('Level $level', color: AppColors.forLevel(level));
}

/// A dot that softly pulses when [pulse] is on.
class StatusDot extends StatelessWidget {
  final Color color;
  final bool pulse;
  final double size;
  const StatusDot({super.key, required this.color, this.pulse = false, this.size = 8});

  @override
  Widget build(BuildContext context) {
    final dot = Container(
      width: size,
      height: size,
      decoration: BoxDecoration(color: color, shape: BoxShape.circle, boxShadow: AppGlow.of(color, opacity: 0.6, blur: 8)),
    );
    if (!pulse || AppMotion.reduced(context)) return dot;
    return dot
        .animate(onPlay: (c) => c.repeat(reverse: true))
        .scaleXY(begin: 0.8, end: 1.15, duration: 900.ms, curve: Curves.easeInOut)
        .fade(begin: 0.6, end: 1);
  }
}

enum ChipTone { ok, warn, bad, idle }

/// Connection chip: "● Backend", "● Pi Camera · 2.9 fps · 47°C".
class ConnectionChip extends StatelessWidget {
  final String label;
  final String? detail;
  final ChipTone tone;
  final IconData icon;
  const ConnectionChip({super.key, required this.label, this.detail, required this.tone, required this.icon});

  Color get _color => switch (tone) {
        ChipTone.ok => AppColors.success,
        ChipTone.warn => AppColors.warning,
        ChipTone.bad => AppColors.danger,
        ChipTone.idle => AppColors.textMuted,
      };

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: '$label ${detail ?? ''} ${tone.name}',
      child: AnimatedContainer(
        duration: AppMotion.of(context, AppMotion.medium),
        curve: AppMotion.curve,
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
        decoration: BoxDecoration(
          color: _color.withValues(alpha: 0.10),
          borderRadius: AppRadii.pillR,
          border: Border.all(color: _color.withValues(alpha: 0.30)),
        ),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          StatusDot(color: _color, pulse: tone == ChipTone.ok || tone == ChipTone.warn, size: 7),
          const SizedBox(width: 6),
          Icon(icon, size: 13, color: AppColors.textSecondary),
          const SizedBox(width: 4),
          Text(label, style: AppText.caption(color: AppColors.textPrimary).copyWith(fontWeight: FontWeight.w600)),
          if (detail != null) ...[
            const SizedBox(width: 6),
            Text(detail!, style: AppText.caption()),
          ],
        ]),
      ),
    );
  }
}

class InitialsAvatar extends StatelessWidget {
  final String name;
  final double size;
  final Color ring;
  const InitialsAvatar({super.key, required this.name, this.size = 44, this.ring = AppColors.primary});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [ring.withValues(alpha: 0.30), AppColors.surfaceRaised],
        ),
        border: Border.all(color: ring.withValues(alpha: 0.55), width: 1.5),
      ),
      child: Text(initialsOf(name), style: AppText.label().copyWith(fontSize: size * 0.34)),
    );
  }
}

/// Big rounded gradient button with a press-down animation and haptic.
class GradientButton extends StatefulWidget {
  final String label;
  final IconData? icon;
  final VoidCallback? onPressed;
  final Gradient gradient;
  final bool loading;
  final Color? foreground;
  final double height;

  const GradientButton({
    super.key,
    required this.label,
    this.icon,
    required this.onPressed,
    this.gradient = AppGlow.primaryButton,
    this.loading = false,
    this.foreground,
    this.height = 56,
  });

  @override
  State<GradientButton> createState() => _GradientButtonState();
}

class _GradientButtonState extends State<GradientButton> {
  bool _down = false;

  @override
  Widget build(BuildContext context) {
    final enabled = widget.onPressed != null && !widget.loading;
    final fg = widget.foreground ?? AppColors.onPrimary;
    final first = (widget.gradient as LinearGradient).colors.first;
    return Semantics(
      button: true,
      enabled: enabled,
      label: widget.label,
      child: GestureDetector(
        onTapDown: enabled ? (_) => setState(() => _down = true) : null,
        onTapCancel: () => setState(() => _down = false),
        onTapUp: enabled
            ? (_) {
                setState(() => _down = false);
                HapticFeedback.mediumImpact();
                widget.onPressed!();
              }
            : null,
        child: AnimatedScale(
          scale: _down ? 0.97 : 1,
          duration: AppMotion.of(context, const Duration(milliseconds: 120)),
          curve: AppMotion.curve,
          child: AnimatedOpacity(
            opacity: enabled ? 1 : 0.55,
            duration: AppMotion.of(context, AppMotion.fast),
            child: Container(
              height: widget.height,
              decoration: BoxDecoration(
                gradient: widget.gradient,
                borderRadius: AppRadii.buttonR,
                boxShadow: enabled ? AppGlow.of(first, opacity: 0.35, blur: 24) : null,
              ),
              alignment: Alignment.center,
              child: widget.loading
                  ? SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2.4, color: fg))
                  : Row(mainAxisSize: MainAxisSize.min, children: [
                      if (widget.icon != null) ...[Icon(widget.icon, color: fg, size: 20), const SizedBox(width: 10)],
                      Text(widget.label, style: AppText.button(color: fg)),
                    ]),
            ),
          ),
        ),
      ),
    );
  }
}

/// Secondary outline button in the same shape.
class GhostButton extends StatelessWidget {
  final String label;
  final IconData? icon;
  final VoidCallback? onPressed;
  final Color color;
  const GhostButton({super.key, required this.label, this.icon, this.onPressed, this.color = AppColors.textPrimary});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 52,
      child: OutlinedButton(
        onPressed: onPressed == null
            ? null
            : () {
                HapticFeedback.selectionClick();
                onPressed!();
              },
        style: OutlinedButton.styleFrom(
          foregroundColor: color,
          side: const BorderSide(color: AppColors.borderStrong),
          shape: const RoundedRectangleBorder(borderRadius: AppRadii.buttonR),
          textStyle: AppText.label(),
        ),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          if (icon != null) ...[Icon(icon, size: 18), const SizedBox(width: 8)],
          Text(label),
        ]),
      ),
    );
  }
}

/// Illustrated empty state: big soft icon + one line.
class EmptyState extends StatelessWidget {
  final IconData icon;
  final String message;
  final String? detail;
  const EmptyState({super.key, required this.icon, required this.message, this.detail});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpace.xxl, horizontal: AppSpace.xl),
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        Container(
          width: 76,
          height: 76,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: AppColors.primary.withValues(alpha: 0.08),
            border: Border.all(color: AppColors.primary.withValues(alpha: 0.18)),
          ),
          child: Icon(icon, size: 34, color: AppColors.primary),
        ),
        const SizedBox(height: AppSpace.l),
        Text(message, textAlign: TextAlign.center, style: AppText.title()),
        if (detail != null) ...[
          const SizedBox(height: AppSpace.xs),
          Text(detail!, textAlign: TextAlign.center, style: AppText.body(color: AppColors.textMuted)),
        ],
      ]),
    ).animate().fadeIn(duration: AppMotion.of(context, AppMotion.slow)).slideY(begin: 0.05, end: 0, curve: AppMotion.curve);
  }
}

/// Friendly error with a retry button (never raw exception text).
class ErrorState extends StatelessWidget {
  final String message;
  final VoidCallback? onRetry;
  const ErrorState({super.key, required this.message, this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(AppSpace.xl),
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        Container(
          width: 72,
          height: 72,
          decoration: BoxDecoration(shape: BoxShape.circle, color: AppColors.warning.withValues(alpha: 0.10)),
          child: Icon(PhosphorIconsRegular.cloudSlash, size: 32, color: AppColors.warning),
        ),
        const SizedBox(height: AppSpace.l),
        Text('Connection hiccup', style: AppText.title()),
        const SizedBox(height: AppSpace.xs),
        Text(message, textAlign: TextAlign.center, style: AppText.body(color: AppColors.textMuted)),
        if (onRetry != null) ...[
          const SizedBox(height: AppSpace.l),
          GhostButton(label: 'Try again', icon: PhosphorIconsRegular.arrowClockwise, onPressed: onRetry, color: AppColors.primary),
        ],
      ]),
    );
  }
}

/// Shimmering placeholder block.
class Skeleton extends StatelessWidget {
  final double height;
  final double? width;
  final double radius;
  const Skeleton({super.key, required this.height, this.width, this.radius = AppRadii.card});

  @override
  Widget build(BuildContext context) {
    final box = Container(
      height: height,
      width: width,
      decoration: BoxDecoration(color: AppColors.surface.withValues(alpha: 0.7), borderRadius: BorderRadius.circular(radius)),
    );
    if (AppMotion.reduced(context)) return box;
    return box
        .animate(onPlay: (c) => c.repeat())
        .shimmer(duration: 1400.ms, color: AppColors.textPrimary.withValues(alpha: 0.06));
  }
}

class SkeletonList extends StatelessWidget {
  final int count;
  final double itemHeight;
  const SkeletonList({super.key, this.count = 4, this.itemHeight = 84});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: List.generate(
        count,
        (_) => Padding(padding: const EdgeInsets.only(bottom: AppSpace.m), child: Skeleton(height: itemHeight)),
      ),
    );
  }
}

/// Small tile for a summary number ("Drivers online · 3").
class StatTile extends StatelessWidget {
  final String label;
  final String value;
  final IconData icon;
  final Color color;
  final String? sub;
  const StatTile({super.key, required this.label, required this.value, required this.icon, this.color = AppColors.primary, this.sub});

  @override
  Widget build(BuildContext context) {
    return GlassCard(
      padding: const EdgeInsets.all(AppSpace.l),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Container(
            padding: const EdgeInsets.all(6),
            decoration: BoxDecoration(color: color.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(AppRadii.small)),
            child: Icon(icon, size: 16, color: color),
          ),
          const Spacer(),
          if (sub != null) Text(sub!, style: AppText.caption()),
        ]),
        const SizedBox(height: AppSpace.m),
        AnimatedSwitcher(
          duration: AppMotion.of(context, AppMotion.medium),
          transitionBuilder: (c, a) => FadeTransition(opacity: a, child: SlideTransition(position: Tween(begin: const Offset(0, 0.3), end: Offset.zero).animate(a), child: c)),
          child: Text(value, key: ValueKey(value), style: AppText.metric(size: 28)),
        ),
        const SizedBox(height: 2),
        Text(label, style: AppText.caption()),
      ]),
    );
  }
}

void showToast(BuildContext context, String message, {bool error = false}) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(
      content: Row(children: [
        Icon(error ? PhosphorIconsFill.warningCircle : PhosphorIconsFill.checkCircle,
            color: error ? AppColors.warning : AppColors.success, size: 18),
        const SizedBox(width: 10),
        Expanded(child: Text(message, style: AppText.label())),
      ]),
    ));
}
