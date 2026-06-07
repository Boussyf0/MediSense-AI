import 'package:flutter/foundation.dart' show kReleaseMode;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'core/router/app_router.dart';
import 'core/theme/app_theme.dart';
import 'services/fcm_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Release builds talk to the deployed backend; debug/profile use local dev.
  await dotenv.load(fileName: kReleaseMode ? '.env.production' : '.env.development');
  await initializeDateFormatting('fr_FR', null);
  // Best-effort: silently no-ops in dev if Firebase isn't configured.
  await FcmService.instance.init();
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
