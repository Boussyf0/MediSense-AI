import 'package:flutter/material.dart';

import '../../theme/app_colors.dart';

/// Concentric expanding rings — mirrors the prototype `pulse-ring` keyframe.
/// Used for IoT pairing states and urgency banners.
class PulseRing extends StatefulWidget {
  final double size;
  final int rings;
  final Color color;
  final Duration period;

  const PulseRing({
    super.key,
    this.size = 56,
    this.rings = 3,
    this.color = AppColors.aiFrom,
    this.period = const Duration(milliseconds: 1500),
  });

  @override
  State<PulseRing> createState() => _PulseRingState();
}

class _PulseRingState extends State<PulseRing>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(vsync: this, duration: widget.period)
      ..repeat();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: widget.size,
      height: widget.size,
      child: AnimatedBuilder(
        animation: _ctrl,
        builder: (context, _) {
          return Stack(
            alignment: Alignment.center,
            children: List.generate(widget.rings, (i) {
              final offset = (i / widget.rings);
              var t = (_ctrl.value + offset) % 1.0;
              final scale = 0.4 + t * 0.6;
              final opacity = (1.0 - t).clamp(0.0, 1.0);
              return Opacity(
                opacity: opacity,
                child: Container(
                  width: widget.size * scale,
                  height: widget.size * scale,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(color: widget.color, width: 2),
                  ),
                ),
              );
            }),
          );
        },
      ),
    );
  }
}
