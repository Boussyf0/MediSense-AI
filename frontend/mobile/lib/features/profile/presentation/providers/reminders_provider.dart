import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../../core/api/dio_client.dart';
import '../../data/datasources/reminders_remote_datasource.dart';

final remindersDatasourceProvider =
    Provider((ref) => RemindersRemoteDatasource(createDio()));

final remindersProvider =
    FutureProvider.autoDispose<List<ReminderDto>>((ref) async {
  return ref.read(remindersDatasourceProvider).list();
});

class RemindersActions {
  final Ref _ref;
  RemindersActions(this._ref);

  RemindersRemoteDatasource get _ds =>
      _ref.read(remindersDatasourceProvider);

  Future<void> create({
    required String name,
    required String dosage,
    required String time,
    required List<int> daysOfWeek,
  }) async {
    await _ds.create(
        name: name, dosage: dosage, time: time, daysOfWeek: daysOfWeek);
    _ref.invalidate(remindersProvider);
  }

  Future<void> toggleEnabled(String id, bool enabled) async {
    await _ds.patch(id, enabled: enabled);
    _ref.invalidate(remindersProvider);
  }

  Future<void> delete(String id) async {
    await _ds.delete(id);
    _ref.invalidate(remindersProvider);
  }
}

final remindersActionsProvider =
    Provider((ref) => RemindersActions(ref));
