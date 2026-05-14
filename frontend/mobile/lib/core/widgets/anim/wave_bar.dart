import 'dart:math';

import 'package:flutter/material.dart';

import '../../theme/app_colors.dart';

/// AI waveform — N vertical bars with a sine-driven amplitude scale.
/// Mirrors the prototype `<AIWaveform>` component used in onboarding and
/// chat headers.
class AIWaveform extends StatefulWidget {
  final int bars;
  final double width;
  final double height;
  final Duration period;

  const AIWaveform({
    super.key,
    this.bars = 5,
    this.width = 32,
    this.height = 24,
    this.period = const Duration(milliseconds: 1400),
  });

  @override
  State<AIWaveform> createState() => _AIWaveformState();
}

class _AIWaveformState extends State<AIWaveform>
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
      width: widget.width,
      height: widget.height,
      child: AnimatedBuilder(
        animation: _ctrl,
        builder: (context, _) {
          return Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            crossAxisAlignment: CrossAxisAlignment.center,
            children: List.generate(widget.bars, (i) {
              final phase = (_ctrl.value * 2 * pi) + (i * pi / widget.bars);
              final amp = 0.4 + 0.6 * (0.5 + 0.5 * sin(phase));
              return SizedBox(
                width: widget.width / (widget.bars * 1.8),
                height: widget.height,
                child: Align(
                  alignment: Alignment.center,
                  child: Container(
                    height: widget.height * amp,
                    decoration: BoxDecoration(
                      gradient: AppColors.aiGrad,
                      borderRadius: BorderRadius.circular(99),
                    ),
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
