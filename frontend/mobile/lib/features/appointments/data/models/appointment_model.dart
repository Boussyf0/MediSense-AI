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
  final String doctorName;
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
    this.noShowProbability,
  });

  factory AppointmentModel.fromJson(Map<String, dynamic> j) {
    final rc = switch (j['risk_color'] as String?) {
      'green'  => RiskColor.green,
      'orange' => RiskColor.orange,
      'red'    => RiskColor.red,
      _        => RiskColor.unknown,
    };
    final st = switch ((j['status'] as String?)?.toUpperCase()) {
      'SCHEDULED' => AppointmentStatus.scheduled,
      'CONFIRMED' => AppointmentStatus.confirmed,
      'CANCELLED' => AppointmentStatus.cancelled,
      'COMPLETED' => AppointmentStatus.completed,
      'NO_SHOW'   => AppointmentStatus.noShow,
      _           => AppointmentStatus.unknown,
    };
    return AppointmentModel(
      id: j['appointment_uuid'] as String? ?? j['id'] as String? ?? '',
      time: j['appointment_time'] as String? ?? j['time'] as String? ?? '',
      doctorName: j['doctor_name'] as String? ?? 'Dr. —',
      appointmentType: j['appointment_type'] as String? ?? 'Consultation',
      riskColor: rc,
      status: st,
      noShowProbability: (j['noshow_probability'] as num?)?.toDouble(),
    );
  }
}
