import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../../core/api/dio_client.dart';
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
