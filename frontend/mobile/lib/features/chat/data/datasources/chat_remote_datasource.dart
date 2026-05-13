import 'dart:async';
import 'dart:convert';
import 'package:dio/dio.dart';

class ChatRemoteDatasource {
  final Dio _dio;
  ChatRemoteDatasource(this._dio);

  Stream<Map<String, dynamic>> streamMessage(
      String message, String? conversationId) async* {
    final response = await _dio.post(
      '/chat/stream',
      data: {
        'message': message,
        if (conversationId != null) 'conversation_id': conversationId,
      },
      options: Options(
        responseType: ResponseType.stream,
        // Disable receive timeout for long LLM streams (cold model can pause >60s).
        receiveTimeout: Duration.zero,
      ),
    );
    final byteStream = (response.data as ResponseBody).stream;
    // Cast Uint8List → List<int> so utf8.decoder accepts it, and handle
    // multi-byte codepoints that span chunk boundaries.
    final textStream = byteStream.cast<List<int>>().transform(utf8.decoder);
    var buffer = '';
    await for (final chunk in textStream) {
      buffer += chunk;
      final lines = buffer.split('\n');
      buffer = lines.last;
      for (final line in lines.take(lines.length - 1)) {
        if (line.startsWith('data:')) {
          final jsonStr = line.substring(5).trim();
          if (jsonStr.isEmpty) continue;
          if (jsonStr == '[DONE]') return;
          try {
            yield jsonDecode(jsonStr) as Map<String, dynamic>;
          } catch (_) {}
        }
      }
    }
  }

  Future<List<Map<String, dynamic>>> getConversations(
      {int limit = 20}) async {
    final res =
        await _dio.get('/chat', queryParameters: {'limit': limit});
    return List<Map<String, dynamic>>.from(res.data as List);
  }

  Future<void> deleteConversation(String id) async {
    await _dio.delete('/chat/$id');
  }
}
