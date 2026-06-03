import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../../data/datasources/auth_remote_datasource.dart';
import '../../data/models/user_model.dart';
import '../../../../core/api/dio_client.dart';
import '../../../../services/fcm_service.dart';
import '../../../../services/inbox_poller.dart';

const _storage = FlutterSecureStorage();
final _dioProvider = Provider((ref) => createDio());
final authDatasourceProvider =
    Provider((ref) => AuthRemoteDatasource(ref.watch(_dioProvider)));

class AuthState {
  final UserModel? user;
  final bool loading;
  final String? error;
  const AuthState({this.user, this.loading = false, this.error});
  AuthState copyWith({UserModel? user, bool? loading, String? error}) =>
      AuthState(
        user: user ?? this.user,
        loading: loading ?? this.loading,
        error: error,
      );
}

class AuthNotifier extends StateNotifier<AuthState> {
  final AuthRemoteDatasource _ds;
  AuthNotifier(this._ds) : super(const AuthState());

  Future<void> login(String email, String password) async {
    state = state.copyWith(loading: true, error: null);
    try {
      final user = await _ds.login(email, password);
      await _storage.write(key: 'onboarded', value: 'true');
      state = state.copyWith(user: user, loading: false);
      // Fire-and-forget — never block the login UX on a push-token round-trip.
      // ignore: unawaited_futures
      FcmService.instance.registerWithBackend();
      // ignore: unawaited_futures
      InboxPoller.instance.start();
    } catch (e) {
      state = state.copyWith(loading: false, error: e.toString());
      rethrow;
    }
  }

  Future<void> logout() async {
    // Revoke push token first so the backend stops pushing to a stale device.
    InboxPoller.instance.stop();
    await FcmService.instance.unregister();
    await _ds.logout();
    state = const AuthState();
  }

  Future<void> loadUser() async {
    try {
      final user = await _ds.me();
      state = state.copyWith(user: user);
    } catch (e) {
      // Non-blocking — session may have expired; login screen will handle it.
      debugPrint('loadUser failed: $e');
    }
  }
}

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>(
  (ref) => AuthNotifier(ref.watch(authDatasourceProvider)),
);
