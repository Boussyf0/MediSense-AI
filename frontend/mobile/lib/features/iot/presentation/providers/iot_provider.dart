import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../../core/api/dio_client.dart';
import '../../../../services/alert_ws_provider.dart';
import '../../data/datasources/iot_remote_datasource.dart';
import '../../data/models/biometric_model.dart';

final iotDatasourceProvider =
    Provider((ref) => IotRemoteDatasource(createDio()));

final vitalsProvider = FutureProvider.autoDispose
    .family<List<BiometricPoint>, String>((ref, range) async {
  return ref.read(iotDatasourceProvider).getVitals(range: range);
});

final deviceProvider =
    FutureProvider.autoDispose<DeviceStatus?>((ref) async {
  return ref.read(iotDatasourceProvider).getDeviceStatus();
});

class AnomalySummary {
  final String summary;
  final double? hrvTrendPct;
  final double? meanHr7d;
  final double? meanSpo27d;
  final int sampleCount;

  const AnomalySummary({
    required this.summary,
    required this.sampleCount,
    this.hrvTrendPct,
    this.meanHr7d,
    this.meanSpo27d,
  });

  factory AnomalySummary.fromJson(Map<String, dynamic> j) => AnomalySummary(
        summary: j['summary'] as String? ?? '',
        hrvTrendPct: (j['hrv_trend_pct'] as num?)?.toDouble(),
        meanHr7d: (j['mean_hr_7d'] as num?)?.toDouble(),
        meanSpo27d: (j['mean_spo2_7d'] as num?)?.toDouble(),
        sampleCount: (j['sample_count'] as num?)?.toInt() ?? 0,
      );
}

final insightProvider =
    FutureProvider.autoDispose<AnomalySummary>((ref) async {
  final dio = createDio();
  try {
    final res = await dio.get('/anomalies/summary');
    return AnomalySummary.fromJson(res.data as Map<String, dynamic>);
  } on DioException {
    return const AnomalySummary(
      summary: 'Insight indisponible pour le moment.',
      sampleCount: 0,
    );
  }
});

/// Exposes the narrative from the latest live WebSocket alert so the
/// InsightCard can temporarily override the 7-day static text.
///
/// Returns null when there is no active toast (cleared after 8 s by
/// AlertsNotifier). No API call — pure reactive state composition.
final liveNarrativeProvider = Provider.autoDispose<String?>((ref) {
  final alertsState = ref.watch(alertsProvider);
  return alertsState.toast?.narrative;
});

