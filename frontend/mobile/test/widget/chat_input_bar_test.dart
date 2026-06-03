import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:medisense_ai/features/chat/presentation/widgets/chat_input_bar.dart';

void main() {
  setUp(() {
    GoogleFonts.config.allowRuntimeFetching = false;

    // Mock SpeechToText platform channel
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
      const MethodChannel('plugin.csdcorp.com/speech_to_text'),
      (call) async {
        if (call.method == 'has_permission') return true;
        if (call.method == 'initialize') return true;
        return null;
      },
    );
  });

  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
      const MethodChannel('plugin.csdcorp.com/speech_to_text'),
      null,
    );
  });

  group('ChatInputBar', () {
    testWidgets('renders text field with hint', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ChatInputBar(onSend: (_) {}),
          ),
        ),
      );
      expect(find.text('Décrivez vos symptômes…'), findsOneWidget);
    });

    testWidgets('send does not fire when empty', (tester) async {
      var called = false;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ChatInputBar(onSend: (_) => called = true),
          ),
        ),
      );
      // Find and tap the send icon (arrow_upward)
      final sendIcons = find.byIcon(Icons.arrow_upward_rounded);
      expect(sendIcons, findsOneWidget);
      await tester.tap(sendIcons);
      await tester.pump();
      expect(called, isFalse);
    });

    testWidgets('send fires callback with text', (tester) async {
      String? sentText;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ChatInputBar(onSend: (t) => sentText = t),
          ),
        ),
      );
      // Enter text
      await tester.enterText(find.byType(TextField), 'mal de tête');
      await tester.pump();
      // Tap send
      await tester.tap(find.byIcon(Icons.arrow_upward_rounded));
      await tester.pump();
      expect(sentText, 'mal de tête');
    });

    testWidgets('TextField has maxLength 2000', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ChatInputBar(onSend: (_) {}),
          ),
        ),
      );
      final textField =
          tester.widget<TextField>(find.byType(TextField));
      expect(textField.maxLength, 2000);
    });
  });
}
