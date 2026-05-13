import 'dart:math';
import 'package:flutter/material.dart';

class ParticleField extends StatefulWidget {
  final int count;
  const ParticleField({super.key, this.count = 20});

  @override
  State<ParticleField> createState() => _ParticleFieldState();
}

class _PData {
  final double x, y, r, dx, dy, dur, delay;
  _PData(Random rng)
      : x = rng.nextDouble(),
        y = rng.nextDouble(),
        r = 0.5 + rng.nextDouble() * 1.5,
        dx = -20 + rng.nextDouble() * 40,
        dy = -(80 + rng.nextDouble() * 60),
        dur = 8 + rng.nextDouble() * 10,
        delay = rng.nextDouble() * 8;
}

class _ParticleFieldState extends State<ParticleField>
    with SingleTickerProviderStateMixin {
  late final List<_PData> _ps;
  late final AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    final rng = Random();
    _ps = List.generate(widget.count, (_) => _PData(rng));
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 20),
    )..repeat();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: AnimatedBuilder(
        animation: _ctrl,
        builder: (context, _) => SizedBox.expand(
          child: CustomPaint(painter: _ParticlePainter(_ps, _ctrl.value)),
        ),
      ),
    );
  }
}

class _ParticlePainter extends CustomPainter {
  final List<_PData> ps;
  final double t; // 0-1 (repeating over 20s)

  _ParticlePainter(this.ps, this.t);

  @override
  void paint(Canvas canvas, Size size) {
    final nowSec = t * 20;
    final paint = Paint()
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 3);

    for (final p in ps) {
      var phase = (nowSec - p.delay) % p.dur;
      if (phase < 0) phase += p.dur;
      final frac = (phase / p.dur).clamp(0.0, 1.0);
      // ease-in
      final eased = frac * frac;

      final px = p.x * size.width + p.dx * eased;
      final py = p.y * size.height + p.dy * eased;

      final opacity = frac < 0.1
          ? frac / 0.1
          : frac > 0.8
              ? (1 - (frac - 0.8) / 0.2)
              : 1.0;

      paint.color = const Color(0xFFA78BFA).withValues(alpha: 0.55 * opacity);
      canvas.drawCircle(Offset(px, py), p.r, paint);
    }
  }

  @override
  bool shouldRepaint(_ParticlePainter old) => old.t != t;
}
