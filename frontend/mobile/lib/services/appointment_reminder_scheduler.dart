/// Schedules local notifications 1 hour before each upcoming appointment.
///
/// Why local-only? FCM push reminders depend on backend cron + a working
/// push token; this is a belt-and-suspenders second layer that runs purely
/// on-device. The scheduler is idempotent: each call to [syncFromAppointments]
/// cancels prior reminder IDs and re-creates the ones still in the future.
library;

import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:timezone/data/latest_all.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

import '../features/appointments/data/models/appointment_model.dart';

class AppointmentReminderScheduler {
  AppointmentReminderScheduler._();
  static final AppointmentReminderScheduler instance =
      AppointmentReminderScheduler._();

  static const _channelId = 'medisense_appt_reminders';
  static const _channelName = 'Rappels rendez-vous';
  static const Duration _leadTime = Duration(hours: 1);

  final FlutterLocalNotificationsPlugin _plugin =
      FlutterLocalNotificationsPlugin();
  bool _ready = false;
  // Reminder notification ids tracked across syncs so we can cancel stale ones.
  final Set<int> _scheduledIds = <int>{};

  Future<void> _ensureReady() async {
    if (_ready) return;
    tzdata.initializeTimeZones();
    const android = AndroidInitializationSettings('@mipmap/ic_launcher');
    const ios = DarwinInitializationSettings(
      requestAlertPermission: true,
      requestBadgePermission: true,
      requestSoundPermission: true,
    );
    await _plugin.initialize(
      const InitializationSettings(android: android, iOS: ios),
    );
    _ready = true;
  }

  int _idFor(String appointmentUuid) =>
      ('appt:$appointmentUuid').hashCode & 0x7fffffff;

  Future<void> syncFromAppointments(List<AppointmentModel> appointments) async {
    await _ensureReady();
    final now = DateTime.now();

    // Cancel anything previously scheduled so removed/cancelled appts don't
    // keep firing.
    for (final id in _scheduledIds) {
      await _plugin.cancel(id);
    }
    _scheduledIds.clear();

    for (final a in appointments) {
      final at = a.scheduledAt;
      if (at == null) continue;
      if (a.status == AppointmentStatus.cancelled ||
          a.status == AppointmentStatus.completed ||
          a.status == AppointmentStatus.noShow) {
        continue;
      }
      final remindAt = at.subtract(_leadTime);
      if (!remindAt.isAfter(now)) continue;

      final id = _idFor(a.id);
      try {
        await _plugin.zonedSchedule(
          id,
          'Rappel — ${a.doctorName}',
          'Rendez-vous dans 1h à ${a.time}'
              '${a.doctorSpecialty != null ? " · ${a.doctorSpecialty}" : ""}',
          tz.TZDateTime.from(remindAt, tz.local),
          NotificationDetails(
            android: const AndroidNotificationDetails(
              _channelId,
              _channelName,
              importance: Importance.high,
              priority: Priority.high,
            ),
            iOS: const DarwinNotificationDetails(),
          ),
          payload: a.id,
          androidScheduleMode: AndroidScheduleMode.inexactAllowWhileIdle,
          uiLocalNotificationDateInterpretation:
              UILocalNotificationDateInterpretation.absoluteTime,
        );
        _scheduledIds.add(id);
      } catch (e) {
        debugPrint('AppointmentReminderScheduler: $e');
      }
    }
  }
}
