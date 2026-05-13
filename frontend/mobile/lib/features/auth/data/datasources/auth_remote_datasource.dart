import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../models/user_model.dart';

class AuthRemoteDatasource {
  final Dio _dio;
  final _storage = const FlutterSecureStorage();

  AuthRemoteDatasource(this._dio);

  Future<UserModel> login(String email, String password) async {
    final res = await _dio.post('/auth/login',
        data: {'email': email, 'password': password});
    await _storage.write(
        key: 'access_token', value: res.data['access_token'] as String);
    if (res.data['refresh_token'] != null) {
      await _storage.write(
          key: 'refresh_token',
          value: res.data['refresh_token'] as String);
    }
    return me();
  }

  Future<UserModel> me() async {
    final res = await _dio.get('/auth/me');
    return UserModel.fromJson(res.data as Map<String, dynamic>);
  }

  Future<void> logout() async {
    try {
      await _dio.post('/auth/logout');
    } catch (_) {}
    await _storage.deleteAll();
  }

  Future<void> updateConsent({
    required bool consentIot,
    required bool consentNlp,
    required bool consentSharing,
  }) async {
    await _dio.patch('/patients/me/consent', data: {
      'consent_iot': consentIot,
      'consent_nlp': consentNlp,
      'consent_sharing': consentSharing,
      'channel': 'app',
    });
  }
}
