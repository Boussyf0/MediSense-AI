import 'dart:convert';
import 'package:dio/dio.dart';

class PatientRemoteDatasource {
  final Dio _dio;
  PatientRemoteDatasource(this._dio);

  Future<({String json, int bytes})> exportData(String uuid) async {
    final res = await _dio.get('/patients/$uuid/data/export');
    const encoder = JsonEncoder.withIndent('  ');
    final body = encoder.convert(res.data);
    return (json: body, bytes: utf8.encode(body).length);
  }

  Future<void> deleteAccount(String uuid) async {
    await _dio.delete('/patients/$uuid');
  }
}
