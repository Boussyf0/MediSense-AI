/// Riverpod providers for real-time anomaly WebSocket alerts.
///
/// Wires the auth lifecycle (login/logout/token) to the WebSocket
/// connection and exposes an alert list + unread count for the UI.
library;

import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../features/auth/presentation/providers/auth_provider.dart';
import 'alert_ws_service.dart';

export 'alert_ws_service.dart' show AlertPayload;

const _storage = FlutterSecureStorage();

/// Latest N alerts received via WebSocket, newest first.
/// The provider auto-connects/disconnects with the auth lifecycle.
final alertsProvider =
    StateNotifierProvider<AlertsNotifier, AlertsState>((ref) {
  final notifier = AlertsNotifier();

  // React to auth state changes — connect on login, disconnect on logout.
  ref.listen<AuthState>(authProvider, (prev, next) async {
    final user = next.user;
    if (user != null) {
      final token = await _storage.read(key: 'access_token');
      if (token != null) {
        notifier.connect(role: user.role, token: token);
      }
    } else {
      notifier.disconnect();
    }
  });

  // If user is already logged in when provider is first read, connect now.
  () async {
    final user = ref.read(authProvider).user;
    if (user != null) {
      final token = await _storage.read(key: 'access_token');
      if (token != null) {
        notifier.connect(role: user.role, token: token);
      }
    }
  }();

  ref.onDispose(() => notifier.disconnect());

  return notifier;
});

class AlertsState {
  final List<AlertPayload> alerts;
  final int unread;
  /// The latest alert for toast display. Cleared by the UI after showing.
  final AlertPayload? toast;

  const AlertsState({
    this.alerts = const [],
    this.unread = 0,
    this.toast,
  });

  AlertsState copyWith({
    List<AlertPayload>? alerts,
    int? unread,
    AlertPayload? toast,
    bool clearToast = false,
  }) =>
      AlertsState(
        alerts: alerts ?? this.alerts,
        unread: unread ?? this.unread,
        toast: clearToast ? null : (toast ?? this.toast),
      );
}

class AlertsNotifier extends StateNotifier<AlertsState> {
  AlertsNotifier() : super(const AlertsState());

  StreamSubscription<AlertPayload>? _sub;
  Timer? _toastTimer;

  static const _maxAlerts = 50;
  static const _toastTtl = Duration(seconds: 8);

  void connect({required String role, required String token}) {
    // Cancel any previous subscription before reconnecting.
    _sub?.cancel();

    AlertWsService.instance.connect(role: role, token: token);

    _sub = AlertWsService.instance.alerts.listen((payload) {
      final updated = [payload, ...state.alerts].take(_maxAlerts).toList();
      state = state.copyWith(
        alerts: updated,
        unread: state.unread + 1,
        toast: payload,
      );

      // Auto-dismiss toast after TTL.
      _toastTimer?.cancel();
      _toastTimer = Timer(_toastTtl, () {
        if (mounted) {
          state = state.copyWith(clearToast: true);
        }
      });
    });
  }

  void disconnect() {
    _sub?.cancel();
    _sub = null;
    _toastTimer?.cancel();
    _toastTimer = null;
    AlertWsService.instance.disconnect();
  }

  void dismissToast() {
    state = state.copyWith(clearToast: true);
  }

  void markAllRead() {
    state = state.copyWith(unread: 0);
  }

  @override
  void dispose() {
    disconnect();
    super.dispose();
  }
}
