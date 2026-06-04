import 'package:flutter_test/flutter_test.dart';
import 'package:medisense_ai/features/auth/data/models/user_model.dart';

void main() {
  group('UserModel.fromJson', () {
    test('parses with user_uuid key', () {
      final u = UserModel.fromJson({
        'user_uuid': 'uuid-123',
        'email': 'patient@test.ma',
        'role': 'patient',
      });
      expect(u.uuid, 'uuid-123');
      expect(u.email, 'patient@test.ma');
      expect(u.role, 'patient');
    });

    test('falls back to uuid key when user_uuid is absent', () {
      final u = UserModel.fromJson({
        'uuid': 'uuid-456',
        'email': 'admin@test.ma',
        'role': 'admin',
        'first_name': 'Fatima',
        'last_name': 'Zahra',
      });
      expect(u.uuid, 'uuid-456');
      expect(u.firstName, 'Fatima');
      expect(u.lastName, 'Zahra');
    });
  });
}
