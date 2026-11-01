import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../providers/auth_provider.dart';
import '../../theme/tokens.dart';
import '../../theme/typography.dart';
import '../../widgets/brand.dart';
import '../../widgets/server_config_dialog.dart';
import '../../widgets/ui.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _obscure = true;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _login() async {
    FocusScope.of(context).unfocus();
    if (_email.text.trim().isEmpty || _password.text.isEmpty) {
      showToast(context, 'Enter your email and password.', error: true);
      return;
    }
    final ok = await ref.read(authProvider.notifier).login(_email.text, _password.text);
    if (!ok && mounted) {
      showToast(context, ref.read(authProvider).error ?? 'Sign in failed.', error: true);
    }
  }

  void _fill(String email) {
    _email.text = email;
    _password.text = 'NoNap@123';
  }

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authProvider);
    final api = ref.watch(apiServiceProvider);
    final d = AppMotion.reduced(context) ? Duration.zero : 1.ms;

    return Scaffold(
      body: PageBackground(
        child: SafeArea(
          child: Column(children: [
            Align(
              alignment: Alignment.centerRight,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(0, AppSpace.s, AppSpace.l, 0),
                child: _ServerButton(
                  label: api.hasServer ? api.baseUrl.replaceFirst(RegExp(r'^https?://'), '') : 'Set server',
                  warn: !api.hasServer,
                  onTap: () async {
                    await ServerConfigDialog.show(context);
                    setState(() {});
                  },
                ),
              ),
            ),
            Expanded(
              child: Center(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.symmetric(horizontal: AppSpace.xl),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                    const Center(child: NoNapMark(size: 84, glow: true))
                        .animate()
                        .fadeIn(duration: d * 400)
                        .scaleXY(begin: 0.9, end: 1, curve: AppMotion.curve, duration: d * 400),
                    const SizedBox(height: AppSpace.l),
                    const Center(child: NoNapWordmark(size: 34)),
                    const SizedBox(height: AppSpace.xs),
                    Text('Real-time driver drowsiness detection',
                        textAlign: TextAlign.center, style: AppText.body(color: AppColors.textMuted)),
                    const SizedBox(height: AppSpace.xxl),
                    GlassCard(
                      padding: const EdgeInsets.all(AppSpace.xl),
                      child: AutofillGroup(
                        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                          Text('Sign in', style: AppText.title()),
                          const SizedBox(height: AppSpace.l),
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
                            autofillHints: const [AutofillHints.password],
                            textInputAction: TextInputAction.done,
                            onSubmitted: (_) => _login(),
                            style: AppText.body(color: AppColors.textPrimary),
                            decoration: InputDecoration(
                              labelText: 'Password',
                              prefixIcon: Icon(PhosphorIconsRegular.lockSimple),
                              suffixIcon: IconButton(
                                tooltip: _obscure ? 'Show password' : 'Hide password',
                                icon: Icon(_obscure ? PhosphorIconsRegular.eye : PhosphorIconsRegular.eyeSlash),
                                onPressed: () => setState(() => _obscure = !_obscure),
                              ),
                            ),
                          ),
                          const SizedBox(height: AppSpace.xl),
                          GradientButton(
                            label: 'Sign in',
                            icon: PhosphorIconsBold.arrowRight,
                            loading: auth.isLoading,
                            onPressed: _login,
                          ),
                        ]),
                      ),
                    ).animate(delay: d * 120).fadeIn(duration: d * 400).slideY(begin: 0.06, end: 0, curve: AppMotion.curve),
                    const SizedBox(height: AppSpace.xl),
                    Text('DEMO ACCOUNTS', textAlign: TextAlign.center, style: AppText.overline()),
                    const SizedBox(height: AppSpace.s),
                    Row(children: [
                      Expanded(
                        child: _DemoChip(
                          name: 'Priyadarshini',
                          role: 'Driver',
                          icon: PhosphorIconsRegular.steeringWheel,
                          onTap: () => _fill('driver1@nonap.demo'),
                        ),
                      ),
                      const SizedBox(width: AppSpace.m),
                      Expanded(
                        child: _DemoChip(
                          name: 'Ananya',
                          role: 'Fleet manager',
                          icon: PhosphorIconsRegular.truck,
                          onTap: () => _fill('manager@nonap.demo'),
                        ),
                      ),
                    ]),
                    const SizedBox(height: AppSpace.l),
                    Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                      Text('New to NoNap?', style: AppText.body(color: AppColors.textMuted)),
                      TextButton(onPressed: () => context.push('/signup'), child: const Text('Create an account')),
                    ]),
                    const SizedBox(height: AppSpace.l),
                  ]),
                ),
              ),
            ),
          ]),
        ),
      ),
    );
  }
}

class _ServerButton extends StatelessWidget {
  final String label;
  final bool warn;
  final VoidCallback onTap;
  const _ServerButton({required this.label, required this.warn, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final color = warn ? AppColors.warning : AppColors.textSecondary;
    return Material(
      type: MaterialType.transparency,
      child: InkWell(
        borderRadius: AppRadii.pillR,
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            borderRadius: AppRadii.pillR,
            border: Border.all(color: warn ? AppColors.warning.withValues(alpha: 0.5) : AppColors.border),
            color: AppColors.surface.withValues(alpha: 0.5),
          ),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Icon(PhosphorIconsRegular.broadcast, size: 15, color: color),
            const SizedBox(width: 6),
            Text(label, style: AppText.caption(color: color).copyWith(fontWeight: FontWeight.w600)),
          ]),
        ),
      ),
    );
  }
}

class _DemoChip extends StatelessWidget {
  final String name;
  final String role;
  final IconData icon;
  final VoidCallback onTap;
  const _DemoChip({required this.name, required this.role, required this.icon, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GlassCard(
      blur: false,
      onTap: onTap,
      padding: const EdgeInsets.symmetric(horizontal: AppSpace.m, vertical: AppSpace.m),
      child: Row(children: [
        Icon(icon, size: 20, color: AppColors.primary),
        const SizedBox(width: AppSpace.s),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(name, style: AppText.label(), overflow: TextOverflow.ellipsis),
            Text(role, style: AppText.caption()),
          ]),
        ),
      ]),
    );
  }
}
