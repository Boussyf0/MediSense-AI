import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../../data/datasources/auth_remote_datasource.dart';
import '../../data/models/user_model.dart';
import '../../../../core/api/dio_client.dart';

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
    } catch (e) {
      state = state.copyWith(loading: false, error: e.toString());
      rethrow;
    }
  }

  Future<void> logout() async {
    await _ds.logout();
    state = const AuthState();
  }

  Future<void> loadUser() async {
    try {
      final user = await _ds.me();
      state = state.copyWith(user: user);
    } catch (_) {}
  }
}

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>(
  (ref) => AuthNotifier(ref.watch(authDatasourceProvider)),
);
