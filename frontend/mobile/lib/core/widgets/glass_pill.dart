import 'dart:ui';

import 'package:flutter/material.dart';

import '../theme/app_colors.dart';

/// iOS 26 "Liquid Glass" container — backdrop blur+saturate with inset
/// highlights. Mirrors the `.glass` utility in the prototype CSS.
class GlassPill extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  final double radius;
  final double blur;
  final Color tint;
  final BoxBorder? border;
  final List<BoxShadow>? shadow;

  const GlassPill({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
    this.radius = 99,
    this.blur = 18,
    this.tint = const Color(0x33111827),
    this.border,
    this.shadow,
  });

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(radius),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: blur, sigmaY: blur),
        child: Container(
          padding: padding,
          decoration: BoxDecoration(
            color: tint,
            borderRadius: BorderRadius.circular(radius),
            border: border ??
                Border.all(color: AppColors.lineStrong, width: 0.5),
            boxShadow: shadow ??
                const [
                  BoxShadow(
                    color: Color(0x33000000),
                    blurRadius: 20,
                    offset: Offset(0, 8),
                  ),
                ],
          ),
          child: child,
        ),
      ),
    );
  }
}
