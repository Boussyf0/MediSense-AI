import 'package:flutter/material.dart';

/// Spring-in scale + fade entrance — mirrors the prototype `bubble-in`
/// keyframe used for chat bubbles and modal cards.
class BubbleIn extends StatefulWidget {
  final Widget child;
  final Duration duration;
  final Duration delay;

  const BubbleIn({
    super.key,
    required this.child,
    this.duration = const Duration(milliseconds: 350),
    this.delay = Duration.zero,
  });

  @override
  State<BubbleIn> createState() => _BubbleInState();
}

class _BubbleInState extends State<BubbleIn>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final Animation<double> _scale;
  late final Animation<double> _opacity;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(vsync: this, duration: widget.duration);
    _scale =
        CurvedAnimation(parent: _ctrl, curve: Curves.elasticOut).drive(
      Tween(begin: 0.85, end: 1.0),
    );
    _opacity = CurvedAnimation(parent: _ctrl, curve: Curves.easeOut);
    Future.delayed(widget.delay, () {
      if (mounted) _ctrl.forward();
    });
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: _opacity,
      child: ScaleTransition(scale: _scale, child: widget.child),
    );
  }
}
