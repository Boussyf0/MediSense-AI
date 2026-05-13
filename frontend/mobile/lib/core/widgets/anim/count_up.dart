import 'package:flutter/material.dart';

/// Animates a numeric value with a cubic-ease curve on mount and on update.
/// Mirrors the prototype `<CountUp>` used for vital metric displays.
class CountUp extends StatefulWidget {
  final num value;
  final Duration duration;
  final int fractionDigits;
  final TextStyle? style;
  final String prefix;
  final String suffix;

  const CountUp({
    super.key,
    required this.value,
    this.duration = const Duration(milliseconds: 800),
    this.fractionDigits = 0,
    this.style,
    this.prefix = '',
    this.suffix = '',
  });

  @override
  State<CountUp> createState() => _CountUpState();
}

class _CountUpState extends State<CountUp>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  num _from = 0;
  late num _to;

  @override
  void initState() {
    super.initState();
    _to = widget.value;
    _ctrl = AnimationController(vsync: this, duration: widget.duration)
      ..addListener(() => setState(() {}))
      ..forward();
  }

  @override
  void didUpdateWidget(CountUp old) {
    super.didUpdateWidget(old);
    if (old.value != widget.value) {
      _from = _value;
      _to = widget.value;
      _ctrl
        ..reset()
        ..forward();
    }
  }

  num get _value {
    final t = Curves.easeOutCubic.transform(_ctrl.value);
    return _from + (_to - _from) * t;
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final display = widget.fractionDigits == 0
        ? _value.round().toString()
        : _value.toStringAsFixed(widget.fractionDigits);
    return Text('${widget.prefix}$display${widget.suffix}', style: widget.style);
  }
}
