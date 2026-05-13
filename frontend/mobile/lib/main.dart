import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'core/router/app_router.dart';
import 'core/theme/app_theme.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await dotenv.load(fileName: '.env.development');
  await initializeDateFormatting('fr_FR', null);
  runApp(const ProviderScope(child: MediSenseApp()));
}

class MediSenseApp extends StatelessWidget {
  const MediSenseApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'MediSense AI',
      theme: AppTheme.dark,
      routerConfig: appRouter,
      debugShowCheckedModeBanner: false,
    );
  }
}
