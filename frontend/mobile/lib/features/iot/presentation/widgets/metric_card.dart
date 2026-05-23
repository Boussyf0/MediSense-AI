import 'package:flutter/material.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_fonts.dart';
import '../../../../core/widgets/anim/count_up.dart';

/// Vital metric card — radial color glow, gradient icon chip, large
/// CountUp value, mono uppercase label, trend chip. Mirrors `vitals.jsx >
/// VitalCard`.
class MetricCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final String name;
  final num? value;
  final String unit;
  final Color color;
  final String trend;
  final String trendDir;
  final bool active;
  final VoidCallback? onTap;

  const MetricCard({
    super.key,
    required this.icon,
    required this.label,
    required this.name,
    required this.value,
    required this.unit,
    required this.color,
    required this.trend,
    required this.trendDir,
    this.active = false,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 250),
        width: 168,
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.surface1,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(
            color: active
                ? color.withValues(alpha: 0.33)
                : AppColors.line,
          ),
          boxShadow: active
              ? [
                  BoxShadow(
                    color: color.withValues(alpha: 0.13),
                    blurRadius: 32,
                    offset: const Offset(0, 12),
                  ),
                ]
              : null,
        ),
        child: Stack(
          clipBehavior: Clip.none,
          children: [
            // Radial glow blob
            Positioned(
              top: -20,
              right: -20,
              child: Container(
                width: 80,
                height: 80,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: RadialGradient(
                    colors: [
                      color.withValues(alpha: 0.2),
                      Colors.transparent,
                    ],
                    stops: const [0.0, 0.7],
                  ),
                ),
              ),
            ),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 32,
                  height: 32,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.13),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(icon, color: color, size: 18),
                ),
                const SizedBox(height: 16),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    if (value == null)
                      Text(
                        '—',
                        style: AppFonts.display(
                          color: color,
                          fontSize: 40,
                          fontWeight: FontWeight.w600,
                          letterSpacing: -0.8,
                          height: 1,
                        ),
                      )
                    else
                      CountUp(
                        value: value!,
                        style: AppFonts.display(
                          color: color,
                          fontSize: 40,
                          fontWeight: FontWeight.w600,
                          letterSpacing: -0.8,
                          height: 1,
                          shadows: [
                            Shadow(
                              color: color.withValues(alpha: 0.33),
                              blurRadius: 20,
                            ),
                          ],
                        ),
                      ),
                    if (unit.isNotEmpty && value != null)
                      Padding(
                        padding: const EdgeInsets.only(left: 2, bottom: 4),
                        child: Text(
                          unit,
                          style: AppFonts.body(
                            color: AppColors.textSecondary,
                            fontSize: 14,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ),
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  label.toUpperCase(),
                  style: AppFonts.mono(
                    color: AppColors.textMuted,
                    fontSize: 9.5,
                    letterSpacing: 1.4,
                  ),
                ),
                const SizedBox(height: 10),
                Row(
                  children: [
                    Text(
                      trendDir,
                      style: AppFonts.body(
                        color: color,
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(width: 4),
                    Flexible(
                      child: Text(
                        trend,
                        overflow: TextOverflow.ellipsis,
                        style: AppFonts.body(
                          color: AppColors.text1,
                          fontSize: 11,
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
