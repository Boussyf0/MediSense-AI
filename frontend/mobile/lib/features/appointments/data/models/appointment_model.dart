import 'package:flutter/material.dart';
import '../../../../core/theme/app_colors.dart';

enum RiskColor { green, orange, red, unknown }

extension RiskColorExt on RiskColor {
  String get label => switch (this) {
        RiskColor.green => 'Faible risque',
        RiskColor.orange => 'Risque modéré',
        RiskColor.red => 'Risque élevé',
        RiskColor.unknown => 'Non calculé',
      };

  Color get color => switch (this) {
        RiskColor.green => AppColors.riskSafe,
        RiskColor.orange => AppColors.riskWarn,
        RiskColor.red => AppColors.riskHigh,
        RiskColor.unknown => const Color(0xFF64748B),
      };

  String get icon => switch (this) {
        RiskColor.green => '🟢',
        RiskColor.orange => '🟡',
        RiskColor.red => '🔴',
        RiskColor.unknown => '⚫',
      };
}

enum AppointmentStatus { scheduled, confirmed, cancelled, completed, noShow, unknown }

extension AppointmentStatusExt on AppointmentStatus {
  String get label => switch (this) {
        AppointmentStatus.scheduled => 'Planifié',
        AppointmentStatus.confirmed => 'Confirmé',
        AppointmentStatus.cancelled => 'Annulé',
        AppointmentStatus.completed => 'Terminé',
        AppointmentStatus.noShow    => 'Absent',
        AppointmentStatus.unknown   => '—',
      };

  Color get color => switch (this) {
        AppointmentStatus.confirmed || AppointmentStatus.completed => const Color(0xFF22C55E),
        AppointmentStatus.cancelled || AppointmentStatus.noShow    => const Color(0xFFEF4444),
        AppointmentStatus.scheduled                                => const Color(0xFFA78BFA),
        AppointmentStatus.unknown                                  => const Color(0xFF64748B),
      };
}

class AppointmentModel {
  final String id;
  final String time;
  final DateTime? scheduledAt;
  final int durationMinutes;
  final int priceMad;
  final String doctorName;
  final String? doctorSpecialty;
  final String appointmentType;
  final RiskColor riskColor;
  final double? noShowProbability;
  final AppointmentStatus status;

  const AppointmentModel({
    required this.id,
    required this.time,
    required this.doctorName,
    required this.appointmentType,
    required this.riskColor,
    required this.status,
    required this.durationMinutes,
    required this.priceMad,
    this.scheduledAt,
    this.doctorSpecialty,
    this.noShowProbability,
  });

  /// True when the visit window has elapsed but the appointment is still in
  /// a non-terminal state. Lets the patient UI surface "Terminé" automatically
  /// without waiting for a backend transition.
  bool get isElapsedButOpen {
    if (scheduledAt == null) return false;
    if (status == AppointmentStatus.cancelled ||
        status == AppointmentStatus.completed ||
        status == AppointmentStatus.noShow) {
      return false;
    }
    final endsAt =
        scheduledAt!.add(Duration(minutes: durationMinutes));
    return DateTime.now().toUtc().isAfter(endsAt.toUtc());
  }

  /// Backend hardcodes appointment_type to "Consultation" today; teleconsult
  /// is signalled by the string containing "télé"/"tele"/"visio". Once a real
  /// telehealth flag lands in the schema this collapses to a single field.
  bool get isTeleconsult {
    final t = appointmentType.toLowerCase();
    return t.contains('télé') ||
        t.contains('tele') ||
        t.contains('visio') ||
        t.contains('video');
  }

  /// Distance from now to `scheduledAt`. Negative if in the past.
  Duration? get timeUntilStart {
    if (scheduledAt == null) return null;
    return scheduledAt!.difference(DateTime.now());
  }

  factory AppointmentModel.fromJson(Map<String, dynamic> j) {
    final rc = switch (j['risk_color'] as String?) {
      'green'  => RiskColor.green,
      'orange' => RiskColor.orange,
      'red'    => RiskColor.red,
      _        => RiskColor.unknown,
    };
    final st = switch ((j['status'] as String?)?.toUpperCase()) {
      'PENDING' || 'SCHEDULED' => AppointmentStatus.scheduled,
      'CONFIRMED'              => AppointmentStatus.confirmed,
      'CANCELLED'              => AppointmentStatus.cancelled,
      'COMPLETED'              => AppointmentStatus.completed,
      'NO_SHOW'                => AppointmentStatus.noShow,
      _                        => AppointmentStatus.unknown,
    };
    DateTime? scheduledAt;
    final rawScheduled = j['scheduled_at'] as String?;
    if (rawScheduled != null) {
      try {
        scheduledAt = DateTime.parse(rawScheduled);
      } catch (e) {
        debugPrint('Appointment scheduled_at parse failed: $e');
      }
    }
    return AppointmentModel(
      id: j['appointment_uuid'] as String? ?? j['id'] as String? ?? '',
      time: j['appointment_time'] as String? ?? j['time'] as String? ?? '',
      scheduledAt: scheduledAt,
      durationMinutes: (j['duration_minutes'] as num?)?.toInt() ?? 20,
      priceMad: (j['price_mad'] as num?)?.toInt() ?? 0,
      doctorName: j['doctor_name'] as String? ?? 'Dr. —',
      doctorSpecialty: j['doctor_specialty'] as String?,
      appointmentType: j['appointment_type'] as String? ?? 'Consultation',
      riskColor: rc,
      status: st,
      noShowProbability: (j['noshow_probability'] as num?)?.toDouble(),
    );
  }
}
