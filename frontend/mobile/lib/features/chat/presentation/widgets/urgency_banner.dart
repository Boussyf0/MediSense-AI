import 'package:flutter/material.dart';
import '../../../../core/theme/app_fonts.dart';

/// Urgency banner — gradient red, pulsing alert icon, "Appeler 141" CTA.
/// Mirrors `chat.jsx > UrgencyBanner`.
class UrgencyBanner extends StatefulWidget {
  final VoidCallback? onCall;
  final VoidCallback? onDismiss;
  const UrgencyBanner({super.key, this.onCall, this.onDismiss});

  @override
  State<UrgencyBanner> createState() => _UrgencyBannerState();
}

class _UrgencyBannerState extends State<UrgencyBanner>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 8, 16, 0),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(14),
        gradient: const LinearGradient(
          begin: Alignment(-0.8, 0),
          end: Alignment(1, 0),
          colors: [Color(0xFFF43F5E), Color(0xFFDC2626)],
        ),
        boxShadow: const [
          BoxShadow(
            color: Color(0x59F43F5E),
            blurRadius: 28,
            offset: Offset(0, 8),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        child: Row(
          children: [
            AnimatedBuilder(
              animation: _ctrl,
              builder: (_, __) {
                final s = 0.94 + 0.12 * _ctrl.value;
                return Transform.scale(
                  scale: s,
                  child: Container(
                    width: 36,
                    height: 36,
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.18),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: const Icon(
                      Icons.warning_amber_rounded,
                      color: Colors.white,
                      size: 20,
                    ),
                  ),
                );
              },
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    'Urgence détectée — appelez maintenant',
                    style: AppFonts.body(
                      color: Colors.white,
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    '141 · SAMU MAROC',
                    style: AppFonts.mono(
                      color: Colors.white.withValues(alpha: 0.85),
                      fontSize: 10,
                      letterSpacing: 0.6,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            GestureDetector(
              onTap: widget.onCall,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(99),
                ),
                child: Text(
                  'Appeler 141',
                  style: AppFonts.body(
                    color: const Color(0xFFDC2626),
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
