import 'package:dio/dio.dart';
import '../models/biometric_model.dart';

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
        hrv: (m['hrv'] as num?)?.toDouble() ?? 0.0,
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
}
