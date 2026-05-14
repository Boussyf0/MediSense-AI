import 'package:flutter/material.dart';
import 'app_colors.dart';

class AppTheme {
  static ThemeData get dark => ThemeData(
        useMaterial3: true,
        brightness: Brightness.dark,
        scaffoldBackgroundColor: AppColors.surface0,
        colorScheme: const ColorScheme.dark(
          primary: AppColors.aiFrom,
          secondary: AppColors.aiTo,
          surface: AppColors.surface1,
        ),
        cardTheme: CardThemeData(
          color: AppColors.surface1,
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
            side: const BorderSide(color: AppColors.line),
          ),
        ),
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: AppColors.surface2,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: AppColors.line),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: AppColors.line),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: AppColors.aiFrom, width: 2),
          ),
        ),
        navigationBarTheme: NavigationBarThemeData(
          backgroundColor: AppColors.surface1,
          indicatorColor: AppColors.aiFrom.withValues(alpha: 0.15),
          labelTextStyle: WidgetStateProperty.all(
            const TextStyle(
                fontSize: 10, fontFamily: 'Inter', letterSpacing: 0.5),
          ),
        ),
        textTheme: const TextTheme(
          displayLarge: TextStyle(
              color: AppColors.textPrimary, fontWeight: FontWeight.w700),
          headlineMedium: TextStyle(
              color: AppColors.textPrimary, fontWeight: FontWeight.w600),
          bodyMedium: TextStyle(
              color: AppColors.textSecondary, fontFamily: 'Inter'),
          bodySmall:
              TextStyle(color: AppColors.textMuted, fontFamily: 'Inter'),
        ),
      );
}
