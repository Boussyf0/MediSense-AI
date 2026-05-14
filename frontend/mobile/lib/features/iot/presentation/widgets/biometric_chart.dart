import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../../../../core/theme/app_colors.dart';
import '../../data/models/biometric_model.dart';

/// Vital sparkline — gradient stroke + soft area fill, hidden grid except
/// for 3 dashed horizontal rules. Mirrors `vitals.jsx > VitalsChart`.
class BiometricChart extends StatelessWidget {
  final List<BiometricPoint> points;
  final Color color;
  final double Function(BiometricPoint) valueSelector;
  const BiometricChart({
    super.key,
    required this.points,
    required this.color,
    required this.valueSelector,
  });

  @override
  Widget build(BuildContext context) {
    if (points.isEmpty) return const SizedBox.shrink();

    final spots = <FlSpot>[];
    for (var i = 0; i < points.length; i++) {
      spots.add(FlSpot(i.toDouble(), valueSelector(points[i])));
    }

    final ys = spots.map((s) => s.y);
    final minY = ys.reduce((a, b) => a < b ? a : b) - 2;
    final maxY = ys.reduce((a, b) => a > b ? a : b) + 2;

    return LineChart(
      LineChartData(
        gridData: FlGridData(
          show: true,
          drawVerticalLine: false,
          horizontalInterval: ((maxY - minY) / 4).clamp(1, 9999),
          getDrawingHorizontalLine: (_) => FlLine(
            color: AppColors.textMuted.withValues(alpha: 0.08),
            strokeWidth: 1,
            dashArray: const [3, 6],
          ),
        ),
        titlesData: const FlTitlesData(show: false),
        borderData: FlBorderData(show: false),
        minY: minY,
        maxY: maxY,
        lineTouchData: LineTouchData(
          touchTooltipData: LineTouchTooltipData(
            getTooltipColor: (_) => AppColors.surface2,
            getTooltipItems: (spots) => spots.map((s) {
              return LineTooltipItem(
                s.y.toStringAsFixed(1),
                TextStyle(
                  color: color,
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                ),
              );
            }).toList(),
          ),
        ),
        lineBarsData: [
          LineChartBarData(
            spots: spots,
            isCurved: true,
            curveSmoothness: 0.32,
            color: null,
            gradient: LinearGradient(
              colors: [
                color.withValues(alpha: 0.9),
                color.withValues(alpha: 0.5),
              ],
            ),
            barWidth: 2,
            isStrokeCapRound: true,
            dotData: const FlDotData(show: false),
            belowBarData: BarAreaData(
              show: true,
              gradient: LinearGradient(
                colors: [
                  color.withValues(alpha: 0.4),
                  color.withValues(alpha: 0.0),
                ],
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
