import 'package:flutter_test/flutter_test.dart';
import 'package:medisense_ai/features/appointments/data/models/appointment_model.dart';

void main() {
  group('AppointmentModel.fromJson', () {
    test('parses all fields', () {
      final json = {
        'appointment_uuid': 'abc-123',
        'appointment_time': '10:30',
        'scheduled_at': '2026-06-01T10:30:00Z',
        'duration_minutes': 30,
        'price_mad': 350,
        'doctor_name': 'Dr. Merrouni',
        'doctor_specialty': 'Cardiologie',
        'appointment_type': 'Consultation',
        'risk_color': 'green',
        'status': 'CONFIRMED',
        'noshow_probability': 0.12,
      };
      final m = AppointmentModel.fromJson(json);
      expect(m.id, 'abc-123');
      expect(m.time, '10:30');
      expect(m.scheduledAt, isNotNull);
      expect(m.durationMinutes, 30);
      expect(m.priceMad, 350);
      expect(m.doctorName, 'Dr. Merrouni');
      expect(m.doctorSpecialty, 'Cardiologie');
      expect(m.appointmentType, 'Consultation');
      expect(m.riskColor, RiskColor.green);
      expect(m.status, AppointmentStatus.confirmed);
      expect(m.noShowProbability, 0.12);
    });

    test('defaults missing fields', () {
      final m = AppointmentModel.fromJson(<String, dynamic>{});
      expect(m.id, '');
      expect(m.time, '');
      expect(m.scheduledAt, isNull);
      expect(m.durationMinutes, 20);
      expect(m.priceMad, 0);
      expect(m.doctorName, 'Dr. —');
      expect(m.appointmentType, 'Consultation');
      expect(m.riskColor, RiskColor.unknown);
      expect(m.status, AppointmentStatus.unknown);
    });

    test('parses risk colors', () {
      for (final entry in {
        'green': RiskColor.green,
        'orange': RiskColor.orange,
        'red': RiskColor.red,
        'banana': RiskColor.unknown,
        null: RiskColor.unknown,
      }.entries) {
        final m = AppointmentModel.fromJson({'risk_color': entry.key});
        expect(m.riskColor, entry.value, reason: 'risk_color=${entry.key}');
      }
    });

    test('parses statuses', () {
      for (final entry in {
        'PENDING': AppointmentStatus.scheduled,
        'SCHEDULED': AppointmentStatus.scheduled,
        'CONFIRMED': AppointmentStatus.confirmed,
        'CANCELLED': AppointmentStatus.cancelled,
        'COMPLETED': AppointmentStatus.completed,
        'NO_SHOW': AppointmentStatus.noShow,
        'UNKNOWN_VALUE': AppointmentStatus.unknown,
        null: AppointmentStatus.unknown,
      }.entries) {
        final m = AppointmentModel.fromJson({'status': entry.key});
        expect(m.status, entry.value, reason: 'status=${entry.key}');
      }
    });
  });

  group('AppointmentModel computed properties', () {
    test('isElapsedButOpen true when past end and non-terminal', () {
      final m = AppointmentModel(
        id: '1',
        time: '08:00',
        doctorName: 'Dr. X',
        appointmentType: 'Consultation',
        riskColor: RiskColor.green,
        status: AppointmentStatus.scheduled,
        durationMinutes: 20,
        priceMad: 200,
        scheduledAt: DateTime.now().toUtc().subtract(const Duration(hours: 2)),
      );
      expect(m.isElapsedButOpen, isTrue);
    });

    test('isElapsedButOpen false for terminal status', () {
      final m = AppointmentModel(
        id: '1',
        time: '08:00',
        doctorName: 'Dr. X',
        appointmentType: 'Consultation',
        riskColor: RiskColor.green,
        status: AppointmentStatus.completed,
        durationMinutes: 20,
        priceMad: 200,
        scheduledAt: DateTime.now().toUtc().subtract(const Duration(hours: 2)),
      );
      expect(m.isElapsedButOpen, isFalse);
    });

    test('isTeleconsult detects keywords', () {
      for (final keyword in ['Téléconsultation', 'teleconsult', 'Visio', 'Video call']) {
        final m = AppointmentModel(
          id: '1',
          time: '08:00',
          doctorName: 'Dr. X',
          appointmentType: keyword,
          riskColor: RiskColor.green,
          status: AppointmentStatus.scheduled,
          durationMinutes: 20,
          priceMad: 0,
        );
        expect(m.isTeleconsult, isTrue, reason: 'keyword=$keyword');
      }
      // Regular consultation is NOT teleconsult
      final m = AppointmentModel(
        id: '1',
        time: '08:00',
        doctorName: 'Dr. X',
        appointmentType: 'Consultation',
        riskColor: RiskColor.green,
        status: AppointmentStatus.scheduled,
        durationMinutes: 20,
        priceMad: 0,
      );
      expect(m.isTeleconsult, isFalse);
    });

    test('timeUntilStart returns duration for future appointments', () {
      final futureTime = DateTime.now().add(const Duration(hours: 1));
      final m = AppointmentModel(
        id: '1',
        time: '10:00',
        doctorName: 'Dr. X',
        appointmentType: 'Consultation',
        riskColor: RiskColor.green,
        status: AppointmentStatus.scheduled,
        durationMinutes: 20,
        priceMad: 0,
        scheduledAt: futureTime,
      );
      expect(m.timeUntilStart, isNotNull);
      expect(m.timeUntilStart!.inMinutes, greaterThan(50));
    });
  });
}
