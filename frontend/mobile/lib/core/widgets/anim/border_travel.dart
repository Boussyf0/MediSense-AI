import 'package:flutter/material.dart';

import '../../theme/app_colors.dart';

/// Travelling gradient highlight along the left edge — mirrors the
/// prototype `border-travel` keyframe used on streaming AI cards.
class BorderTravel extends StatefulWidget {
  final Widget child;
  final bool active;
  final double radius;
  final EdgeInsetsGeometry padding;

  const BorderTravel({
    super.key,
    required this.child,
    this.active = true,
    this.radius = 12,
    this.padding = EdgeInsets.zero,
  });

  @override
  State<BorderTravel> createState() => _BorderTravelState();
}

class _BorderTravelState extends State<BorderTravel>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 3),
    );
    if (widget.active) _ctrl.repeat();
  }

  @override
  void didUpdateWidget(BorderTravel old) {
    super.didUpdateWidget(old);
    if (widget.active && !_ctrl.isAnimating) {
      _ctrl.repeat();
    } else if (!widget.active && _ctrl.isAnimating) {
      _ctrl.stop();
    }
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        Padding(padding: widget.padding, child: widget.child),
        if (widget.active)
          Positioned.fill(
            child: IgnorePointer(
              child: AnimatedBuilder(
                animation: _ctrl,
                builder: (context, _) {
                  return CustomPaint(
                    painter:
                        _BorderTravelPainter(_ctrl.value, widget.radius),
                  );
                },
              ),
            ),
          ),
      ],
    );
  }
}

class _BorderTravelPainter extends CustomPainter {
  final double t;
  final double radius;

  _BorderTravelPainter(this.t, this.radius);

  @override
  void paint(Canvas canvas, Size size) {
    final barHeight = size.height * 0.4;
    final travel = (t * (size.height + barHeight)) - barHeight;
    final rect = Rect.fromLTWH(0, travel, 3, barHeight);
    final paint = Paint()
      ..shader = AppColors.aiGrad.createShader(rect);
    canvas.drawRRect(
      RRect.fromRectAndRadius(rect, const Radius.circular(3)),
      paint,
    );
  }

  @override
  bool shouldRepaint(_BorderTravelPainter old) => old.t != t;
}
