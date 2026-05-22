import 'dart:math';

import 'package:health/health.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../data/datasources/iot_remote_datasource.dart';

class HealthConnectPermissionDenied implements Exception {
  const HealthConnectPermissionDenied();
  @override
  String toString() =>
      'Permission Health Connect refusée. Activez HR/SpO₂/HRV pour MediSense.';
}

class HealthSyncSummary {
  final int accepted;
  final int dropped;
  final int rawPoints;
  final int hrPoints;
  final int spo2Points;
  final int hrvPoints;
  final int seedSpo2Points;
  final int seedHrvPoints;
  final bool hrPerm;
  final bool spo2Perm;
  final bool hrvPerm;
  final DateTime windowStart;
  final DateTime windowEnd;
  const HealthSyncSummary({
    required this.accepted,
    required this.dropped,
    required this.rawPoints,
    required this.hrPoints,
    required this.spo2Points,
    required this.hrvPoints,
    required this.seedSpo2Points,
    required this.seedHrvPoints,
    required this.hrPerm,
    required this.spo2Perm,
    required this.hrvPerm,
    required this.windowStart,
    required this.windowEnd,
  });
}

class HealthSyncService {
  HealthSyncService(this._remote);
  final IotRemoteDatasource _remote;

  static const _deviceIdKey = 'iot_device_id';
  static const _lastSyncKey = 'iot_last_sync_utc';

  static const _types = [
    HealthDataType.HEART_RATE,
    HealthDataType.BLOOD_OXYGEN,
    HealthDataType.HEART_RATE_VARIABILITY_RMSSD,
  ];

  Future<HealthSyncSummary> syncNow() async {
    await Health().configure();

    final perms = _types.map((_) => HealthDataAccess.READ).toList();
    final hasPerm =
        await Health().hasPermissions(_types, permissions: perms) ?? false;
    if (!hasPerm) {
      final ok = await Health()
          .requestAuthorization(_types, permissions: perms);
      if (!ok) throw const HealthConnectPermissionDenied();
    }

    // Per-type probe — Health Connect grants permissions individually, and
    // `hasPermissions` over the union can return true while one type was
    // silently denied. Surface each to the UI so the user can spot a missing
    // grant (notably HEART_RATE, which Mi Fitness writes but the user can
    // toggle off when accepting MediSense's read request).
    Future<bool> probe(HealthDataType t) async =>
        (await Health().hasPermissions(
              [t],
              permissions: [HealthDataAccess.READ],
            )) ??
            false;
    final hrPerm = await probe(HealthDataType.HEART_RATE);
    final spo2Perm = await probe(HealthDataType.BLOOD_OXYGEN);
    final hrvPerm =
        await probe(HealthDataType.HEART_RATE_VARIABILITY_RMSSD);

    final prefs = await SharedPreferences.getInstance();
    final now = DateTime.now().toUtc();
    final lastSyncIso = prefs.getString(_lastSyncKey);
    var since = lastSyncIso != null
        ? DateTime.parse(lastSyncIso)
        : now.subtract(const Duration(hours: 24));

    // Two queries: the active window (for HR — the dense signal) and a
    // 14-day lookback to seed SpO₂/HRV. Mi Band 7 Pro samples SpO₂ on
    // demand and HRV mostly during sleep, so they're rare in any 24h slice.
    var points = await Health().getHealthDataFromTypes(
      startTime: since,
      endTime: now,
      types: _types,
    );

    // Auto-widen: if the cursor window has no HR data, fall back to 24h then
    // 14d. The 14d step exists because Mi Fitness's HC bridge sometimes stops
    // exporting HR for days at a time — widening surfaces the most recent
    // sample regardless of when Mi Fitness last pushed.
    var hrCount = points
        .where((p) => p.type == HealthDataType.HEART_RATE)
        .length;
    for (final fallback in const [Duration(hours: 24), Duration(days: 14)]) {
      if (hrCount > 0) break;
      since = now.subtract(fallback);
      // HR-only retry with explicit recording-method filter (empty = no
      // filter), in case a combined multi-type query drops HR series records.
      final hrOnly = await Health().getHealthDataFromTypes(
        startTime: since,
        endTime: now,
        types: const [HealthDataType.HEART_RATE],
        recordingMethodsToFilter: const [],
      );
      points = await Health().getHealthDataFromTypes(
        startTime: since,
        endTime: now,
        types: _types,
      );
      final combinedHr =
          points.where((p) => p.type == HealthDataType.HEART_RATE).length;
      if (combinedHr == 0 && hrOnly.isNotEmpty) {
        points = [...points, ...hrOnly];
      }
      hrCount = points
          .where((p) => p.type == HealthDataType.HEART_RATE)
          .length;
    }

    // Seed lookback is only useful when the main window is shorter than 14d.
    // After the 14d auto-widen, `since == now - 14d` and the seed window
    // would collapse to zero width — HC throws on that.
    final seedStart = now.subtract(const Duration(days: 14));
    final seedPoints = seedStart.isBefore(since)
        ? await Health().getHealthDataFromTypes(
            startTime: seedStart,
            endTime: since,
            types: const [
              HealthDataType.BLOOD_OXYGEN,
              HealthDataType.HEART_RATE_VARIABILITY_RMSSD,
            ],
          )
        : const <HealthDataPoint>[];

    final samples = _bucketIntoSamples(points, seed: seedPoints);
    final deviceId = await _deviceId(prefs);

    final result = await _remote.ingest(deviceId: deviceId, samples: samples);

    // Only advance the cursor when we actually shipped something — otherwise
    // a transient "no Mi Band data yet" tap would shrink every subsequent
    // window to a few seconds.
    if (result.accepted > 0) {
      await prefs.setString(_lastSyncKey, now.toIso8601String());
    }

    final spo2Count = points
        .where((p) => p.type == HealthDataType.BLOOD_OXYGEN)
        .length;
    final hrvCount = points
        .where((p) => p.type == HealthDataType.HEART_RATE_VARIABILITY_RMSSD)
        .length;
    final seedSpo2Count = seedPoints
        .where((p) => p.type == HealthDataType.BLOOD_OXYGEN)
        .length;
    final seedHrvCount = seedPoints
        .where((p) => p.type == HealthDataType.HEART_RATE_VARIABILITY_RMSSD)
        .length;

    return HealthSyncSummary(
      accepted: result.accepted,
      dropped: result.dropped,
      rawPoints: points.length,
      hrPoints: hrCount,
      spo2Points: spo2Count,
      hrvPoints: hrvCount,
      seedSpo2Points: seedSpo2Count,
      seedHrvPoints: seedHrvCount,
      hrPerm: hrPerm,
      spo2Perm: spo2Perm,
      hrvPerm: hrvPerm,
      windowStart: since,
      windowEnd: now,
    );
  }

  Future<void> resetCursor() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_lastSyncKey);
  }

  Future<String> _deviceId(SharedPreferences prefs) async {
    final existing = prefs.getString(_deviceIdKey);
    if (existing != null && existing.isNotEmpty) return existing;
    final rand = Random.secure();
    final bytes = List<int>.generate(8, (_) => rand.nextInt(256));
    final hex =
        bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join().toUpperCase();
    final id = 'HC-$hex';
    await prefs.setString(_deviceIdKey, id);
    return id;
  }

  List<VitalSample> _bucketIntoSamples(
    List<HealthDataPoint> points, {
    List<HealthDataPoint> seed = const [],
  }) {
    // Seed lastSpo2 / lastHrv from the 14-day lookback so HR-only minutes
    // in the active window still produce complete samples.
    int? lastSpo2;
    int? lastHrv;
    for (final p in seed) {
      final v = p.value;
      if (v is! NumericHealthValue) continue;
      final raw = v.numericValue.toDouble();
      switch (p.type) {
        case HealthDataType.BLOOD_OXYGEN:
          lastSpo2 = (raw <= 1.0 ? raw * 100 : raw).round();
          break;
        case HealthDataType.HEART_RATE_VARIABILITY_RMSSD:
          lastHrv = raw.round();
          break;
        default:
          break;
      }
    }

    final byMinute = <DateTime, _Bucket>{};
    for (final p in points) {
      final ts = p.dateFrom.toUtc();
      final minute = DateTime.utc(
          ts.year, ts.month, ts.day, ts.hour, ts.minute);
      final v = p.value;
      if (v is! NumericHealthValue) continue;
      final num n = v.numericValue;
      final b = byMinute.putIfAbsent(minute, _Bucket.new);
      switch (p.type) {
        case HealthDataType.HEART_RATE:
          b.addHr(n.toDouble());
          break;
        case HealthDataType.BLOOD_OXYGEN:
          b.addSpo2(n.toDouble());
          break;
        case HealthDataType.HEART_RATE_VARIABILITY_RMSSD:
          b.addHrv(n.toDouble());
          break;
        default:
          break;
      }
    }

    final samples = <VitalSample>[];
    final sortedKeys = byMinute.keys.toList()..sort();
    for (final k in sortedKeys) {
      final b = byMinute[k]!;
      final hr = b.hr;
      final spo2Raw = b.spo2;
      final spo2 = spo2Raw == null
          ? null
          : (spo2Raw <= 1.0 ? spo2Raw * 100 : spo2Raw);
      final hrv = b.hrv;

      if (spo2 != null) lastSpo2 = spo2.round();
      if (hrv != null) lastHrv = hrv.round();

      if (hr == null) continue;
      if (lastSpo2 == null) continue;

      samples.add(VitalSample(
        ts: k,
        hr: hr.round(),
        spo2: lastSpo2,
        hrv: lastHrv,
      ));
    }
    return samples;
  }
}

class _Bucket {
  double _hrSum = 0;
  int _hrN = 0;
  double _spo2Sum = 0;
  int _spo2N = 0;
  double _hrvSum = 0;
  int _hrvN = 0;

  void addHr(double v) {
    _hrSum += v;
    _hrN += 1;
  }

  void addSpo2(double v) {
    _spo2Sum += v;
    _spo2N += 1;
  }

  void addHrv(double v) {
    _hrvSum += v;
    _hrvN += 1;
  }

  double? get hr => _hrN == 0 ? null : _hrSum / _hrN;
  double? get spo2 => _spo2N == 0 ? null : _spo2Sum / _spo2N;
  double? get hrv => _hrvN == 0 ? null : _hrvSum / _hrvN;
}
