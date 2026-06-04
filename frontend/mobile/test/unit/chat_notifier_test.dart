import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:medisense_ai/features/chat/data/datasources/chat_remote_datasource.dart';
import 'package:medisense_ai/features/chat/data/models/chat_models.dart';
import 'package:medisense_ai/features/chat/presentation/providers/chat_provider.dart';

class MockChatDS extends Mock implements ChatRemoteDatasource {}

void main() {
  late MockChatDS mockDs;
  late ChatNotifier notifier;

  setUp(() {
    mockDs = MockChatDS();
    notifier = ChatNotifier(mockDs);
  });

  tearDown(() {
    notifier.dispose();
  });

  group('ChatNotifier', () {
    test('sendMessage adds user and streaming messages', () async {
      when(() => mockDs.streamMessage(any(), any()))
          .thenAnswer((_) => Stream.fromIterable([
                {'type': 'done', 'conversation_id': 'conv-1'},
              ]));
      await notifier.sendMessage('Bonjour');
      expect(notifier.state.messages.length, 2);
      expect(notifier.state.messages[0].role, MessageRole.user);
      expect(notifier.state.messages[0].content, 'Bonjour');
      expect(notifier.state.messages[1].role, MessageRole.assistant);
    });

    test('sendMessage accumulates tokens', () async {
      when(() => mockDs.streamMessage(any(), any()))
          .thenAnswer((_) => Stream.fromIterable([
                {'type': 'token', 'value': 'Bon'},
                {'type': 'token', 'value': 'jour'},
                {
                  'type': 'done',
                  'conversation_id': 'conv-1',
                },
              ]));
      await notifier.sendMessage('hello');
      final assistant = notifier.state.messages[1];
      expect(assistant.content, 'Bonjour');
      expect(assistant.isStreaming, isFalse);
    });

    test('sendMessage handles done event with sources and conversationId',
        () async {
      when(() => mockDs.streamMessage(any(), any()))
          .thenAnswer((_) => Stream.fromIterable([
                {'type': 'token', 'value': 'Réponse'},
                {
                  'type': 'done',
                  'conversation_id': 'conv-42',
                  'language': 'fr',
                  'confidence': 0.95,
                  'is_urgent': false,
                  'sources': [
                    {'title': 'ANSM', 'src': 'https://ansm.fr'}
                  ],
                },
              ]));
      await notifier.sendMessage('test');
      final assistant = notifier.state.messages[1];
      expect(assistant.content, 'Réponse');
      expect(assistant.language, 'fr');
      expect(assistant.confidence, 0.95);
      expect(assistant.sources, isNotNull);
      expect(assistant.sources!.length, 1);
      expect(notifier.state.conversationId, 'conv-42');
      expect(notifier.state.isStreaming, isFalse);
    });

    test('sendMessage sets sources from done event', () async {
      when(() => mockDs.streamMessage(any(), any()))
          .thenAnswer((_) => Stream.fromIterable([
                {
                  'type': 'done',
                  'sources': [
                    {'title': 'Vidal', 'src': '/vidal.pdf', 'score': 0.88},
                    {'title': 'HAS', 'src': '/has.pdf', 'score': 0.75},
                  ],
                },
              ]));
      await notifier.sendMessage('médicament');
      final assistant = notifier.state.messages[1];
      expect(assistant.sources!.length, 2);
      expect(assistant.sources![0].title, 'Vidal');
    });

    test('sendMessage handles stream error gracefully', () async {
      when(() => mockDs.streamMessage(any(), any()))
          .thenAnswer((_) => Stream.error(Exception('Network error')));
      await notifier.sendMessage('test');
      final assistant = notifier.state.messages[1];
      expect(assistant.isStreaming, isFalse);
      expect(assistant.content, contains('Exception: Network error'));
      expect(notifier.state.isStreaming, isFalse);
    });

    test('newConversation resets state', () async {
      when(() => mockDs.streamMessage(any(), any()))
          .thenAnswer((_) => Stream.fromIterable([
                {'type': 'done', 'conversation_id': 'conv-1'},
              ]));
      await notifier.sendMessage('hello');
      expect(notifier.state.messages, isNotEmpty);
      notifier.newConversation();
      expect(notifier.state.isEmpty, isTrue);
      expect(notifier.state.conversationId, isNull);
      expect(notifier.state.isStreaming, isFalse);
    });
  });
}
