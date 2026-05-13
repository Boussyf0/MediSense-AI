import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/widgets/particle_field.dart';

class OnboardingPage extends StatefulWidget {
  const OnboardingPage({super.key});
  @override
  State<OnboardingPage> createState() => _OnboardingPageState();
}

class _Step {
  final IconData icon;
  final String title;
  final String desc;
  final String tag;
  const _Step(this.icon, this.title, this.desc, this.tag);
}

const _steps = [
  _Step(
    Icons.monitor_heart_outlined,
    'Vos signes vitaux,\nen continu',
    'Synchronisez votre bracelet connecté pour suivre fréquence cardiaque, SpO₂ et HRV en temps réel.',
    'IoT · BLE',
  ),
  _Step(
    Icons.chat_bubble_outline_rounded,
    'Une IA médicale\nen FR · AR · Darija',
    'Posez vos questions en langage naturel. Réponses sourcées avec score de confiance, jamais inventées.',
    'RAG · 30k corpus',
  ),
  _Step(
    Icons.shield_outlined,
    'Vos données,\nau Maroc',
    'Conforme RGPD et Loi 09-08. Hébergement local, modèle local, droit à l\'effacement en 1 tap.',
    'Loi 09-08',
  ),
];

class _OnboardingPageState extends State<OnboardingPage> {
  final _pageCtrl = PageController();
  final _storage = const FlutterSecureStorage();
  int _idx = 0;

  void _next() {
    if (_idx < _steps.length - 1) {
      _pageCtrl.nextPage(
          duration: const Duration(milliseconds: 500),
          curve: const Cubic(0.65, 0.05, 0.36, 1));
    } else {
      _finish();
    }
  }

  Future<void> _finish() async {
    await _storage.write(key: 'onboarded', value: 'true');
    if (!mounted) return;
    context.go('/login');
  }

  @override
  void dispose() {
    _pageCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.surface0,
      body: Stack(
        children: [
          const Positioned.fill(child: ParticleField(count: 18)),
          SafeArea(
            child: Column(
              children: [
                const SizedBox(height: 8),
                // Skip button top-right
                Align(
                  alignment: Alignment.centerRight,
                  child: Padding(
                    padding: const EdgeInsets.only(right: 16),
                    child: TextButton(
                      onPressed: _finish,
                      child: const Text(
                        'Passer',
                        style: TextStyle(
                            color: AppColors.textSecondary, fontSize: 14),
                      ),
                    ),
                  ),
                ),
                // Slides
                Expanded(
                  child: PageView.builder(
                    controller: _pageCtrl,
                    onPageChanged: (p) => setState(() => _idx = p),
                    itemCount: _steps.length,
                    itemBuilder: (_, i) => _SlideCard(step: _steps[i], idx: i),
                  ),
                ),
                // Bottom: progress pill + button
                Padding(
                  padding: const EdgeInsets.fromLTRB(24, 0, 24, 32),
                  child: Column(
                    children: [
                      // Progress pill bar
                      Container(
                        height: 4,
                        decoration: BoxDecoration(
                          color: const Color(0x1A94A3B8),
                          borderRadius: BorderRadius.circular(99),
                        ),
                        child: Align(
                          alignment: Alignment.centerLeft,
                          child: AnimatedFractionallySizedBox(
                            duration: const Duration(milliseconds: 400),
                            widthFactor: (_idx + 1) / _steps.length,
                            child: Container(
                              decoration: BoxDecoration(
                                gradient: AppColors.aiGrad,
                                borderRadius: BorderRadius.circular(99),
                              ),
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(height: 24),
                      // Full-width gradient button
                      SizedBox(
                        width: double.infinity,
                        height: 54,
                        child: DecoratedBox(
                          decoration: BoxDecoration(
                            gradient: AppColors.aiGrad,
                            borderRadius: BorderRadius.circular(16),
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
                            onPressed: _next,
                            style: ElevatedButton.styleFrom(
                              backgroundColor: Colors.transparent,
                              shadowColor: Colors.transparent,
                              shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(16)),
                            ),
                            child: Text(
                              _idx < _steps.length - 1
                                  ? 'Continuer'
                                  : 'Commencer',
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 15,
                                fontWeight: FontWeight.w600,
                                letterSpacing: 0.15,
                              ),
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _SlideCard extends StatelessWidget {
  final _Step step;
  final int idx;
  const _SlideCard({required this.step, required this.idx});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 32),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          // 130×130 rounded square with gradient bg + inner radial glow
          SizedBox(
            width: 130,
            height: 130,
            child: Stack(
              children: [
                // Container background
                Container(
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(40),
                    gradient: const LinearGradient(
                      begin: Alignment(-0.6, -0.6),
                      end: Alignment(1, 1),
                      colors: [
                        Color(0x2E6366F1), // rgba(99,102,241,0.18)
                        Color(0x0F8B5CF6), // rgba(139,92,246,0.06)
                      ],
                    ),
                    border: Border.all(
                      color: const Color(0x408B5CF6), // rgba(139,92,246,0.25)
                    ),
                  ),
                ),
                // Inner radial glow
                Positioned.fill(
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(40),
                    child: Container(
                      decoration: const BoxDecoration(
                        gradient: RadialGradient(
                          center: Alignment(-0.4, -0.4),
                          radius: 0.9,
                          colors: [
                            Color(0x666366F1), // rgba(99,102,241,0.4)
                            Colors.transparent,
                          ],
                          stops: [0.0, 0.6],
                        ),
                      ),
                    ),
                  ),
                ),
                // Icon
                Center(
                  child: Icon(step.icon,
                      size: 56, color: const Color(0xFFC4B5FD)),
                ),
              ],
            ),
          ),
          const SizedBox(height: 36),
          // Step counter tag
          Text(
            '0${idx + 1} / 03 · ${step.tag}',
            style: const TextStyle(
              fontSize: 10,
              letterSpacing: 1.8,
              color: Color(0xFF64748B),
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: 14),
          // Title
          Text(
            step.title,
            textAlign: TextAlign.center,
            style: const TextStyle(
              color: AppColors.textPrimary,
              fontSize: 30,
              fontWeight: FontWeight.w600,
              height: 1.15,
              letterSpacing: -0.5,
            ),
          ),
          const SizedBox(height: 18),
          // Description
          Text(
            step.desc,
            textAlign: TextAlign.center,
            style: const TextStyle(
              color: AppColors.textSecondary,
              fontSize: 15,
              height: 1.55,
            ),
          ),
        ],
      ),
    );
  }
}
