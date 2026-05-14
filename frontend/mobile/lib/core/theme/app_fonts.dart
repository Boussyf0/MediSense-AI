import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Typography helpers — Space Grotesk (display), Inter (body),
/// JetBrains Mono (monospace numbers / labels).
///
/// Usage:
///   Text('Title', style: AppFonts.display(fontSize: 28, ...))
class AppFonts {
  static TextStyle display({
    double fontSize = 16,
    FontWeight fontWeight = FontWeight.w600,
    Color? color,
    double? letterSpacing,
    double? height,
    List<Shadow>? shadows,
    TextDecoration? decoration,
  }) =>
      GoogleFonts.spaceGrotesk(
        fontSize: fontSize,
        fontWeight: fontWeight,
        color: color,
        letterSpacing: letterSpacing,
        height: height,
        shadows: shadows,
        decoration: decoration,
      );

  static TextStyle body({
    double fontSize = 14,
    FontWeight fontWeight = FontWeight.w400,
    Color? color,
    double? letterSpacing,
    double? height,
    TextDecoration? decoration,
  }) =>
      GoogleFonts.inter(
        fontSize: fontSize,
        fontWeight: fontWeight,
        color: color,
        letterSpacing: letterSpacing,
        height: height,
        decoration: decoration,
      );

  static TextStyle mono({
    double fontSize = 11,
    FontWeight fontWeight = FontWeight.w500,
    Color? color,
    double letterSpacing = 0.4,
    double? height,
  }) =>
      GoogleFonts.jetBrainsMono(
        fontSize: fontSize,
        fontWeight: fontWeight,
        color: color,
        letterSpacing: letterSpacing,
        height: height,
      );
}
