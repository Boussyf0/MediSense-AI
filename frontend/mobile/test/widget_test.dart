import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:medisense_ai/main.dart';

void main() {
  testWidgets('app builds without errors', (WidgetTester tester) async {
    await tester.pumpWidget(const ProviderScope(child: MediSenseApp()));
    await tester.pump();
    expect(find.byType(MaterialApp), findsOneWidget);
  });
}
