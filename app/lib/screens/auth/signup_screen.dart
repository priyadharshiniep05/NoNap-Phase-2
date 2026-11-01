import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../providers/auth_provider.dart';
import '../../theme/tokens.dart';
import '../../theme/typography.dart';
import '../../widgets/ui.dart';

/// Sign up. The role picked here is permanent: drivers only ever see the
/// Driver dashboard, fleet managers only the Fleet dashboard.
class SignupScreen extends ConsumerStatefulWidget {
  const SignupScreen({super.key});

  @override
  ConsumerState<SignupScreen> createState() => _SignupScreenState();
}

class _SignupScreenState extends ConsumerState<SignupScreen> {
  final _name = TextEditingController();
  final _email = TextEditingController();
  final _password = TextEditingController();
  String? _role;
  bool _obscure = true;

  @override
  void dispose() {
    _name.dispose();
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  String? _validate() {
    if (_role == null) return 'Choose whether you drive or manage a fleet.';
    if (_name.text.trim().length < 2) return 'Enter your full name.';
    if (!_email.text.contains('@')) return 'Enter a valid email address.';
    final p = _password.text;
    if (p.length < 8 || !p.contains(RegExp(r'[A-Za-z]')) || !p.contains(RegExp(r'\d'))) {
      return 'Password needs 8+ characters with a letter and a number.';
    }
    return null;
  }

  Future<void> _submit() async {
    FocusScope.of(context).unfocus();
    final problem = _validate();
    if (problem != null) {
      showToast(context, problem, error: true);
      return;
    }
    final ok = await ref.read(authProvider.notifier).signup(
          fullName: _name.text,
          email: _email.text,
          password: _password.text,
          role: _role!,
        );
    if (!ok && mounted) showToast(context, ref.read(authProvider).error ?? 'Sign up failed.', error: true);
  }

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authProvider);
    final d = AppMotion.reduced(context) ? Duration.zero : 1.ms;
    return Scaffold(
      extendBodyBehindAppBar: true,
      appBar: AppBar(
        leading: IconButton(
          tooltip: 'Back',
          icon: Icon(PhosphorIconsRegular.caretLeft),
          onPressed: () => context.pop(),
        ),
      ),
      body: PageBackground(
        child: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(AppSpace.xl, AppSpace.s, AppSpace.xl, AppSpace.xxl),
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              Text('Create your account', style: AppText.headline()),
              const SizedBox(height: AppSpace.xs),
              Text('Pick your role. It sets which app you see and cannot be switched later.',
                  style: AppText.body(color: AppColors.textMuted)),
              const SizedBox(height: AppSpace.xl),
              Row(children: [
                Expanded(
                  child: _RoleCard(
                    title: "I'm a Driver",
                    body: 'Get alerted the moment drowsiness starts.',
                    icon: PhosphorIconsFill.steeringWheel,
                    selected: _role == 'driver',
                    onTap: () => setState(() => _role = 'driver'),
                  ),
                ),
                const SizedBox(width: AppSpace.m),
                Expanded(
                  child: _RoleCard(
                    title: 'I manage a Fleet',
                    body: 'See every driver live and act fast.',
                    icon: PhosphorIconsFill.truck,
                    selected: _role == 'fleet_manager',
                    onTap: () => setState(() => _role = 'fleet_manager'),
                  ),
                ),
              ]).animate().fadeIn(duration: d * 400).slideY(begin: 0.05, end: 0, curve: AppMotion.curve),
              const SizedBox(height: AppSpace.xl),
              GlassCard(
                padding: const EdgeInsets.all(AppSpace.xl),
                child: AutofillGroup(
                  child: Column(children: [
                    TextField(
                      controller: _name,
                      textCapitalization: TextCapitalization.words,
                      autofillHints: const [AutofillHints.name],
                      textInputAction: TextInputAction.next,
                      style: AppText.body(color: AppColors.textPrimary),
                      decoration: InputDecoration(
                        labelText: 'Full name',
                        hintText: 'Priyadarshini Prasanna',
                        prefixIcon: Icon(PhosphorIconsRegular.user),
                      ),
                    ),
                    const SizedBox(height: AppSpace.m),
                    TextField(
                      controller: _email,
                      keyboardType: TextInputType.emailAddress,
                      autofillHints: const [AutofillHints.email],
                      textInputAction: TextInputAction.next,
                      style: AppText.body(color: AppColors.textPrimary),
                      decoration: InputDecoration(labelText: 'Email', prefixIcon: Icon(PhosphorIconsRegular.envelopeSimple)),
                    ),
                    const SizedBox(height: AppSpace.m),
                    TextField(
                      controller: _password,
                      obscureText: _obscure,
                      autofillHints: const [AutofillHints.newPassword],
                      onSubmitted: (_) => _submit(),
                      style: AppText.body(color: AppColors.textPrimary),
                      decoration: InputDecoration(
                        labelText: 'Password',
                        helperText: '8+ characters, with a letter and a number',
                        helperStyle: AppText.caption(),
                        prefixIcon: Icon(PhosphorIconsRegular.lockSimple),
                        suffixIcon: IconButton(
                          tooltip: _obscure ? 'Show password' : 'Hide password',
                          icon: Icon(_obscure ? PhosphorIconsRegular.eye : PhosphorIconsRegular.eyeSlash),
                          onPressed: () => setState(() => _obscure = !_obscure),
                        ),
                      ),
                    ),
                  ]),
                ),
              ).animate(delay: d * 100).fadeIn(duration: d * 400),
              const SizedBox(height: AppSpace.xl),
              GradientButton(label: 'Create account', loading: auth.isLoading, onPressed: _submit),
            ]),
          ),
        ),
      ),
    );
  }
}

class _RoleCard extends StatelessWidget {
  final String title;
  final String body;
  final IconData icon;
  final bool selected;
  final VoidCallback onTap;
  const _RoleCard({required this.title, required this.body, required this.icon, required this.selected, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Semantics(
      selected: selected,
      button: true,
      label: title,
      child: AnimatedContainer(
        duration: AppMotion.of(context, AppMotion.medium),
        curve: AppMotion.curve,
        decoration: BoxDecoration(
          borderRadius: AppRadii.cardR,
          boxShadow: selected ? AppGlow.of(AppColors.primary, opacity: 0.35) : null,
        ),
        child: GlassCard(
          onTap: () {
            HapticFeedback.selectionClick();
            onTap();
          },
          borderColor: selected ? AppColors.primary : AppColors.border,
          borderWidth: selected ? 1.5 : 1,
          padding: const EdgeInsets.all(AppSpace.l),
          child: SizedBox(
            height: 150,
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: (selected ? AppColors.primary : AppColors.textMuted).withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(AppRadii.small + 2),
                  ),
                  child: Icon(icon, size: 26, color: selected ? AppColors.primary : AppColors.textSecondary),
                ),
                const Spacer(),
                AnimatedSwitcher(
                  duration: AppMotion.of(context, AppMotion.fast),
                  child: selected
                      ? Icon(PhosphorIconsFill.checkCircle, key: const ValueKey(1), color: AppColors.primary, size: 22)
                      : Icon(PhosphorIconsRegular.circle, key: const ValueKey(0), color: AppColors.textMuted, size: 22),
                ),
              ]),
              const Spacer(),
              Text(title, style: AppText.title().copyWith(fontSize: 16)),
              const SizedBox(height: 4),
              Text(body, style: AppText.caption(), maxLines: 2),
            ]),
          ),
        ),
      ),
    );
  }
}
