import 'dart:developer' as developer;

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_fonts.dart';
import '../../../../core/widgets/anim/pulse_ring.dart';
import '../../../../services/alert_ws_provider.dart';
import '../../data/datasources/iot_remote_datasource.dart';
import '../../data/models/biometric_model.dart';
import '../../domain/health_sync_service.dart';
import '../providers/iot_provider.dart';
import '../widgets/biometric_chart.dart';
import '../widgets/metric_card.dart';


class _Vital {
  final String key;
  final String label;
  final String name;
  final String unit;
  final IconData icon;
  final Color color;
  final num? Function(BiometricPoint) selector;
  const _Vital({
    required this.key,
    required this.label,
    required this.name,
    required this.unit,
    required this.icon,
    required this.color,
    required this.selector,
  });
}

/// Holds derived stats for a vital so the chart card doesn't fake values.
class _VitalStats {
  final double avg;
  final double pctDelta;
  final bool available;
  const _VitalStats({
    required this.avg,
    required this.pctDelta,
    this.available = true,
  });

  static _VitalStats from(
    List<BiometricPoint> points,
    num? Function(BiometricPoint) selector,
  ) {
    final values = <double>[];
    for (final p in points) {
      final v = selector(p);
      if (v != null) values.add(v.toDouble());
    }
    if (values.isEmpty) {
      return const _VitalStats(avg: 0, pctDelta: 0, available: false);
    }
    double total = 0;
    for (final v in values) {
      total += v;
    }
    final avg = total / values.length;
    if (values.length < 4) return _VitalStats(avg: avg, pctDelta: 0);
    final q = (values.length / 4).floor();
    double earlySum = 0;
    double lateSum = 0;
    for (var i = 0; i < q; i++) {
      earlySum += values[i];
    }
    for (var i = values.length - q; i < values.length; i++) {
      lateSum += values[i];
    }
    final early = earlySum / q;
    final late_ = lateSum / q;
    if (early == 0) return _VitalStats(avg: avg, pctDelta: 0);
    return _VitalStats(avg: avg, pctDelta: (late_ - early) / early * 100);
  }
}

/// Resting HR: lowest 5-min rolling average. Prefers samples taken between
/// 02h and 06h local (true resting window during sleep); falls back to the
/// minimum 5-min window across the full range when no nighttime data is
/// available — useful before the user has worn the band overnight.
int? _restingHr(List<BiometricPoint> points) {
  if (points.length < 3) return null;
  final buckets = <int, ({double sum, int n, int hour})>{};
  for (final p in points) {
    final local = p.timestamp.toLocal();
    final bucketKey = local.millisecondsSinceEpoch ~/ (5 * 60 * 1000);
    final prev = buckets[bucketKey];
    buckets[bucketKey] = (
      sum: (prev?.sum ?? 0) + p.heartRate,
      n: (prev?.n ?? 0) + 1,
      hour: local.hour,
    );
  }
  final averages = buckets.values
      .map((b) => (avg: b.sum / b.n, hour: b.hour))
      .toList();
  final nightly =
      averages.where((b) => b.hour >= 2 && b.hour < 6).toList();
  final pool = nightly.length >= 3 ? nightly : averages;
  if (pool.length < 3) return null;
  final minAvg = pool.map((b) => b.avg).reduce((a, b) => a < b ? a : b);
  return minAvg.round();
}

class IotDashboardPage extends ConsumerStatefulWidget {
  const IotDashboardPage({super.key});

  @override
  ConsumerState<IotDashboardPage> createState() => _IotDashboardPageState();
}

class _IotDashboardPageState extends ConsumerState<IotDashboardPage> {
  String _activeKey = 'hr';
  String _range = '24h';
  bool _syncing = false;

  Future<void> _showSyncDialog(String title, String body) async {
    if (!mounted) return;
    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.surface1,
        title: Text(title, style: AppFonts.body(color: AppColors.textPrimary)),
        content: Text(body, style: AppFonts.body(color: AppColors.textSecondary)),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  Future<void> _resetAndSync() async {
    await HealthSyncService(ref.read(iotDatasourceProvider)).resetCursor();
    await _showSyncDialog(
      'Curseur réinitialisé',
      'La prochaine sync relira les dernières 24h.',
    );
  }

  Future<void> _syncFromBand({bool resetFirst = false}) async {
    if (_syncing) return;
    setState(() => _syncing = true);
    developer.log('Sync: starting reset=$resetFirst', name: 'medisense.iot');
    try {
      final service = HealthSyncService(ref.read(iotDatasourceProvider));
      if (resetFirst) await service.resetCursor();
      final summary = await service.syncNow();
      developer.log(
        'Sync: ok raw=${summary.rawPoints} hr=${summary.hrPoints} '
        'spo2=${summary.spo2Points} hrv=${summary.hrvPoints} '
        'seedSpo2=${summary.seedSpo2Points} seedHrv=${summary.seedHrvPoints} '
        'perms hr=${summary.hrPerm} spo2=${summary.spo2Perm} hrv=${summary.hrvPerm} '
        'accepted=${summary.accepted} dropped=${summary.dropped} '
        'window=${summary.windowStart}→${summary.windowEnd}',
        name: 'medisense.iot',
      );
      ref.invalidate(deviceProvider);
      ref.invalidate(vitalsProvider(_apiRange));
      ref.invalidate(insightProvider);
      if (mounted) {
        final msg = summary.accepted > 0
            ? '${summary.accepted} nouvelles mesures'
            : 'À jour';
        ScaffoldMessenger.of(context)
          ..hideCurrentSnackBar()
          ..showSnackBar(
            SnackBar(
              behavior: SnackBarBehavior.floating,
              backgroundColor: AppColors.surface2,
              duration: const Duration(seconds: 2),
              margin: const EdgeInsets.fromLTRB(20, 0, 20, 96),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(14),
                side: BorderSide(
                  color: AppColors.aiFrom.withValues(alpha: 0.4),
                ),
              ),
              content: Row(
                children: [
                  const Icon(Icons.check_circle_rounded,
                      color: AppColors.riskSafe, size: 18),
                  const SizedBox(width: 10),
                  Text(
                    msg,
                    style: AppFonts.body(
                      color: AppColors.textPrimary,
                      fontSize: 13,
                    ),
                  ),
                ],
              ),
            ),
          );
      }
    } on HealthConnectPermissionDenied catch (e) {
      developer.log('Sync: permission denied', name: 'medisense.iot');
      await _showSyncDialog('Permission refusée', e.toString());
    } on DioException catch (e) {
      final code = e.response?.statusCode;
      final body = e.response?.data;
      final detail = body is Map && body['detail'] != null
          ? body['detail'].toString()
          : (e.message ?? 'connexion impossible');
      developer.log(
        'Sync: HTTP error code=$code detail=$detail',
        name: 'medisense.iot',
        error: e,
      );
      await _showSyncDialog('Sync échouée', 'HTTP ${code ?? "—"}: $detail');
    } catch (e, st) {
      developer.log('Sync: exception', name: 'medisense.iot', error: e, stackTrace: st);
      await _showSyncDialog('Sync échouée', e.toString());
    } finally {
      if (mounted) setState(() => _syncing = false);
    }
  }

  Future<void> _runSimulate() async {
    try {
      await ref.read(iotDatasourceProvider).simulate();
      ref.invalidate(deviceProvider);
      ref.invalidate(vitalsProvider(_apiRange));
      ref.invalidate(insightProvider);
    } on DioException catch (e) {
      if (!mounted) return;
      final code = e.response?.statusCode;
      final body = e.response?.data;
      final detail = body is Map && body['detail'] != null
          ? body['detail'].toString()
          : (e.message ?? 'connexion impossible');
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Simulation ${code ?? "—"}: $detail')),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Erreur de simulation: $e')),
      );
    }
  }

  String get _apiRange {
    switch (_range) {
      case '1h':
        return '1h';
      case '7j':
        return '7d';
      default:
        return '24h';
    }
  }

  List<BiometricPoint> _sample(List<BiometricPoint> data) {
    if (data.length <= 168) return data;
    final step = (data.length / 168).ceil();
    return [for (int i = 0; i < data.length; i += step) data[i]];
  }


  Future<void> _refresh() async {
    ref.invalidate(deviceProvider);
    ref.invalidate(vitalsProvider(_apiRange));
    ref.invalidate(insightProvider);
    await Future.wait([
      ref.read(deviceProvider.future),
      ref.read(vitalsProvider(_apiRange).future),
    ]);
  }

  List<_Vital> get _vitals => [
        _Vital(
          key: 'hr',
          label: 'BPM',
          name: 'Fréquence cardiaque',
          unit: '',
          icon: Icons.favorite_rounded,
          color: AppColors.pulse,
          selector: (p) => p.heartRate,
        ),
        _Vital(
          key: 'spo2',
          label: 'SpO₂',
          name: 'Saturation O₂',
          unit: '%',
          icon: Icons.air_rounded,
          color: AppColors.oxy,
          selector: (p) => p.spo2,
        ),
        _Vital(
          key: 'hrv',
          label: 'HRV',
          name: 'Variabilité',
          unit: 'ms',
          icon: Icons.graphic_eq_rounded,
          color: AppColors.hrv,
          selector: (p) => p.hrv,
        ),
      ];

  /// Patient-friendly summary for the metric tile. Tone matches the rest of
  /// the dashboard (short, no jargon) and avoids alarming labels — the
  /// anomaly card handles real alerts.
  String _trendLabel(String key, _VitalStats stats) {
    final delta = stats.pctDelta;
    final dirNote = delta.abs() < 2
        ? 'stable'
        : (delta > 0 ? 'en hausse' : 'en baisse');
    switch (key) {
      case 'spo2':
        if (stats.avg >= 96) return 'Excellent · $dirNote';
        if (stats.avg >= 92) return 'Correct · $dirNote';
        return 'Bas · $dirNote';
      case 'hrv':
        if (stats.avg >= 50) return 'Élevé · $dirNote';
        if (stats.avg >= 30) return 'Normal · $dirNote';
        return 'Bas · $dirNote';
      default:
        if (stats.avg < 60) return 'Bradycardie · $dirNote';
        if (stats.avg > 100) return 'Tachycardie · $dirNote';
        return 'Normal · $dirNote';
    }
  }

  String _trendDir(double delta) {
    if (delta.abs() < 2) return '→';
    return delta > 0 ? '↗' : '↘';
  }

  @override
  Widget build(BuildContext context) {
    final deviceAsync = ref.watch(deviceProvider);
    final vitalsAsync = ref.watch(vitalsProvider(_apiRange));

    return Scaffold(
      backgroundColor: AppColors.surface0,
      floatingActionButton: Padding(
        padding: const EdgeInsets.only(bottom: 96, right: 4),
        child: GestureDetector(
          onLongPress: _syncing ? null : _resetAndSync,
          child: FloatingActionButton.extended(
          heroTag: 'sync-band-fab',
          onPressed: _syncing ? null : _syncFromBand,
          backgroundColor: AppColors.aiFrom,
          foregroundColor: Colors.white,
          icon: _syncing
              ? const SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    valueColor: AlwaysStoppedAnimation(Colors.white),
                  ),
                )
              : const Icon(Icons.watch_outlined),
          label: Text(
            _syncing ? 'Sync...' : 'Sync bracelet',
            style: AppFonts.body(
              color: Colors.white,
              fontSize: 13.5,
              fontWeight: FontWeight.w600,
            ),
          ),
          ),
        ),
      ),
      body: SafeArea(
        child: deviceAsync.when(
          loading: () => const _SyncingState(),
          error: (_, __) => _NoDeviceState(
            onConnect: _refresh,
            onSimulate: _runSimulate,
          ),
          data: (device) {
            if (device == null || !device.paired) {
              return _NoDeviceState(
                onConnect: _refresh,
                onSimulate: _runSimulate,
              );
            }
            return vitalsAsync.when(
              loading: () => const _SyncingState(),
              error: (e, _) => Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.cloud_off_outlined,
                        color: AppColors.textMuted, size: 36),
                    const SizedBox(height: 12),
                    Text(
                      'Erreur de chargement',
                      style: AppFonts.body(
                          color: AppColors.textSecondary, fontSize: 13),
                    ),
                    const SizedBox(height: 16),
                    ElevatedButton(
                      onPressed: () =>
                          ref.invalidate(vitalsProvider(_apiRange)),
                      style: ElevatedButton.styleFrom(
                          backgroundColor: AppColors.surface2),
                      child: const Text('Réessayer',
                          style:
                              TextStyle(color: AppColors.textPrimary)),
                    ),
                  ],
                ),
              ),
              data: (data) {
                if (data.isEmpty) {
                  if (_range == '1h') {
                    return Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.query_stats_rounded,
                              color: AppColors.textMuted, size: 36),
                          const SizedBox(height: 12),
                          Text(
                            'Pas de données sur la dernière heure',
                            style: AppFonts.body(
                                color: AppColors.textSecondary, fontSize: 13),
                          ),
                          const SizedBox(height: 6),
                          Text(
                            'Essayez une plage plus large.',
                            style: AppFonts.body(
                                color: AppColors.textMuted, fontSize: 12),
                          ),
                          const SizedBox(height: 16),
                          ElevatedButton(
                            onPressed: () => setState(() => _range = '24h'),
                            style: ElevatedButton.styleFrom(
                                backgroundColor: AppColors.surface2),
                            child: const Text('Voir 24h',
                                style: TextStyle(
                                    color: AppColors.textPrimary)),
                          ),
                        ],
                      ),
                    );
                  }
                  return Center(
                    child: Text(
                      'Aucune donnée biométrique',
                      style: AppFonts.body(
                          color: AppColors.textMuted, fontSize: 13),
                    ),
                  );
                }
                final sampled = _sample(data);
                final hasHrv = sampled.any((p) => p.hrv != null);
                final vitals = hasHrv
                    ? _vitals
                    : _vitals.where((v) => v.key != 'hrv').toList();
                final activeKey =
                    vitals.any((v) => v.key == _activeKey) ? _activeKey : 'hr';
                final stats = <String, _VitalStats>{
                  for (final v in vitals)
                    v.key: _VitalStats.from(sampled, v.selector),
                };
                // Pick up any live narrative from the WS alert toast.
                final liveNarrative =
                    ref.watch(alertsProvider).toast?.narrative;
                return _DataDashboard(
                  vitals: vitals,
                  activeKey: activeKey,
                  onActive: (k) => setState(() => _activeKey = k),
                  range: _range,
                  onRange: (r) => setState(() => _range = r),
                  latest: data.last,
                  sampled: sampled,
                  device: device,
                  stats: stats,
                  trendLabel: _trendLabel,
                  trendDir: _trendDir,
                  onRefresh: _refresh,
                  anomalyNarrative: liveNarrative,
                );
              },
            );
          },
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Data dashboard
// ─────────────────────────────────────────────────────────────────────────────

class _DataDashboard extends StatelessWidget {
  final List<_Vital> vitals;
  final String activeKey;
  final void Function(String) onActive;
  final String range;
  final void Function(String) onRange;
  final BiometricPoint latest;
  final List<BiometricPoint> sampled;
  final DeviceStatus device;
  final Map<String, _VitalStats> stats;
  final String Function(String, _VitalStats) trendLabel;
  final String Function(double) trendDir;
  final Future<void> Function() onRefresh;
  final String? anomalyNarrative;

  const _DataDashboard({
    required this.vitals,
    required this.activeKey,
    required this.onActive,
    required this.range,
    required this.onRange,
    required this.latest,
    required this.sampled,
    required this.device,
    required this.stats,
    required this.trendLabel,
    required this.trendDir,
    required this.onRefresh,
    this.anomalyNarrative,
  });

  num? _liveValue(_Vital v) {
    switch (v.key) {
      case 'spo2':
        return latest.spo2.round();
      case 'hrv':
        return latest.hrv?.round();
      default:
        return latest.heartRate.round();
    }
  }

  String get _syncLabel {
    if (device.lastSync == null) return 'IOT · JAMAIS SYNCHRONISÉ';
    final diff = DateTime.now().difference(device.lastSync!);
    final ago = diff.inSeconds < 60
        ? '${diff.inSeconds}S'
        : diff.inMinutes < 60
            ? '${diff.inMinutes}MIN'
            : '${diff.inHours}H';
    return 'IOT · SYNC IL Y A $ago';
  }

  @override
  Widget build(BuildContext context) {
    final cur = vitals.firstWhere((v) => v.key == activeKey);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 8),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      _syncLabel,
                      style: AppFonts.mono(
                        color: AppColors.textMuted,
                        fontSize: 10,
                        letterSpacing: 1.4,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Signes vitaux',
                      style: AppFonts.display(
                        color: AppColors.textPrimary,
                        fontSize: 28,
                        fontWeight: FontWeight.w600,
                        letterSpacing: -0.56,
                      ),
                    ),
                  ],
                ),
              ),
              GestureDetector(
                onTap: onRefresh,
                behavior: HitTestBehavior.opaque,
                child: Container(
                  width: 38,
                  height: 38,
                  decoration: BoxDecoration(
                    color: AppColors.surface1,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppColors.line),
                  ),
                  child: const Icon(
                    Icons.refresh_rounded,
                    size: 18,
                    color: AppColors.text1,
                  ),
                ),
              ),
            ],
          ),
        ),
        Expanded(
          child: RefreshIndicator(
            onRefresh: onRefresh,
            color: AppColors.aiFrom,
            child: ListView(
              padding: EdgeInsets.zero,
              physics: const AlwaysScrollableScrollPhysics(),
              children: [
                // Hero pulse — breathes at the live BPM rate
                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 8, 20, 4),
                  child: _PulseHero(
                    bpm: latest.heartRate.round(),
                    spo2: latest.spo2.round(),
                    hrv: latest.hrv?.round(),
                    restingHr: _restingHr(sampled),
                    anomalyNarrative: anomalyNarrative,
                  ),
                ),
                // Horizontal metric cards
                SizedBox(
                  height: 200,
                  child: ListView.separated(
                    scrollDirection: Axis.horizontal,
                    padding: const EdgeInsets.fromLTRB(20, 14, 20, 14),
                    itemCount: vitals.length,
                    separatorBuilder: (_, __) => const SizedBox(width: 12),
                    itemBuilder: (_, i) {
                      final v = vitals[i];
                      final s = stats[v.key] ??
                          const _VitalStats(avg: 0, pctDelta: 0);
                      return MetricCard(
                        icon: v.icon,
                        label: v.label,
                        name: v.name,
                        value: _liveValue(v),
                        unit: v.unit,
                        color: v.color,
                        trend: trendLabel(v.key, s),
                        trendDir: trendDir(s.pctDelta),
                        active: v.key == activeKey,
                        onTap: () => onActive(v.key),
                      );
                    },
                  ),
                ),
                // Chart card
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 20),
                  child: _ChartCard(
                    vital: cur,
                    range: range,
                    onRange: onRange,
                    latest: latest,
                    sampled: sampled,
                    stats: stats[cur.key] ??
                        const _VitalStats(avg: 0, pctDelta: 0),
                  ),
                ),
                const SizedBox(height: 14),
                // AI insight
                const Padding(
                  padding: EdgeInsets.symmetric(horizontal: 20),
                  child: _InsightCard(),
                ),
                const SizedBox(height: 14),
                // Device status
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 20),
                  child: _DeviceStatusCard(device: device),
                ),
                const SizedBox(height: 110),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Chart card with range selector
// ─────────────────────────────────────────────────────────────────────────────

class _ChartCard extends StatelessWidget {
  final _Vital vital;
  final String range;
  final void Function(String) onRange;
  final BiometricPoint latest;
  final List<BiometricPoint> sampled;
  final _VitalStats stats;

  const _ChartCard({
    required this.vital,
    required this.range,
    required this.onRange,
    required this.latest,
    required this.sampled,
    required this.stats,
  });

  @override
  Widget build(BuildContext context) {
    final v = vital.selector(latest);
    final avg = stats.avg.round();
    final headline = v == null ? '—' : '${v.toStringAsFixed(0)}${vital.unit}';
    final avgLabel = stats.available
        ? 'moy. $avg${vital.unit}'
        : 'indisponible';
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface1,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.line),
      ),
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      vital.name.toUpperCase(),
                      style: AppFonts.mono(
                        color: AppColors.textMuted,
                        fontSize: 10,
                        letterSpacing: 1.2,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.baseline,
                      textBaseline: TextBaseline.alphabetic,
                      children: [
                        Text(
                          headline,
                          style: AppFonts.display(
                            color: vital.color,
                            fontSize: 22,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        const SizedBox(width: 6),
                        Text(
                          avgLabel,
                          style: AppFonts.body(
                            color: AppColors.textSecondary,
                            fontSize: 11,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              Row(
                children: [
                  for (final r in const ['1h', '24h', '7j']) ...[
                    _RangeBtn(
                        label: r, active: range == r, onTap: () => onRange(r)),
                    if (r != '7j') const SizedBox(width: 4),
                  ],
                ],
              ),
            ],
          ),
          const SizedBox(height: 14),
          SizedBox(
            height: 140,
            child: BiometricChart(
              points: sampled,
              color: vital.color,
              valueSelector: (p) => vital.selector(p)?.toDouble(),
            ),
          ),
          const SizedBox(height: 6),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                for (final t in const [
                  '00:00',
                  '06:00',
                  '12:00',
                  '18:00',
                  'maint.'
                ])
                  Text(
                    t,
                    style: AppFonts.mono(
                      color: AppColors.textFaint,
                      fontSize: 9,
                      letterSpacing: 0.4,
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _RangeBtn extends StatelessWidget {
  final String label;
  final bool active;
  final VoidCallback onTap;
  const _RangeBtn(
      {required this.label, required this.active, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 6),
        decoration: BoxDecoration(
          gradient: active ? AppColors.aiGrad : null,
          color: active ? null : const Color(0x991C2333),
          borderRadius: BorderRadius.circular(99),
          border: active ? null : Border.all(color: AppColors.line),
        ),
        child: Text(
          label,
          style: AppFonts.mono(
            color: active ? Colors.white : AppColors.text1,
            fontSize: 10,
            fontWeight: FontWeight.w600,
            letterSpacing: 0.4,
          ),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Insight + device status
// ─────────────────────────────────────────────────────────────────────────────

class _InsightCard extends ConsumerWidget {
  const _InsightCard();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final insightAsync = ref.watch(insightProvider);
    final liveNarrative = ref.watch(liveNarrativeProvider);

    final isLive = liveNarrative != null;
    final text = isLive
        ? liveNarrative
        : insightAsync.maybeWhen(
            data: (s) => s.summary,
            orElse: () => 'Analyse en cours…',
          );

    // Colour shifts from AI-violet to danger-red when a live alert is active.
    final cardColor = isLive
        ? const Color(0xEF1F1035)
        : AppColors.surface1;
    final borderColor = isLive
        ? AppColors.pulse.withValues(alpha: 0.45)
        : AppColors.line;
    final iconBg = isLive
        ? AppColors.pulse.withValues(alpha: 0.15)
        : AppColors.hrv.withValues(alpha: 0.15);
    final iconColor = isLive
        ? AppColors.pulse
        : const Color(0xFFA78BFA);
    final iconData = isLive ? Icons.warning_amber_rounded : Icons.auto_awesome;
    final labelText = isLive ? 'EN DIRECT · ALERTE' : 'INSIGHT IA · MEDISENSE';
    final labelColor = isLive
        ? AppColors.pulse
        : const Color(0xFFA5B4FC);

    return AnimatedContainer(
      duration: const Duration(milliseconds: 400),
      curve: Curves.easeInOut,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: cardColor,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: borderColor),
        boxShadow: isLive
            ? [
                BoxShadow(
                  color: AppColors.pulse.withValues(alpha: 0.12),
                  blurRadius: 20,
                  offset: const Offset(0, 8),
                ),
              ]
            : null,
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AnimatedContainer(
            duration: const Duration(milliseconds: 300),
            width: 36,
            height: 36,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: iconBg,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(iconData, color: iconColor, size: 18),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Row(
                  children: [
                    Text(
                      labelText,
                      style: AppFonts.mono(
                        color: labelColor,
                        fontSize: 9.5,
                        letterSpacing: 1.4,
                      ),
                    ),
                    if (isLive) ...[
                      const SizedBox(width: 6),
                      _LiveDot(),
                    ],
                  ],
                ),
                const SizedBox(height: 4),
                AnimatedSwitcher(
                  duration: const Duration(milliseconds: 350),
                  child: Text(
                    text,
                    key: ValueKey(text),
                    style: AppFonts.body(
                      color: AppColors.textPrimary,
                      fontSize: 13,
                      height: 1.5,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Pulsing red dot shown next to "EN DIRECT" label.
class _LiveDot extends StatefulWidget {
  @override
  State<_LiveDot> createState() => _LiveDotState();
}

class _LiveDotState extends State<_LiveDot>
    with SingleTickerProviderStateMixin {
  late AnimationController _ctrl;
  late Animation<double> _scale;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    )..repeat(reverse: true);
    _scale = Tween<double>(begin: 0.7, end: 1.2).animate(
      CurvedAnimation(parent: _ctrl, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ScaleTransition(
      scale: _scale,
      child: Container(
        width: 6,
        height: 6,
        decoration: BoxDecoration(
          color: AppColors.pulse,
          shape: BoxShape.circle,
          boxShadow: [
            BoxShadow(
              color: AppColors.pulse.withValues(alpha: 0.7),
              blurRadius: 4,
            ),
          ],
        ),
      ),
    );
  }
}

class _DeviceStatusCard extends StatelessWidget {
  final DeviceStatus device;
  const _DeviceStatusCard({required this.device});

  String _syncedAgo() {
    if (device.lastSync == null) return 'pas encore synchronisé';
    final diff = DateTime.now().difference(device.lastSync!);
    if (diff.inMinutes < 1) return 'à l\'instant';
    if (diff.inMinutes < 60) return 'il y a ${diff.inMinutes}min';
    if (diff.inHours < 24) return 'il y a ${diff.inHours}h';
    return 'il y a ${diff.inDays}j';
  }

  @override
  Widget build(BuildContext context) {
    final battery = device.battery;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: const Color(0x801C2333),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.line),
      ),
      child: Row(
        children: [
          Container(
            width: 32,
            height: 32,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: AppColors.oxy.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Icon(Icons.bluetooth, color: AppColors.oxy, size: 16),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  'Bracelet connecté',
                  style: AppFonts.body(
                    color: AppColors.textPrimary,
                    fontSize: 13,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  'sync ${_syncedAgo()}${battery != null ? ' · batterie $battery%' : ''}',
                  style: AppFonts.mono(
                    color: AppColors.textMuted,
                    fontSize: 9.5,
                    letterSpacing: 0.6,
                  ),
                ),
              ],
            ),
          ),
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              color: AppColors.riskSafe,
              shape: BoxShape.circle,
              boxShadow: [
                BoxShadow(
                  color: AppColors.riskSafe.withValues(alpha: 0.6),
                  blurRadius: 6,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// No device + syncing states
// ─────────────────────────────────────────────────────────────────────────────

class _NoDeviceState extends StatelessWidget {
  final Future<void> Function() onConnect;
  final Future<void> Function()? onSimulate;
  const _NoDeviceState({required this.onConnect, this.onSimulate});

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: onConnect,
      color: AppColors.aiFrom,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.symmetric(horizontal: 32),
        children: [
          SizedBox(
            height: MediaQuery.of(context).size.height * 0.85,
            child: _NoDeviceContent(
              onConnect: onConnect,
              onSimulate: onSimulate,
            ),
          ),
        ],
      ),
    );
  }
}

class _NoDeviceContent extends StatelessWidget {
  final VoidCallback onConnect;
  final Future<void> Function()? onSimulate;
  const _NoDeviceContent({required this.onConnect, this.onSimulate});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        mainAxisSize: MainAxisSize.min,
        children: [
          SizedBox(
            width: 140,
            height: 140,
            child: Stack(
              alignment: Alignment.center,
              children: [
                const PulseRing(
                  size: 140,
                  rings: 3,
                  color: AppColors.oxy,
                  period: Duration(milliseconds: 2400),
                ),
                Container(
                  width: 64,
                  height: 64,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(18),
                    color: AppColors.oxy.withValues(alpha: 0.12),
                  ),
                  alignment: Alignment.center,
                  child: const Icon(Icons.bluetooth,
                      color: AppColors.oxy, size: 28),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),
          Text(
            'Connectez votre bracelet',
            textAlign: TextAlign.center,
            style: AppFonts.display(
              color: AppColors.textPrimary,
              fontSize: 24,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Scannez le QR sur votre bracelet pour synchroniser fréquence cardiaque, SpO₂ et HRV.',
            textAlign: TextAlign.center,
            style: AppFonts.body(
              color: AppColors.textSecondary,
              fontSize: 13,
              height: 1.5,
            ),
          ),
          const SizedBox(height: 28),
          GestureDetector(
            onTap: onConnect,
            child: Container(
              width: 120,
              height: 120,
              decoration: BoxDecoration(
                color: AppColors.surface1,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppColors.line),
              ),
              alignment: Alignment.center,
              child: const Icon(
                Icons.qr_code_2_rounded,
                color: AppColors.text1,
                size: 84,
              ),
            ),
          ),
          if (onSimulate != null) ...[
            const SizedBox(height: 16),
            GestureDetector(
              onTap: () => onSimulate!(),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 11),
                decoration: BoxDecoration(
                  border: Border.all(color: AppColors.oxy.withValues(alpha: 0.4)),
                  borderRadius: BorderRadius.circular(99),
                ),
                child: Text(
                  'Mode démo',
                  style: AppFonts.body(
                    color: AppColors.oxy,
                    fontSize: 13,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Pulse hero — animated heart-rate visualization
// ─────────────────────────────────────────────────────────────────────────────

class _PulseHero extends StatelessWidget {
  final int bpm;
  final int spo2;
  final int? hrv;
  final int? restingHr;
  final String? anomalyNarrative;
  const _PulseHero({
    required this.bpm,
    required this.spo2,
    this.hrv,
    this.restingHr,
    this.anomalyNarrative,
  });

  @override
  Widget build(BuildContext context) {
    // Drive the pulse rings at the actual BPM (clamped to a reasonable demo
    // range so a missing/zero reading doesn't divide-by-zero or spin too fast).
    final safeBpm = bpm.clamp(40, 180);
    final periodMs = (60000 / safeBpm).round();
    final narrative = anomalyNarrative?.trim();
    final showBanner = narrative != null && narrative.isNotEmpty;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        _buildHeroContainer(periodMs),
        if (showBanner) ...[
          const SizedBox(height: 10),
          _AnomalyNarrativeBanner(narrative: narrative),
        ],
      ],
    );
  }

  Widget _buildHeroContainer(int periodMs) {
    return Container(
      height: 220,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(28),
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            AppColors.surface1,
            AppColors.pulse.withValues(alpha: 0.08),
          ],
        ),
        border: Border.all(color: AppColors.line),
      ),
      child: Stack(
        children: [
          // Radial glow blob, top-right
          Positioned(
            top: -40,
            right: -40,
            child: Container(
              width: 180,
              height: 180,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: RadialGradient(
                  colors: [
                    AppColors.pulse.withValues(alpha: 0.18),
                    Colors.transparent,
                  ],
                  stops: const [0.0, 0.8],
                ),
              ),
            ),
          ),
          // Pulse rings + central BPM
          Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                SizedBox(
                  width: 140,
                  height: 140,
                  child: Stack(
                    alignment: Alignment.center,
                    children: [
                      PulseRing(
                        size: 140,
                        rings: 3,
                        color: AppColors.pulse,
                        period: Duration(milliseconds: periodMs),
                      ),
                      Container(
                        width: 86,
                        height: 86,
                        alignment: Alignment.center,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          gradient: RadialGradient(
                            colors: [
                              AppColors.pulse.withValues(alpha: 0.28),
                              AppColors.pulse.withValues(alpha: 0.08),
                            ],
                          ),
                          border: Border.all(
                            color: AppColors.pulse.withValues(alpha: 0.5),
                            width: 2,
                          ),
                        ),
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Text(
                              '$bpm',
                              style: AppFonts.display(
                                color: AppColors.pulse,
                                fontSize: 34,
                                fontWeight: FontWeight.w700,
                                height: 1,
                                letterSpacing: -0.5,
                              ),
                            ),
                            Text(
                              'BPM',
                              style: AppFonts.mono(
                                color: AppColors.pulse.withValues(alpha: 0.8),
                                fontSize: 9,
                                letterSpacing: 1.6,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 4),
                if (restingHr != null)
                  Text(
                    'FC REPOS · $restingHr BPM',
                    style: AppFonts.mono(
                      color: AppColors.pulse.withValues(alpha: 0.7),
                      fontSize: 9.5,
                      letterSpacing: 1.4,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                const SizedBox(height: 6),
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    _PulseChip(
                      icon: Icons.air_rounded,
                      color: AppColors.oxy,
                      value: '$spo2%',
                    ),
                    if (hrv != null) ...[
                      const SizedBox(width: 10),
                      _PulseChip(
                        icon: Icons.graphic_eq_rounded,
                        color: AppColors.hrv,
                        value: '${hrv}ms',
                      ),
                    ],
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Amber banner shown below the pulse hero when a live anomaly narrative is active.
/// Replaces the bare BPM number with a sentence the patient can act on.
class _AnomalyNarrativeBanner extends StatelessWidget {
  final String narrative;
  const _AnomalyNarrativeBanner({required this.narrative});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(16),
        color: AppColors.warnAmber.withValues(alpha: 0.10),
        border: Border.all(color: AppColors.warnAmber.withValues(alpha: 0.40)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.warning_amber_rounded, color: AppColors.warnAmber, size: 18),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              narrative,
              style: AppFonts.body(
                color: AppColors.textPrimary,
                fontSize: 13,
                height: 1.35,
              ),
            ),
          ),
        ],
      ),
    );
  }
}


class _PulseChip extends StatelessWidget {
  final IconData icon;
  final Color color;
  final String value;
  const _PulseChip({
    required this.icon,
    required this.color,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(99),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: color, size: 13),
          const SizedBox(width: 5),
          Text(
            value,
            style: AppFonts.mono(
              color: color,
              fontSize: 11,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.4,
            ),
          ),
        ],
      ),
    );
  }
}

class _SyncingState extends StatelessWidget {
  const _SyncingState();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const PulseRing(
            size: 120,
            rings: 3,
            color: AppColors.aiFrom,
            period: Duration(milliseconds: 1800),
          ),
          const SizedBox(height: 22),
          Text(
            'Synchronisation en cours...',
            style: AppFonts.body(
              color: AppColors.textSecondary,
              fontSize: 14,
            ),
          ),
        ],
      ),
    );
  }
}
