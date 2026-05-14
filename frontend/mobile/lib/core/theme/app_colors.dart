import 'package:flutter/material.dart';

/// Neural Dark design tokens — kept in lock-step with the prototype CSS
/// variables in `Medisense AI Prototype/MediSense AI.html`.
class AppColors {
  // Surfaces
  static const surface0 = Color(0xFF0A0D14);
  static const surface1 = Color(0xFF111827);
  static const surface2 = Color(0xFF1C2333);
  static const surface3 = Color(0xFF252D40);

  // Text
  static const textPrimary = Color(0xFFF8FAFC); // t0
  static const text1 = Color(0xFFE2E8F0); // t1
  static const textSecondary = Color(0xFFCBD5E1); // t2
  static const textMuted = Color(0xFF94A3B8); // t3
  static const textFaint = Color(0xFF64748B); // t4

  // Brand gradient
  static const aiFrom = Color(0xFF6366F1);
  static const aiTo = Color(0xFF8B5CF6);

  // Medical
  static const pulse = Color(0xFFF43F5E);
  static const oxy = Color(0xFF38BDF8);
  static const hrv = Color(0xFFA78BFA);

  // Risk
  static const riskSafe = Color(0xFF22C55E);
  static const riskWarn = Color(0xFFF97316);
  static const riskHigh = Color(0xFFEF4444);
  static const warnAmber = Color(0xFFF59E0B);

  // Lines
  static const line = Color(0x1A94A3B8);
  static const lineStrong = Color(0x2E94A3B8);

  static const aiGrad = LinearGradient(
    colors: [aiFrom, aiTo],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  /// Soft gradient used for selected chips / active buttons.
  static const aiGradSoft = LinearGradient(
    colors: [Color(0x33636FF1), Color(0x338B5CF6)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static Color riskColor(String? level) {
    switch (level) {
      case 'green':
      case 'safe':
        return riskSafe;
      case 'orange':
      case 'warn':
        return riskWarn;
      case 'red':
      case 'danger':
      case 'high':
        return riskHigh;
      default:
        return textFaint;
    }
  }
}
