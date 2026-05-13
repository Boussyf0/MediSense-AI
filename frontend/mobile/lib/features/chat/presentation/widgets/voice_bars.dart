import 'package:flutter/material.dart';
import '../../../../core/theme/app_colors.dart';

/// 5 vertical waveform bars with sequenced wave-bar animation.
/// Mirrors `chat.jsx > VoiceBars`.
class VoiceBars extends StatefulWidget {
  final double height;
  final Color? barColor;
  const VoiceBars({super.key, this.height = 22, this.barColor});

  @override
  State<VoiceBars> createState() => _VoiceBarsState();
}

class _VoiceBarsState extends State<VoiceBars> with TickerProviderStateMixin {
  late List<AnimationController> _controllers;

  @override
  void initState() {
    super.initState();
    _controllers = List.generate(
      5,
      (i) => AnimationController(
        vsync: this,
        duration: Duration(milliseconds: 420 + i * 90),
      ),
    );
    for (var i = 0; i < _controllers.length; i++) {
      Future.delayed(Duration(milliseconds: i * 70), () {
        if (mounted) _controllers[i].repeat(reverse: true);
      });
    }
  }

  @override
  void dispose() {
    for (final c in _controllers) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: widget.height,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.center,
        children: List.generate(5, (i) {
          return Padding(
            padding: const EdgeInsets.symmetric(horizontal: 1.5),
            child: AnimatedBuilder(
              animation: _controllers[i],
              builder: (_, __) {
                final t = _controllers[i].value;
                return Container(
                  width: 3,
                  height: widget.height * (0.35 + 0.65 * t),
                  decoration: BoxDecoration(
                    gradient: AppColors.aiGrad,
                    borderRadius: BorderRadius.circular(2),
                  ),
                );
              },
            ),
          );
        }),
      ),
    );
  }
}
