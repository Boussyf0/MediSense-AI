import 'package:flutter_test/flutter_test.dart';
import 'package:medisense_ai/features/chat/data/models/chat_models.dart';
import 'package:medisense_ai/features/auth/data/models/user_model.dart';

void main() {
  group('ChatSource.fromJson', () {
    test('parses all fields', () {
      final s = ChatSource.fromJson({
        'title': 'ANSM Notice',
        'src': 'https://ansm.fr/doc/123',
        'date': '2026-01-15',
        'score': 0.92,
      });
      expect(s.title, 'ANSM Notice');
      expect(s.src, 'https://ansm.fr/doc/123');
      expect(s.date, '2026-01-15');
      expect(s.score, 0.92);
    });

    test('uses chunk_id and source as fallbacks', () {
      final s = ChatSource.fromJson({
        'chunk_id': 'chunk-42',
        'source': '/data/vidal.pdf',
      });
      expect(s.title, 'chunk-42');
      expect(s.src, '/data/vidal.pdf');
      expect(s.date, isNull);
      expect(s.score, isNull);
    });
  });

  group('ChatMessage', () {
    test('copyWith preserves id and role', () {
      const msg = ChatMessage(
        id: 'msg-1',
        role: MessageRole.assistant,
        content: 'Bonjour',
      );
      final updated = msg.copyWith(content: 'Salut');
      expect(updated.id, 'msg-1');
      expect(updated.role, MessageRole.assistant);
      expect(updated.content, 'Salut');
    });

    test('copyWith updates streaming state', () {
      const msg = ChatMessage(
        id: 'msg-2',
        role: MessageRole.assistant,
        content: '',
        isStreaming: true,
      );
      final done = msg.copyWith(isStreaming: false, content: 'Réponse complète');
      expect(done.isStreaming, isFalse);
      expect(done.content, 'Réponse complète');
    });
  });

  group('UserModel.fromJson', () {
    test('parses all fields including user_uuid alias', () {
      final u = UserModel.fromJson({
        'user_uuid': 'uuid-abc',
        'email': 'dr@clinic.ma',
        'role': 'doctor',
        'first_name': 'Ahmed',
        'last_name': 'Merrouni',
        'consent_iot': true,
        'consent_nlp': true,
        'consent_sharing': false,
      });
      expect(u.uuid, 'uuid-abc');
      expect(u.email, 'dr@clinic.ma');
      expect(u.role, 'doctor');
      expect(u.firstName, 'Ahmed');
      expect(u.lastName, 'Merrouni');
      expect(u.consentIot, isTrue);
      expect(u.consentNlp, isTrue);
      expect(u.consentSharing, isFalse);
    });
  });
}
