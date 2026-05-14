import 'package:flutter/foundation.dart' show kDebugMode;
import 'package:flutter/material.dart';

import '../theme/app_colors.dart';

/// Mirrors the prototype's iOS frame chrome (Dynamic Island + status bar +
/// home indicator) used in the design showcase. Active by default only in
/// debug builds and on phones with notch-less viewports; otherwise falls
/// back to a transparent [SafeArea].
class IosFrame extends StatelessWidget {
  final Widget child;

  /// Force-enable / disable the decorative chrome (overrides auto-detect).
  final bool? showChrome;

  /// Time label shown in the status bar.
  final String time;

  const IosFrame({
    super.key,
    required this.child,
    this.showChrome,
    this.time = '9:41',
  });

  bool _shouldShow(BuildContext context) {
    if (showChrome != null) return showChrome!;
    final mq = MediaQuery.of(context);
    // Auto-show in debug builds where the OS hasn't already drawn the chrome.
    return kDebugMode && mq.padding.top < 30;
  }

  @override
  Widget build(BuildContext context) {
    if (!_shouldShow(context)) {
      return SafeArea(child: child);
    }

    return Stack(
      children: [
        Positioned.fill(child: child),

        // Status bar
        Positioned(
          top: 0,
          left: 0,
          right: 0,
          height: 44,
          child: IgnorePointer(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 28),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  Text(
                    time,
                    style: const TextStyle(
                      color: AppColors.textPrimary,
                      fontWeight: FontWeight.w600,
                      fontSize: 15,
                      fontFamily: 'SF Pro',
                    ),
                  ),
                  const Row(
                    children: [
                      Icon(Icons.signal_cellular_alt,
                          color: AppColors.textPrimary, size: 14),
                      SizedBox(width: 4),
                      Icon(Icons.wifi, color: AppColors.textPrimary, size: 14),
                      SizedBox(width: 4),
                      Icon(Icons.battery_full,
                          color: AppColors.textPrimary, size: 16),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),

        // Dynamic Island
        Positioned(
          top: 8,
          left: 0,
          right: 0,
          child: Center(
            child: Container(
              width: 120,
              height: 36,
              decoration: BoxDecoration(
                color: Colors.black,
                borderRadius: BorderRadius.circular(18),
                border: Border.all(color: const Color(0x33000000)),
              ),
            ),
          ),
        ),

        // Home indicator
        Positioned(
          bottom: 8,
          left: 0,
          right: 0,
          child: IgnorePointer(
            child: Center(
              child: Container(
                width: 134,
                height: 5,
                decoration: BoxDecoration(
                  color: AppColors.textPrimary.withValues(alpha: 0.85),
                  borderRadius: BorderRadius.circular(99),
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }
}
