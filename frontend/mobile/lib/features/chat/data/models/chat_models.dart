class ChatSource {
  final String title;
  final String src;
  final String? date;
  final double? score;
  const ChatSource({
    required this.title,
    required this.src,
    this.date,
    this.score,
  });
  factory ChatSource.fromJson(Map<String, dynamic> j) => ChatSource(
        title: j['title'] as String? ??
            j['chunk_id'] as String? ??
            'Source',
        src: j['src'] as String? ?? j['source'] as String? ?? '',
        date: j['date'] as String?,
        score: (j['score'] as num?)?.toDouble(),
      );
}

enum MessageRole { user, assistant }

class ChatMessage {
  final String id;
  final MessageRole role;
  final String content;
  final bool isStreaming;
  final String? language;
  final double? confidence;
  final List<ChatSource>? sources;
  final bool isUrgent;

  const ChatMessage({
    required this.id,
    required this.role,
    required this.content,
    this.isStreaming = false,
    this.language,
    this.confidence,
    this.sources,
    this.isUrgent = false,
  });

  ChatMessage copyWith({
    String? content,
    bool? isStreaming,
    String? language,
    double? confidence,
    List<ChatSource>? sources,
    bool? isUrgent,
  }) =>
      ChatMessage(
        id: id,
        role: role,
        content: content ?? this.content,
        isStreaming: isStreaming ?? this.isStreaming,
        language: language ?? this.language,
        confidence: confidence ?? this.confidence,
        sources: sources ?? this.sources,
        isUrgent: isUrgent ?? this.isUrgent,
      );
}
