import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:medisense_ai/features/auth/data/datasources/auth_remote_datasource.dart';
import 'package:medisense_ai/features/auth/data/models/user_model.dart';
import 'package:medisense_ai/features/auth/presentation/providers/auth_provider.dart';

class MockAuthDS extends Mock implements AuthRemoteDatasource {}

const _testUser = UserModel(
  uuid: 'user-uuid-123',
  email: 'dr@clinic.ma',
  role: 'doctor',
  firstName: 'Ahmed',
  lastName: 'Merrouni',
);

void main() {
  late MockAuthDS mockDs;
  late AuthNotifier notifier;

  setUp(() {
    TestWidgetsFlutterBinding.ensureInitialized();

    // Mock FlutterSecureStorage method channel
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
      const MethodChannel('plugins.it_nomads.com/flutter_secure_storage'),
      (call) async => null,
    );

    mockDs = MockAuthDS();
    notifier = AuthNotifier(mockDs);
  });

  tearDown(() {
    notifier.dispose();
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
      const MethodChannel('plugins.it_nomads.com/flutter_secure_storage'),
      null,
    );
  });

  // NOTE: login() is NOT tested directly because it calls
  // FcmService.instance.registerWithBackend() and InboxPoller.instance.start()
  // as fire-and-forget. These are static final singletons that require
  // Firebase and FlutterLocalNotifications platform registration — unavailable
  // in unit tests. Instead we test loadUser() and logout() which don't
  // trigger platform plugins, and verify AuthState in isolation.

  group('AuthNotifier', () {
    test('loadUser sets user silently on success', () async {
      when(() => mockDs.me()).thenAnswer((_) async => _testUser);

      await notifier.loadUser();
      expect(notifier.state.user, isNotNull);
      expect(notifier.state.user!.uuid, 'user-uuid-123');
      expect(notifier.state.user!.email, 'dr@clinic.ma');
      expect(notifier.state.user!.role, 'doctor');
      expect(notifier.state.error, isNull);
    });

    test('loadUser swallows error silently', () async {
      when(() => mockDs.me()).thenThrow(Exception('session expired'));

      await notifier.loadUser();
      // loadUser is non-blocking — no error is set in state
      expect(notifier.state.user, isNull);
      expect(notifier.state.error, isNull);
    });

    test('logout clears state', () async {
      // Seed the notifier state as if logged in
      when(() => mockDs.me()).thenAnswer((_) async => _testUser);
      await notifier.loadUser();
      expect(notifier.state.user, isNotNull);

      when(() => mockDs.logout()).thenAnswer((_) async {});
      await notifier.logout();
      expect(notifier.state.user, isNull);
      expect(notifier.state.loading, isFalse);
      expect(notifier.state.error, isNull);
    });

    test('logout calls datasource logout', () async {
      when(() => mockDs.logout()).thenAnswer((_) async {});
      await notifier.logout();
      verify(() => mockDs.logout()).called(1);
    });
  });

  group('AuthState', () {
    test('copyWith preserves existing user when not overriding', () {
      const s = AuthState(user: _testUser, loading: false);
      final updated = s.copyWith(loading: true);
      expect(updated.user, isNotNull);
      expect(updated.user!.uuid, 'user-uuid-123');
      expect(updated.loading, isTrue);
    });
  });
}
