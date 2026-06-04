import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:medisense_ai/features/chat/data/models/chat_models.dart';
import 'package:medisense_ai/features/chat/presentation/widgets/user_bubble.dart';
import 'package:medisense_ai/features/chat/presentation/widgets/ai_bubble.dart';

void main() {
  setUp(() {
    // Prevent GoogleFonts from fetching fonts over network in tests
    GoogleFonts.config.allowRuntimeFetching = false;
  });

  group('UserBubble', () {
    testWidgets('renders content text', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(body: UserBubble(content: 'Bonjour docteur')),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Bonjour docteur'), findsOneWidget);
    });

    testWidgets('has gradient decoration', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(body: UserBubble(content: 'test')),
        ),
      );
      await tester.pumpAndSettle();
      final decoratedBoxes = tester
          .widgetList<Container>(find.byType(Container))
          .where((c) =>
              c.decoration is BoxDecoration &&
              (c.decoration as BoxDecoration).gradient != null);
      expect(decoratedBoxes, isNotEmpty);
    });
  });

  group('AIBubble', () {
    // AIBubble uses AnimationController..repeat() for cursor blink, so
    // pumpAndSettle() would time out. We use pump(duration) then dispose
    // the widget before the test ends to clear pending tickers.

    testWidgets('renders message text', (tester) async {
      const msg = ChatMessage(
        id: 'ai-1',
        role: MessageRole.assistant,
        content: 'Je peux vous aider.',
        isStreaming: false,
      );
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(body: AIBubble(message: msg)),
        ),
      );
      await tester.pump(const Duration(milliseconds: 500));
      expect(find.text('Je peux vous aider.'), findsOneWidget);
      // Dispose widget to stop repeating animation controller
      await tester.pumpWidget(const SizedBox());
    });

    testWidgets('shows meta row with language when not streaming',
        (tester) async {
      const msg = ChatMessage(
        id: 'ai-2',
        role: MessageRole.assistant,
        content: 'Réponse complète.',
        isStreaming: false,
        language: 'fr',
        confidence: 0.92,
      );
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(body: AIBubble(message: msg)),
        ),
      );
      await tester.pump(const Duration(milliseconds: 500));
      expect(find.text('FR'), findsOneWidget);
      expect(find.text('92%'), findsOneWidget);
      // Dispose widget to stop repeating animation controller
      await tester.pumpWidget(const SizedBox());
    });
  });
}
