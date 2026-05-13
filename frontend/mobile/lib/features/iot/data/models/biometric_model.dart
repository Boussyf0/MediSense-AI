import 'dart:math' as math;

class BiometricPoint {
  final DateTime timestamp;
  final double heartRate;
  final double spo2;
  final double hrv;
  const BiometricPoint({
    required this.timestamp,
    required this.heartRate,
    required this.spo2,
    required this.hrv,
  });
}

class BiometricMockData {
  static List<BiometricPoint> generate(int days) {
    final now = DateTime.now();
    return List.generate(days * 24, (i) {
      final ts = now.subtract(Duration(hours: days * 24 - i));
      final hourFactor = math.sin(ts.hour * math.pi / 12);
      return BiometricPoint(
        timestamp: ts,
        heartRate:
            (72 + hourFactor * 12 + (i % 7 - 3) * 2).clamp(50.0, 110.0),
        spo2: (97.5 + (i % 5 - 2) * 0.3).clamp(95.0, 100.0),
        hrv: (42 + hourFactor * 15 + (i % 9 - 4) * 3).clamp(20.0, 70.0),
      );
    });
  }
}
