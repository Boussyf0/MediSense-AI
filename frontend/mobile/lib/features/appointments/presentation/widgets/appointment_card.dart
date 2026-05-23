import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_fonts.dart';
import '../../../../core/widgets/anim/bubble_in.dart';
import '../../data/models/appointment_model.dart';

class _StatusChip extends StatelessWidget {
  final Color color;
  final String label;
  const _StatusChip({required this.color, required this.label});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(99),
        border: Border.all(color: color.withValues(alpha: 0.30)),
      ),
      child: Text(
        label,
        style: AppFonts.body(
          color: color,
          fontSize: 11,
          fontWeight: FontWeight.w600,
          letterSpacing: 0.1,
        ),
      ),
    );
  }
}

class _InfoPill extends StatelessWidget {
  final IconData icon;
  final String text;
  const _InfoPill({required this.icon, required this.text});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 13, color: AppColors.textMuted),
        const SizedBox(width: 4),
        Text(
          text,
          style: AppFonts.body(
            color: AppColors.textSecondary,
            fontSize: 12,
            fontWeight: FontWeight.w500,
          ),
        ),
      ],
    );
  }
}

/// Risk-coded appointment card — full details for patients (date, duration,
/// specialty, price) and the same density for staff. Auto-derives "Terminé"
/// when the visit window has elapsed.
class AppointmentCard extends StatelessWidget {
  final AppointmentModel appointment;
  final int index;
  final String? patientName;
  final int? patientAge;
  final String? reason;
  final bool isPatientView;
  final VoidCallback? onTap;

  const AppointmentCard({
    super.key,
    required this.appointment,
    this.index = 0,
    this.patientName,
    this.patientAge,
    this.reason,
    this.isPatientView = false,
    this.onTap,
  });

  String _formatTime(String raw) {
    try {
      final dt = DateTime.parse(raw);
      return DateFormat('HH:mm').format(dt);
    } catch (_) {
      return raw;
    }
  }

  String get _riskLabel => switch (appointment.riskColor) {
        RiskColor.red => 'Risque élevé',
        RiskColor.orange => 'Risque modéré',
        RiskColor.green => 'Risque faible',
        RiskColor.unknown => 'Non calculé',
      };

  ({Color color, String label}) _resolvedStatus() {
    final s = appointment.status;
    if (s == AppointmentStatus.completed) {
      return (color: s.color, label: 'Terminé par le docteur');
    }
    if (appointment.isElapsedButOpen) {
      return (color: const Color(0xFF22C55E), label: 'Terminé');
    }
    return (color: s.color, label: s.label);
  }

  @override
  Widget build(BuildContext context) {
    final color = appointment.riskColor.color;
    final scorePct = appointment.noShowProbability != null
        ? (appointment.noShowProbability! * 100).round()
        : null;
    final name = patientName ?? appointment.doctorName;
    final reasonText = reason ?? appointment.appointmentType;
    final dateLabel = appointment.scheduledAt != null
        ? DateFormat('EEE d MMM', 'fr_FR').format(appointment.scheduledAt!)
        : null;
    final resolved = _resolvedStatus();

    return BubbleIn(
      delay: Duration(milliseconds: 40 * index),
      child: GestureDetector(
        onTap: onTap,
        behavior: HitTestBehavior.opaque,
        child: Container(
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.fromLTRB(16, 14, 12, 14),
        decoration: BoxDecoration(
          color: AppColors.surface1,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppColors.line),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // glowing dot + time column
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    width: 10,
                    height: 10,
                    decoration: BoxDecoration(
                      color: color,
                      shape: BoxShape.circle,
                      boxShadow: [
                        BoxShadow(
                          color: color.withValues(alpha: 0.5),
                          blurRadius: 10,
                          spreadRadius: 2,
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    _formatTime(appointment.time),
                    style: AppFonts.mono(
                      color: AppColors.text1,
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      letterSpacing: 0.4,
                    ),
                  ),
                  if (dateLabel != null) ...[
                    const SizedBox(height: 2),
                    Text(
                      dateLabel,
                      style: AppFonts.mono(
                        color: AppColors.textMuted,
                        fontSize: 9,
                        letterSpacing: 0.2,
                      ),
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(width: 14),
            // Main column
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  // name + age
                  RichText(
                    text: TextSpan(
                      style: AppFonts.display(
                        color: AppColors.textPrimary,
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                        letterSpacing: -0.075,
                      ),
                      children: [
                        TextSpan(text: name),
                        if (patientAge != null)
                          TextSpan(
                            text: '  · ${patientAge}a',
                            style: AppFonts.mono(
                              color: AppColors.textMuted,
                              fontSize: 11,
                              fontWeight: FontWeight.w400,
                            ),
                          ),
                      ],
                    ),
                  ),
                  if (isPatientView && appointment.doctorSpecialty != null) ...[
                    const SizedBox(height: 2),
                    Text(
                      appointment.doctorSpecialty!,
                      style: AppFonts.body(
                        color: AppColors.textSecondary,
                        fontSize: 12,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                  if (!isPatientView) ...[
                    const SizedBox(height: 2),
                    Text(
                      appointment.doctorName,
                      style: AppFonts.body(
                        color: AppColors.textSecondary,
                        fontSize: 12,
                      ),
                    ),
                  ],
                  const SizedBox(height: 8),
                  Text(
                    reasonText,
                    style: AppFonts.body(
                      color: AppColors.text1,
                      fontSize: 12,
                      height: 1.4,
                    ),
                  ),
                  const SizedBox(height: 8),
                  // Duration + price line — always shown so patients know
                  // how long the slot is and how much it costs.
                  Wrap(
                    spacing: 10,
                    runSpacing: 4,
                    children: [
                      _InfoPill(
                        icon: Icons.schedule_rounded,
                        text: '${appointment.durationMinutes} min',
                      ),
                      if (appointment.priceMad > 0)
                        _InfoPill(
                          icon: Icons.payments_outlined,
                          text: '${appointment.priceMad} MAD',
                        ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  // Status chip; risk chip is hidden in patient view
                  Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    children: [
                      _StatusChip(
                        color: resolved.color,
                        label: resolved.label,
                      ),
                      if (!isPatientView) Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 10, vertical: 4),
                        decoration: BoxDecoration(
                          color: color.withValues(alpha: 0.10),
                          borderRadius: BorderRadius.circular(99),
                          border: Border.all(
                            color: color.withValues(alpha: 0.25),
                          ),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Container(
                              width: 6,
                              height: 6,
                              decoration: BoxDecoration(
                                color: color,
                                shape: BoxShape.circle,
                              ),
                            ),
                            const SizedBox(width: 6),
                            Text(
                              _riskLabel,
                              style: AppFonts.body(
                                color: color,
                                fontSize: 11,
                                fontWeight: FontWeight.w600,
                                letterSpacing: 0.1,
                              ),
                            ),
                            if (scorePct != null) ...[
                              const SizedBox(width: 6),
                              Text(
                                '· $scorePct%',
                                style: AppFonts.mono(
                                  color: color.withValues(alpha: 0.85),
                                  fontSize: 10,
                                ),
                              ),
                            ],
                          ],
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(width: 6),
            const Icon(
              Icons.chevron_right_rounded,
              color: AppColors.textMuted,
              size: 18,
            ),
          ],
        ),
      ),
      ),
    );
  }
}
