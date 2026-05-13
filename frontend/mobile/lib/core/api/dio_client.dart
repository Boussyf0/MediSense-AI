import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../config/app_config.dart';

const _storage = FlutterSecureStorage();

Dio createDio() {
  final dio = Dio(BaseOptions(
    baseUrl: AppConfig.apiBaseUrl,
    connectTimeout: const Duration(seconds: 5),
    receiveTimeout: const Duration(seconds: 60),
  ));
  dio.interceptors.add(_AuthInterceptor());
  return dio;
}

class _AuthInterceptor extends Interceptor {
  final _refreshDio = Dio(BaseOptions(
    baseUrl: AppConfig.apiBaseUrl,
    connectTimeout: const Duration(seconds: 10),
  ));

  @override
  void onRequest(
      RequestOptions options, RequestInterceptorHandler handler) async {
    final token = await _storage.read(key: 'access_token');
    if (token != null) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    handler.next(options);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) async {
    if (err.response?.statusCode != 401) return handler.next(err);
    final refresh = await _storage.read(key: 'refresh_token');
    if (refresh == null) return handler.next(err);
    try {
      final res = await _refreshDio
          .post('/auth/refresh', data: {'refresh_token': refresh});
      final newToken = res.data['access_token'] as String;
      await _storage.write(key: 'access_token', value: newToken);
      err.requestOptions.headers['Authorization'] = 'Bearer $newToken';
      final retry = await _refreshDio.fetch(err.requestOptions);
      return handler.resolve(retry);
    } catch (_) {
      await _storage.deleteAll();
      handler.next(err);
    }
  }
}
