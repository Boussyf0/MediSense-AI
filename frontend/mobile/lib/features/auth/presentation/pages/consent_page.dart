import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:go_router/go_router.dart';
import '../../../../core/theme/app_colors.dart';
import '../providers/auth_provider.dart';

class ConsentPage extends ConsumerStatefulWidget {
  const ConsentPage({super.key});
  @override
  ConsumerState<ConsentPage> createState() => _ConsentPageState();
}

class _ConsentPageState extends ConsumerState<ConsentPage> {
  bool _iot = true;
  bool _nlp = true;
  bool _sharing = false;
  bool _loading = false;
  final _storage = const FlutterSecureStorage();

  Future<void> _confirm({bool allOff = false}) async {
    setState(() => _loading = true);
    try {
      await ref.read(authDatasourceProvider).updateConsent(
            consentIot: allOff ? false : _iot,
            consentNlp: allOff ? false : _nlp,
            consentSharing: allOff ? false : _sharing,
          );
    } catch (e) {
      debugPrint('Consent update failed: $e');
    }
    await _storage.write(key: 'consent_given', value: 'true');
    if (!mounted) return;
    setState(() => _loading = false);
    if (allOff) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content:
              Text('Consentement refusé — certaines fonctionnalités seront limitées.'),
          backgroundColor: AppColors.riskWarn,
        ),
      );
    }
    context.go('/home');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.surface0,
      body: SafeArea(
        child: Column(
          children: [
            const SizedBox(height: 32),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: AppColors.aiFrom.withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: const Icon(Icons.shield_outlined,
                            color: AppColors.aiFrom, size: 22),
                      ),
                      const SizedBox(width: 12),
                      const Text(
                        'Vos données, votre contrôle',
                        style: TextStyle(
                          color: AppColors.textPrimary,
                          fontSize: 20,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Choisissez comment MediSense AI peut utiliser vos données. Vous pouvez modifier ces paramètres à tout moment.',
                    style: TextStyle(
                      color: AppColors.textMuted,
                      fontSize: 13,
                      height: 1.5,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.symmetric(horizontal: 24),
                children: [
                  _ConsentTile(
                    icon: Icons.monitor_heart_outlined,
                    iconColor: AppColors.pulse,
                    title: 'Capteurs IoT & Biométrie',
                    description:
                        'Permettre la collecte de vos données biométriques (FC, SpO2, HRV) depuis vos appareils connectés pour le suivi en temps réel.',
                    value: _iot,
                    onChanged: (v) => setState(() => _iot = v),
                  ),
                  const SizedBox(height: 12),
                  _ConsentTile(
                    icon: Icons.psychology_outlined,
                    iconColor: AppColors.aiFrom,
                    title: 'Traitement NLP & IA',
                    description:
                        'Permettre le traitement de vos conversations par notre moteur IA (RAG + Mistral-7B) pour des réponses médicales personnalisées.',
                    value: _nlp,
                    onChanged: (v) => setState(() => _nlp = v),
                  ),
                  const SizedBox(height: 12),
                  _ConsentTile(
                    icon: Icons.share_outlined,
                    iconColor: AppColors.riskSafe,
                    title: 'Partage avec votre médecin',
                    description:
                        'Autoriser le partage de vos données agrégées avec votre équipe soignante pour améliorer votre suivi médical.',
                    value: _sharing,
                    onChanged: (v) => setState(() => _sharing = v),
                  ),
                  const SizedBox(height: 24),
                  Container(
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: AppColors.surface2,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: AppColors.line),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.info_outline,
                            color: AppColors.textMuted, size: 16),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            'Toutes les données sont chiffrées AES-256. Vous disposez d\'un droit d\'accès, de rectification et d\'effacement (RGPD Art. 17).',
                            style: TextStyle(
                              color: AppColors.textMuted
                                  .withValues(alpha: 0.8),
                              fontSize: 11,
                              height: 1.5,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                children: [
                  SizedBox(
                    width: double.infinity,
                    child: Container(
                      decoration: BoxDecoration(
                        gradient: _loading ? null : AppColors.aiGrad,
                        color: _loading ? AppColors.surface3 : null,
                        borderRadius: BorderRadius.circular(999),
                      ),
                      child: ElevatedButton(
                        onPressed: _loading ? null : () => _confirm(),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.transparent,
                          shadowColor: Colors.transparent,
                          padding: const EdgeInsets.symmetric(vertical: 16),
                          shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(999)),
                        ),
                        child: _loading
                            ? const SizedBox(
                                width: 20,
                                height: 20,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: Colors.white,
                                ),
                              )
                            : const Text(
                                'Confirmer mes choix',
                                style: TextStyle(
                                  color: Colors.white,
                                  fontSize: 16,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextButton(
                    onPressed:
                        _loading ? null : () => _confirm(allOff: true),
                    child: const Text(
                      'Ignorer pour l\'instant',
                      style: TextStyle(
                          color: AppColors.textMuted, fontSize: 13),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ConsentTile extends StatelessWidget {
  final IconData icon;
  final Color iconColor;
  final String title;
  final String description;
  final bool value;
  final ValueChanged<bool> onChanged;

  const _ConsentTile({
    required this.icon,
    required this.iconColor,
    required this.title,
    required this.description,
    required this.value,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(14),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        decoration: BoxDecoration(
          color: value ? AppColors.surface2 : AppColors.surface1,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppColors.line),
        ),
        child: Stack(
          children: [
            AnimatedPositioned(
              duration: const Duration(milliseconds: 200),
              left: 0,
              top: 0,
              bottom: 0,
              width: value ? 4 : 0,
              child: Container(color: iconColor),
            ),
            Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: (value ? iconColor : AppColors.textMuted)
                          .withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Icon(
                      icon,
                      size: 20,
                      color: value ? iconColor : AppColors.textMuted,
                    ),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          title,
                          style: TextStyle(
                            color: value
                                ? AppColors.textPrimary
                                : AppColors.textSecondary,
                            fontSize: 14,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          description,
                          style: const TextStyle(
                            color: AppColors.textMuted,
                            fontSize: 12,
                            height: 1.5,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 8),
                  Switch(
                    value: value,
                    onChanged: onChanged,
                    activeThumbColor: iconColor,
                    activeTrackColor: iconColor.withValues(alpha: 0.3),
                    inactiveThumbColor: AppColors.textMuted,
                    inactiveTrackColor: AppColors.surface3,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
