import 'package:dio/dio.dart';

List<int> _normalizeDays(List<int> days) {
  final normalized = days.map((d) {
    final mod = d % 7;
    return mod < 0 ? mod + 7 : mod;
  }).toSet().toList()
    ..sort();
  return normalized;
}

class ReminderDto {
  final String id;
  final String name;
  final String dosage;
  final String time; // HH:MM
  final List<int> daysOfWeek;
  final bool enabled;

  const ReminderDto({
    required this.id,
    required this.name,
    required this.dosage,
    required this.time,
    required this.daysOfWeek,
    required this.enabled,
  });

  factory ReminderDto.fromJson(Map<String, dynamic> j) => ReminderDto(
        id: j['uuid']?.toString() ?? j['id']?.toString() ?? '',
        name: j['name'] as String? ?? '',
        dosage: j['dosage'] as String? ?? '',
        time: j['time'] as String? ?? '08:00',
        daysOfWeek: _normalizeDays(
          (j['days_of_week'] as List?)
                  ?.map((e) => (e as num).toInt())
                  .toList() ??
              const [0, 1, 2, 3, 4, 5, 6],
        ),
        enabled: j['enabled'] != false,
      );
}

class RemindersRemoteDatasource {
  final Dio _dio;
  RemindersRemoteDatasource(this._dio);

  Future<List<ReminderDto>> list() async {
    final res = await _dio.get('/reminders');
    return (res.data as List)
        .map((e) => ReminderDto.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<ReminderDto> create({
    required String name,
    required String dosage,
    required String time,
    required List<int> daysOfWeek,
  }) async {
    final normalizedDays = _normalizeDays(daysOfWeek);
    final res = await _dio.post('/reminders', data: {
      'name': name,
      'dosage': dosage,
      'time': time,
      'days_of_week': normalizedDays,
    });
    return ReminderDto.fromJson(res.data as Map<String, dynamic>);
  }

  Future<ReminderDto> patch(
    String id, {
    String? name,
    String? dosage,
    String? time,
    List<int>? daysOfWeek,
    bool? enabled,
  }) async {
    final body = <String, dynamic>{};
    if (name != null) body['name'] = name;
    if (dosage != null) body['dosage'] = dosage;
    if (time != null) body['time'] = time;
    if (daysOfWeek != null) {
      body['days_of_week'] = _normalizeDays(daysOfWeek);
    }
    if (enabled != null) body['enabled'] = enabled;
    final res = await _dio.patch('/reminders/$id', data: body);
    return ReminderDto.fromJson(res.data as Map<String, dynamic>);
  }

  Future<void> delete(String id) async {
    await _dio.delete('/reminders/$id');
  }
}
