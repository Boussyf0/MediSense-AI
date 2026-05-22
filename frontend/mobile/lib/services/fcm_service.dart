/// FCM push-notification service — Sprint 7 (US-29).
///
/// Initialises Firebase Messaging, requests permissions, retrieves the device
/// token, registers it with the backend, and routes incoming messages to a
/// handler that the app can extend (foreground toast, deep-link on tap).
///
/// Initialisation is best-effort: if Firebase isn't configured (no native
/// google-services.json / GoogleService-Info.plist) the service logs and
/// becomes a no-op so the rest of the app keeps working in dev/CI.
library;

import 'dart:async';
import 'dart:io' show Platform;

import 'package:dio/dio.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';

import '../core/api/dio_client.dart';

typedef FcmMessageHandler = void Function(RemoteMessage message);

class FcmService {
  FcmService._();
  static final FcmService instance = FcmService._();

  bool _initialised = false;
  String? _token;
  FcmMessageHandler? onForegroundMessage;
  FcmMessageHandler? onMessageOpenedApp;

  String get platform =>
      kIsWeb ? 'web' : (Platform.isIOS ? 'ios' : 'android');

  Future<void> init() async {
    if (_initialised) return;
    _initialised = true;
    try {
      await Firebase.initializeApp();
    } catch (e) {
      debugPrint('FCM init skipped — Firebase not configured: $e');
      return;
    }

    final messaging = FirebaseMessaging.instance;
    final settings = await messaging.requestPermission(
      alert: true,
      badge: true,
      sound: true,
    );
    if (settings.authorizationStatus == AuthorizationStatus.denied) {
      debugPrint('FCM permission denied by user');
      return;
    }

    _token = await messaging.getToken();
    debugPrint('FCM token: ${_token?.substring(0, 12)}…');

    messaging.onTokenRefresh.listen((newToken) async {
      _token = newToken;
      await _registerToken(newToken);
    });

    FirebaseMessaging.onMessage.listen((msg) {
      if (onForegroundMessage != null) onForegroundMessage!(msg);
    });
    FirebaseMessaging.onMessageOpenedApp.listen((msg) {
      if (onMessageOpenedApp != null) onMessageOpenedApp!(msg);
    });
  }

  /// Call after a successful login — sends the cached token to the backend.
  Future<void> registerWithBackend() async {
    if (_token == null) return;
    await _registerToken(_token!);
  }

  Future<void> _registerToken(String token) async {
    try {
      final dio = createDio();
      await dio.post(
        '/notifications/register-token',
        data: {'token': token, 'platform': platform},
      );
      debugPrint('FCM token registered with backend');
    } on DioException catch (e) {
      debugPrint('FCM registerToken failed: ${e.message}');
    }
  }

  /// Call on logout to revoke the token server-side.
  Future<void> unregister() async {
    if (_token == null) return;
    try {
      final dio = createDio();
      await dio.delete('/notifications/token/$_token');
    } on DioException catch (e) {
      debugPrint('FCM unregister failed: ${e.message}');
    }
  }
}
