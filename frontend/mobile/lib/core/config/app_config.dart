import 'package:flutter_dotenv/flutter_dotenv.dart';

class AppConfig {
  static String get apiBaseUrl =>
      dotenv.env['API_BASE_URL'] ?? 'http://localhost:8000/api/v1';
  static bool get isDev => dotenv.env['ENV'] == 'development';
}
