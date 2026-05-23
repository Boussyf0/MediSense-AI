import 'package:dio/dio.dart';
import '../models/biometric_model.dart';

class VitalSample {
  final DateTime ts;
  final int? hr;
  final int? spo2;
  final int? hrv;
  const VitalSample({required this.ts, this.hr, this.spo2, this.hrv});

  Map<String, dynamic> toJson() => {
        'ts': ts.toUtc().toIso8601String(),
        if (hr != null) 'hr': hr,
        if (spo2 != null) 'spo2': spo2,
        if (hrv != null) 'hrv': hrv,
      };
}

class IngestResult {
  final int accepted;
  final int dropped;
  const IngestResult({required this.accepted, required this.dropped});
}

class DeviceStatus {
  final bool paired;
  final DateTime? lastSync;
  final int? battery;
  const DeviceStatus({required this.paired, this.lastSync, this.battery});

  factory DeviceStatus.fromJson(Map<String, dynamic> j) => DeviceStatus(
        paired: j['paired'] == true,
        lastSync: j['last_sync'] != null
            ? DateTime.tryParse(j['last_sync'] as String)
            : null,
        battery: (j['battery'] as num?)?.toInt(),
      );
}

class IotRemoteDatasource {
  final Dio _dio;
  IotRemoteDatasource(this._dio);

  Future<List<BiometricPoint>> getVitals({String range = '7d'}) async {
    final res = await _dio.get('/iot/vitals',
        queryParameters: {'range': range});
    final data = res.data as List;
    return data.map((p) {
      final m = p as Map<String, dynamic>;
      return BiometricPoint(
        timestamp:
            DateTime.tryParse(m['ts'] as String? ?? '') ?? DateTime.now(),
        heartRate: (m['hr'] as num?)?.toDouble() ?? 0.0,
        spo2: (m['spo2'] as num?)?.toDouble() ?? 0.0,
        hrv: (m['hrv'] as num?)?.toDouble(),
      );
    }).toList();
  }

  Future<DeviceStatus?> getDeviceStatus() async {
    try {
      final res = await _dio.get('/iot/devices');
      return DeviceStatus.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      if (e.response?.statusCode == 404) return null;
      rethrow;
    }
  }

  Future<DeviceStatus> simulate() async {
    final res = await _dio.post('/iot/simulate');
    return DeviceStatus.fromJson(res.data as Map<String, dynamic>);
  }

  Future<IngestResult> ingest({
    required String deviceId,
    required List<VitalSample> samples,
    int? battery,
  }) async {
    final res = await _dio.post('/iot/ingest', data: {
      'device_id': deviceId,
      if (battery != null) 'battery': battery,
      'samples': samples.map((s) => s.toJson()).toList(),
    });
    final m = res.data as Map<String, dynamic>;
    return IngestResult(
      accepted: (m['accepted'] as num?)?.toInt() ?? 0,
      dropped: (m['dropped'] as num?)?.toInt() ?? 0,
    );
  }
}
