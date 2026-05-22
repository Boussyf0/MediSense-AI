/// Real-time anomaly alert WebSocket — Sprint 7 (US-54 mobile).
///
/// Mirrors the web dashboard's `AlertsProvider.tsx` / `ws.ts` pattern:
/// connects to `ws://<host>/api/v1/ws/alerts/{role}?token=<jwt>`,
/// decodes incoming anomaly_critical JSON payloads, and exposes them
/// via a broadcast stream that the UI can listen to.
///
/// Reconnection: exponential back-off (1s → 30s cap), auto-recovers on
/// network flaps. Intentional `disconnect()` stops all retry attempts.
///
/// No extra pub dependency — uses `dart:io` `WebSocket` directly.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:developer' as developer;
import 'dart:io';
import 'dart:math' show min;

import '../core/config/app_config.dart';

/// Decoded anomaly alert payload from the backend WebSocket.
class AlertPayload {
  final String type;
  final String? patientUuid;
  final double? score5m;
  final double? score60m;
  final String? narrative;
  final double? hr;
  final double? spo2;
  final double? hrv;
  final double ts;
  final DateTime receivedAt;

  const AlertPayload({
    required this.type,
    this.patientUuid,
    this.score5m,
    this.score60m,
    this.narrative,
    this.hr,
    this.spo2,
    this.hrv,
    required this.ts,
    required this.receivedAt,
  });

  factory AlertPayload.fromJson(Map<String, dynamic> j) {
    final reading = j['reading'] as Map<String, dynamic>? ?? {};
    return AlertPayload(
      type: j['type'] as String? ?? 'anomaly_critical',
      patientUuid: j['patient_uuid'] as String?,
      score5m: (j['score_5m'] as num?)?.toDouble(),
      score60m: (j['score_60m'] as num?)?.toDouble(),
      narrative: j['narrative'] as String?,
      hr: (reading['hr'] as num?)?.toDouble(),
      spo2: (reading['spo2'] as num?)?.toDouble(),
      hrv: (reading['hrv'] as num?)?.toDouble(),
      ts: (j['ts'] as num?)?.toDouble() ?? 0,
      receivedAt: DateTime.now(),
    );
  }
}

/// Singleton WebSocket manager for anomaly alerts.
///
/// Usage:
///   AlertWsService.instance.connect(role: 'patient', token: jwt);
///   AlertWsService.instance.alerts.listen((payload) { ... });
///   AlertWsService.instance.disconnect();
class AlertWsService {
  AlertWsService._();
  static final AlertWsService instance = AlertWsService._();

  WebSocket? _ws;
  bool _intentionalClose = false;
  int _retryAttempt = 0;
  Timer? _reconnectTimer;
  String _role = '';
  String _token = '';

  static const _reconnectBaseMs = 1000;
  static const _reconnectMaxMs = 30000;

  final _controller = StreamController<AlertPayload>.broadcast();

  /// Broadcast stream of incoming anomaly alerts.
  Stream<AlertPayload> get alerts => _controller.stream;

  /// Whether the WebSocket is currently connected.
  bool get isConnected => _ws != null;

  /// Connect to the anomaly alerts WebSocket.
  ///
  /// [role] must be one of: 'doctor', 'secretary', 'admin', 'patient'.
  /// [token] is the JWT access token.
  void connect({required String role, required String token}) {
    _role = role;
    _token = token;
    _intentionalClose = false;
    _open();
  }

  /// Gracefully disconnect and stop all reconnect attempts.
  void disconnect() {
    _intentionalClose = true;
    _reconnectTimer?.cancel();
    _reconnectTimer = null;
    _ws?.close(WebSocketStatus.normalClosure);
    _ws = null;
    developer.log('WS: disconnected intentionally', name: 'medisense.ws');
  }

  void _open() async {
    if (_intentionalClose) return;

    // Derive WS URL from the HTTP API base URL:
    //   http://host:8000/api/v1 → ws://host:8000/api/v1/ws/alerts/{role}
    final httpBase = AppConfig.apiBaseUrl;
    final wsBase = httpBase
        .replaceFirst(RegExp(r'^http'), 'ws')
        .replaceFirst(RegExp(r'/api/v1/?$'), '');
    final url =
        '$wsBase/api/v1/ws/alerts/$_role?token=${Uri.encodeComponent(_token)}';

    developer.log('WS: connecting to $url', name: 'medisense.ws');

    try {
      _ws = await WebSocket.connect(url);
      _retryAttempt = 0;
      developer.log('WS: connected', name: 'medisense.ws');

      _ws!.listen(
        (dynamic data) {
          try {
            final json = jsonDecode(data as String) as Map<String, dynamic>;
            final payload = AlertPayload.fromJson(json);
            _controller.add(payload);
            developer.log(
              'WS: received alert type=${payload.type} '
              'narrative=${payload.narrative?.substring(0, min(40, payload.narrative?.length ?? 0))}',
              name: 'medisense.ws',
            );
          } catch (e) {
            developer.log('WS: decode error: $e', name: 'medisense.ws');
          }
        },
        onDone: () {
          developer.log('WS: connection closed', name: 'medisense.ws');
          _ws = null;
          if (!_intentionalClose) _scheduleReconnect();
        },
        onError: (Object error) {
          developer.log('WS: error: $error', name: 'medisense.ws');
          _ws = null;
          if (!_intentionalClose) _scheduleReconnect();
        },
        cancelOnError: true,
      );
    } catch (e) {
      developer.log('WS: connect failed: $e', name: 'medisense.ws');
      _ws = null;
      if (!_intentionalClose) _scheduleReconnect();
    }
  }

  void _scheduleReconnect() {
    if (_intentionalClose) return;
    final delayMs = min(
      _reconnectBaseMs * (1 << _retryAttempt),
      _reconnectMaxMs,
    );
    _retryAttempt++;
    developer.log(
      'WS: reconnecting in ${delayMs}ms (attempt $_retryAttempt)',
      name: 'medisense.ws',
    );
    _reconnectTimer = Timer(Duration(milliseconds: delayMs), _open);
  }

  /// Dispose resources. Call only on app termination.
  void dispose() {
    disconnect();
    _controller.close();
  }
}
