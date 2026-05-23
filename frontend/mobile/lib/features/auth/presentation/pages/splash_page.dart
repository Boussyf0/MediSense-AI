import 'dart:async';
import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/widgets/particle_field.dart';
import '../providers/auth_provider.dart';

class SplashPage extends ConsumerStatefulWidget {
  const SplashPage({super.key});
  @override
  ConsumerState<SplashPage> createState() => _SplashPageState();
}

class _SplashPageState extends ConsumerState<SplashPage> with TickerProviderStateMixin {
  late final List<AnimationController> _rings;
  Timer? _ringDelay;
  final _storage = const FlutterSecureStorage();

  @override
  void initState() {
    super.initState();

    _rings = List.generate(
      2,
      (i) => AnimationController(
        vsync: this,
        duration: const Duration(milliseconds: 2400),
      ),
    );
    _rings[0].repeat();
    _ringDelay = Timer(const Duration(milliseconds: 1200), () {
      if (mounted) _rings[1].repeat();
    });

    _checkAuth();
  }

  Future<void> _checkAuth() async {
    await Future.delayed(const Duration(milliseconds: 2600));
    if (!mounted) return;
    final token = await _storage.read(key: 'access_token');
    final onboarded = await _storage.read(key: 'onboarded');
    if (!mounted) return;
    if (token != null) {
      // Hydrate auth state from /auth/me so downstream screens
      // (booking, profile) can read user.uuid without re-login.
      await ref.read(authProvider.notifier).loadUser();
      if (!mounted) return;
      context.go('/home');
    } else if (onboarded != null) {
      context.go('/login');
    } else {
      context.go('/onboarding');
    }
  }

  @override
  void dispose() {
    _ringDelay?.cancel();
    for (final c in _rings) { c.dispose(); }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.surface0,
      body: Stack(
        children: [
          const Positioned.fill(child: ParticleField(count: 20)),
          Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                // Logo with pulse rings
                SizedBox(
                  width: 200,
                  height: 200,
                  child: Stack(
                    alignment: Alignment.center,
                    children: [
                      // Pulse rings
                      ..._rings.map((ctrl) => AnimatedBuilder(
                            animation: ctrl,
                            builder: (_, __) {
                              final v =
                                  Curves.easeOut.transform(ctrl.value);
                              return Opacity(
                                opacity: (1 - v).clamp(0.0, 1.0),
                                child: Container(
                                  width: 110 + 80 * v,
                                  height: 110 + 80 * v,
                                  decoration: BoxDecoration(
                                    shape: BoxShape.circle,
                                    gradient: RadialGradient(
                                      colors: [
                                        const Color(0xFF8B5CF6)
                                            .withValues(alpha: 0.25),
                                        Colors.transparent,
                                      ],
                                      stops: const [0.0, 0.7],
                                    ),
                                  ),
                                ),
                              );
                            },
                          )),
                      // Logo image container
                      ClipRRect(
                        borderRadius: BorderRadius.circular(28),
                        child: BackdropFilter(
                          filter:
                              ImageFilter.blur(sigmaX: 12, sigmaY: 12),
                          child: Container(
                            width: 96,
                            height: 96,
                            decoration: BoxDecoration(
                              borderRadius: BorderRadius.circular(28),
                              color: const Color(0xFF1C2333)
                                  .withValues(alpha: 0.5),
                              border: Border.all(
                                color: const Color(0xFF8B5CF6)
                                    .withValues(alpha: 0.25),
                              ),
                              boxShadow: [
                                BoxShadow(
                                  color: const Color(0xFF6366F1)
                                      .withValues(alpha: 0.25),
                                  blurRadius: 40,
                                  offset: const Offset(0, 8),
                                ),
                              ],
                            ),
                            child: ClipRRect(
                              borderRadius: BorderRadius.circular(27),
                              child: Image.asset(
                                'assets/branding/app_icon.png',
                                width: 96,
                                height: 96,
                                fit: BoxFit.cover,
                              ),
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 28),
                // "MEDISENSE AI" — gradient on "AI"
                Row(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.baseline,
                  textBaseline: TextBaseline.alphabetic,
                  children: [
                    const Text(
                      'MEDISENSE',
                      style: TextStyle(
                        color: AppColors.textPrimary,
                        fontSize: 26,
                        fontWeight: FontWeight.w600,
                        letterSpacing: 4.5,
                        height: 1.2,
                      ),
                    ),
                    const SizedBox(width: 8),
                    ShaderMask(
                      shaderCallback: (b) =>
                          AppColors.aiGrad.createShader(b),
                      child: const Text(
                        'AI',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 26,
                          fontWeight: FontWeight.w600,
                          letterSpacing: 4.5,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 14),
                const Text(
                  'Powered by RAG · XGBoost · LSTM',
                  style: TextStyle(
                    color: Color(0xFF64748B),
                    fontSize: 9.5,
                    letterSpacing: 1.5,
                  ),
                ),
              ],
            ),
          ),
          // Bottom version label
          const Positioned(
            bottom: 72,
            left: 0,
            right: 0,
            child: Text(
              'v1.0.0 · marrakech',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: Color(0xFF334155),
                fontSize: 9,
                letterSpacing: 1.3,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
