/// Inbox polling fallback for clients without working FCM (iOS without APNs).
///
/// On `start()` the poller baselines the current unread notifications, then
/// periodically calls `GET /notifications?unread_only=true`, dedupes against ids
/// seen so far, and surfaces genuinely-new items as local notifications.
/// Designed to coexist with FCM: if push delivery already fired for an item, the
/// dedupe set drops it on the next poll.
library;

import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

import '../core/api/dio_client.dart';

class InboxPoller {
  InboxPoller._();
  static final InboxPoller instance = InboxPoller._();

  static const _channelId = 'medisense_reminders';
  static const _channelName = 'Rappels MediSense';
  static const _defaultInterval = Duration(seconds: 30);

  final FlutterLocalNotificationsPlugin _plugin =
      FlutterLocalNotificationsPlugin();
  final Set<String> _seen = <String>{};
  Timer? _timer;
  bool _localNotifReady = false;

  Future<void> _ensureLocalNotifs() async {
    if (_localNotifReady) return;
    const android = AndroidInitializationSettings('@mipmap/ic_launcher');
    const ios = DarwinInitializationSettings(
      requestAlertPermission: true,
      requestBadgePermission: true,
      requestSoundPermission: true,
    );
    await _plugin.initialize(
      const InitializationSettings(android: android, iOS: ios),
    );
    _localNotifReady = true;
  }

  Future<void> start({Duration interval = _defaultInterval}) async {
    if (_timer != null) return;
    await _ensureLocalNotifs();
    await _prime();
    _timer = Timer.periodic(interval, (_) => _poll());
  }

  void stop() {
    _timer?.cancel();
    _timer = null;
    _seen.clear();
  }

  /// Baseline the unread notifications already present at startup (mark them
  /// seen without notifying) so only items arriving afterwards surface locally.
  Future<void> _prime() async {
    for (final item in await _fetchUnread()) {
      _seen.add(item['id'] as String);
    }
  }

  Future<void> _poll() async {
    for (final item in await _fetchUnread()) {
      final id = item['id'] as String;
      if (_seen.contains(id)) continue;
      _seen.add(id);
      await _showLocal(item);
    }
  }

  Future<List<Map<String, dynamic>>> _fetchUnread() async {
    try {
      final dio = createDio();
      final resp = await dio.get(
        '/notifications',
        queryParameters: <String, dynamic>{'unread_only': true, 'limit': 50},
      );
      return (resp.data['items'] as List).cast<Map<String, dynamic>>();
    } on DioException catch (e) {
      debugPrint('InboxPoller: ${e.message}');
      return const [];
    }
  }

  Future<void> _showLocal(Map<String, dynamic> item) async {
    const android = AndroidNotificationDetails(
      _channelId,
      _channelName,
      importance: Importance.high,
      priority: Priority.high,
    );
    const ios = DarwinNotificationDetails();
    await _plugin.show(
      item['id'].hashCode,
      item['title'] as String? ?? 'Rappel MediSense',
      item['body'] as String? ?? '',
      const NotificationDetails(android: android, iOS: ios),
      payload: item['appointment_uuid'] as String?,
    );
  }
}
