import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../data/datasources/chat_remote_datasource.dart';
import '../../data/models/chat_models.dart';
import '../../../../core/api/dio_client.dart';

final chatDatasourceProvider =
    Provider((ref) => ChatRemoteDatasource(createDio()));

class ChatState {
  final List<ChatMessage> messages;
  final bool isStreaming;
  final bool isUrgent;
  final String? conversationId;
  final bool consentNlp;

  const ChatState({
    this.messages = const [],
    this.isStreaming = false,
    this.isUrgent = false,
    this.conversationId,
    this.consentNlp = true,
  });

  bool get isEmpty => messages.isEmpty;

  ChatState copyWith({
    List<ChatMessage>? messages,
    bool? isStreaming,
    bool? isUrgent,
    String? conversationId,
    bool? consentNlp,
  }) =>
      ChatState(
        messages: messages ?? this.messages,
        isStreaming: isStreaming ?? this.isStreaming,
        isUrgent: isUrgent ?? this.isUrgent,
        conversationId: conversationId ?? this.conversationId,
        consentNlp: consentNlp ?? this.consentNlp,
      );
}

class ChatNotifier extends StateNotifier<ChatState> {
  final ChatRemoteDatasource _ds;
  ChatNotifier(this._ds) : super(const ChatState());

  List<ChatMessage> get _msgs => state.messages;

  Future<void> sendMessage(String text) async {
    if (text.trim().isEmpty) return;

    final userMsg = ChatMessage(
      id: 'u${DateTime.now().millisecondsSinceEpoch}',
      role: MessageRole.user,
      content: text,
    );
    final streamingMsg = ChatMessage(
      id: 'a${DateTime.now().millisecondsSinceEpoch}',
      role: MessageRole.assistant,
      content: '',
      isStreaming: true,
    );
    state = state.copyWith(
        messages: [..._msgs, userMsg, streamingMsg], isStreaming: true);

    String accumulated = '';
    final String msgId = streamingMsg.id;

    try {
      await for (final event
          in _ds.streamMessage(text, state.conversationId)) {
        final type = event['type'] as String?;
        if (type == 'token') {
          accumulated += (event['value'] as String? ?? '');
          final updated = [..._msgs];
          final idx = updated.indexWhere((m) => m.id == msgId);
          if (idx >= 0) {
            updated[idx] = updated[idx].copyWith(content: accumulated);
          }
          state = state.copyWith(messages: updated);
        } else if (type == 'done') {
          final convId = event['conversation_id'] as String?;
          final sources = (event['sources'] as List?)
              ?.map((s) =>
                  ChatSource.fromJson(s as Map<String, dynamic>))
              .toList();
          final isUrgent = event['is_urgent'] == true;
          final updated = [..._msgs];
          final idx = updated.indexWhere((m) => m.id == msgId);
          if (idx >= 0) {
            updated[idx] = updated[idx].copyWith(
              content: accumulated,
              isStreaming: false,
              language: event['language'] as String?,
              confidence: (event['confidence'] as num?)?.toDouble(),
              sources: sources,
              isUrgent: isUrgent,
            );
          }
          state = state.copyWith(
            messages: updated,
            isStreaming: false,
            isUrgent: isUrgent || state.isUrgent,
            conversationId: convId ?? state.conversationId,
          );
          return;
        }
      }
    } catch (e) {
      final updated = [..._msgs];
      final idx = updated.indexWhere((m) => m.id == msgId);
      if (idx >= 0) {
        updated[idx] = updated[idx].copyWith(
          content: 'Erreur de connexion. Vérifiez votre réseau.',
          isStreaming: false,
        );
      }
      state = state.copyWith(messages: updated, isStreaming: false);
    }
  }

  void newConversation() => state = const ChatState();
}

final chatProvider = StateNotifierProvider<ChatNotifier, ChatState>(
  (ref) => ChatNotifier(ref.watch(chatDatasourceProvider)),
);
