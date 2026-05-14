import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:go_router/go_router.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/widgets/particle_field.dart';
import '../providers/auth_provider.dart';

class LoginPage extends ConsumerStatefulWidget {
  const LoginPage({super.key});
  @override
  ConsumerState<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends ConsumerState<LoginPage>
    with SingleTickerProviderStateMixin {
  final _emailCtrl = TextEditingController();
  final _passCtrl = TextEditingController();
  bool _loading = false;
  bool _hasError = false;
  String? _errorMsg;
  final _storage = const FlutterSecureStorage();

  @override
  void dispose() {
    _emailCtrl.dispose();
    _passCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final email = _emailCtrl.text.trim();
    final pass = _passCtrl.text;
    if (email.isEmpty || pass.isEmpty) {
      setState(() {
        _hasError = true;
        _errorMsg = 'Veuillez remplir tous les champs.';
      });
      Future.delayed(const Duration(milliseconds: 600),
          () { if (mounted) setState(() => _hasError = false); });
      return;
    }
    setState(() { _loading = true; _hasError = false; _errorMsg = null; });
    try {
      final container = ProviderScope.containerOf(context);
      await container.read(authProvider.notifier).login(email, pass);
      if (!mounted) return;
      final consentGiven = await _storage.read(key: 'consent_given');
      if (!mounted) return;
      if (consentGiven == 'true') {
        context.go('/home');
      } else {
        context.go('/consent');
      }
    } catch (e) {
      if (!mounted) return;
      String msg = 'Erreur de connexion.';
      final s = e.toString();
      if (s.contains('401') || s.contains('403')) {
        msg = 'Email ou mot de passe incorrect.';
      } else if (s.contains('network') || s.contains('connect') || s.contains('Socket')) {
        msg = 'Impossible de joindre le serveur.';
      }
      setState(() { _loading = false; _hasError = true; _errorMsg = msg; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.surface0,
      body: Stack(
        children: [
          const Positioned.fill(child: ParticleField(count: 12)),
          SafeArea(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 32),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const SizedBox(height: 60),
                  // App logo (52×52 rounded)
                  ClipRRect(
                    borderRadius: BorderRadius.circular(16),
                    child: Image.asset(
                      'assets/branding/app_icon.png',
                      width: 52,
                      height: 52,
                      fit: BoxFit.cover,
                    ),
                  ),
                  const SizedBox(height: 28),
                  // Title
                  const Text(
                    'Connexion',
                    style: TextStyle(
                      color: AppColors.textPrimary,
                      fontSize: 32,
                      fontWeight: FontWeight.w600,
                      letterSpacing: -0.5,
                      height: 1.1,
                    ),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Bon retour. Vos données restent au Maroc.',
                    style: TextStyle(
                      color: AppColors.textSecondary,
                      fontSize: 14,
                      height: 1.5,
                    ),
                  ),
                  const SizedBox(height: 36),
                  // Email field
                  _GradientInputField(
                    label: 'EMAIL',
                    controller: _emailCtrl,
                    keyboardType: TextInputType.emailAddress,
                    hasError: false,
                  ),
                  const SizedBox(height: 22),
                  // Password field
                  _GradientInputField(
                    label: 'MOT DE PASSE',
                    controller: _passCtrl,
                    isPassword: true,
                    hasError: _hasError,
                    onSubmit: _submit,
                  ),
                  // Forgot password
                  Align(
                    alignment: Alignment.centerRight,
                    child: TextButton(
                      onPressed: () {},
                      style: TextButton.styleFrom(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 0, vertical: 8)),
                      child: const Text(
                        'Mot de passe oublié ?',
                        style: TextStyle(
                            color: AppColors.textSecondary, fontSize: 12),
                      ),
                    ),
                  ),
                  const SizedBox(height: 20),
                  // Error message
                  if (_errorMsg != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 16),
                      child: Text(
                        _errorMsg!,
                        style: const TextStyle(
                            color: AppColors.riskHigh, fontSize: 13),
                      ),
                    ),
                  // Submit button
                  SizedBox(
                    width: double.infinity,
                    height: 54,
                    child: DecoratedBox(
                      decoration: BoxDecoration(
                        gradient: AppColors.aiGrad,
                        borderRadius: BorderRadius.circular(99),
                        boxShadow: [
                          BoxShadow(
                            color: const Color(0xFF6366F1)
                                .withValues(alpha: 0.35),
                            blurRadius: 24,
                            offset: const Offset(0, 8),
                          ),
                        ],
                      ),
                      child: ElevatedButton(
                        onPressed: _loading ? null : _submit,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.transparent,
                          shadowColor: Colors.transparent,
                          shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(99)),
                          disabledBackgroundColor: Colors.transparent,
                        ),
                        child: _loading
                            ? const _TypingDots()
                            : const Text(
                                'Se connecter',
                                style: TextStyle(
                                  color: Colors.white,
                                  fontSize: 15,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 28),
                  // Lock footer
                  const Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.lock_outline,
                          size: 11, color: Color(0xFF475569)),
                      SizedBox(width: 6),
                      Text(
                        'CHIFFRÉ · LOI 09-08',
                        style: TextStyle(
                          color: Color(0xFF475569),
                          fontSize: 10,
                          letterSpacing: 1.2,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 32),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ── Gradient underline input ──────────────────────────────────────────────────

class _GradientInputField extends StatefulWidget {
  final String label;
  final TextEditingController controller;
  final bool isPassword;
  final bool hasError;
  final TextInputType? keyboardType;
  final VoidCallback? onSubmit;

  const _GradientInputField({
    required this.label,
    required this.controller,
    this.isPassword = false,
    this.hasError = false,
    this.keyboardType,
    this.onSubmit,
  });

  @override
  State<_GradientInputField> createState() => _GradientInputFieldState();
}

class _GradientInputFieldState extends State<_GradientInputField> {
  final _focus = FocusNode();
  bool _focused = false;
  bool _obscure = true;

  @override
  void initState() {
    super.initState();
    _focus.addListener(() {
      setState(() => _focused = _focus.hasFocus);
    });
  }

  @override
  void dispose() {
    _focus.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final showGrad = _focused && !widget.hasError;
    final showErr = widget.hasError;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Mono uppercase label
        Text(
          widget.label,
          style: TextStyle(
            fontSize: 10,
            letterSpacing: 1.4,
            color: showErr
                ? AppColors.pulse
                : const Color(0xFF64748B),
            fontWeight: FontWeight.w500,
          ),
        ),
        const SizedBox(height: 8),
        Stack(
          children: [
            TextField(
              controller: widget.controller,
              focusNode: _focus,
              obscureText: widget.isPassword && _obscure,
              keyboardType: widget.keyboardType,
              autocorrect: false,
              style: const TextStyle(
                color: AppColors.textPrimary,
                fontSize: 16,
              ),
              onSubmitted: (_) => widget.onSubmit?.call(),
              decoration: InputDecoration(
                hintText: widget.isPassword ? '••••••••' : null,
                hintStyle:
                    const TextStyle(color: Color(0xFF475569)),
                filled: true,
                fillColor: const Color(0xFF111827).withValues(alpha: 0.6),
                contentPadding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
                border: const OutlineInputBorder(
                  borderSide: BorderSide.none,
                  borderRadius: BorderRadius.only(
                    topLeft: Radius.circular(8),
                    topRight: Radius.circular(8),
                  ),
                ),
                enabledBorder: const OutlineInputBorder(
                  borderSide: BorderSide.none,
                  borderRadius: BorderRadius.only(
                    topLeft: Radius.circular(8),
                    topRight: Radius.circular(8),
                  ),
                ),
                focusedBorder: const OutlineInputBorder(
                  borderSide: BorderSide.none,
                  borderRadius: BorderRadius.only(
                    topLeft: Radius.circular(8),
                    topRight: Radius.circular(8),
                  ),
                ),
                suffixIcon: widget.isPassword
                    ? IconButton(
                        icon: Icon(
                          _obscure
                              ? Icons.visibility_off_outlined
                              : Icons.visibility_outlined,
                          color: const Color(0xFF64748B),
                          size: 18,
                        ),
                        onPressed: () =>
                            setState(() => _obscure = !_obscure),
                      )
                    : null,
              ),
            ),
            // Gradient / error bottom line
            Positioned(
              left: 0,
              right: 0,
              bottom: 0,
              child: LayoutBuilder(
                builder: (_, c) => AnimatedContainer(
                  duration: const Duration(milliseconds: 250),
                  height: 2,
                  width: (showGrad || showErr) ? c.maxWidth : 0,
                  decoration: BoxDecoration(
                    gradient: showErr
                        ? const LinearGradient(colors: [
                            AppColors.pulse,
                            AppColors.pulse,
                          ])
                        : AppColors.aiGrad,
                    borderRadius: BorderRadius.circular(2),
                    boxShadow: showGrad
                        ? [
                            BoxShadow(
                              color: const Color(0xFF8B5CF6)
                                  .withValues(alpha: 0.4),
                              blurRadius: 12,
                            )
                          ]
                        : null,
                  ),
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }
}

// ── Animated typing dots ──────────────────────────────────────────────────────

class _TypingDots extends StatefulWidget {
  const _TypingDots();
  @override
  State<_TypingDots> createState() => _TypingDotsState();
}

class _TypingDotsState extends State<_TypingDots>
    with TickerProviderStateMixin {
  late final List<AnimationController> _ctrls;

  @override
  void initState() {
    super.initState();
    _ctrls = List.generate(3, (i) {
      final c = AnimationController(
        vsync: this,
        duration: const Duration(milliseconds: 600),
      );
      Future.delayed(Duration(milliseconds: i * 150), () {
        if (mounted) c.repeat(reverse: true);
      });
      return c;
    });
  }

  @override
  void dispose() {
    for (final c in _ctrls) { c.dispose(); }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: List.generate(
        3,
        (i) => AnimatedBuilder(
          animation: _ctrls[i],
          builder: (_, __) => Opacity(
            opacity: 0.4 + 0.6 * _ctrls[i].value,
            child: Container(
              width: 6,
              height: 6,
              margin: const EdgeInsets.symmetric(horizontal: 2),
              decoration: const BoxDecoration(
                color: Colors.white,
                shape: BoxShape.circle,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
