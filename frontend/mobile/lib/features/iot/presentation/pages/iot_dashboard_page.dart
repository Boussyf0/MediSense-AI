import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_fonts.dart';
import '../../../../core/widgets/anim/pulse_ring.dart';
import '../../data/datasources/iot_remote_datasource.dart';
import '../../data/models/biometric_model.dart';
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
  final String trend;
  final String trendDir;
  final num Function(BiometricPoint) selector;
  const _Vital({
    required this.key,
    required this.label,
    required this.name,
    required this.unit,
    required this.icon,
    required this.color,
    required this.trend,
    required this.trendDir,
    required this.selector,
  });
}

class IotDashboardPage extends ConsumerStatefulWidget {
  const IotDashboardPage({super.key});

  @override
  ConsumerState<IotDashboardPage> createState() => _IotDashboardPageState();
}

class _IotDashboardPageState extends ConsumerState<IotDashboardPage> {
  String _activeKey = 'hr';
  String _range = '24h';

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

  List<_Vital> get _vitals => [
        _Vital(
          key: 'hr',
          label: 'BPM',
          name: 'Fréquence cardiaque',
          unit: '',
          icon: Icons.favorite_rounded,
          color: AppColors.pulse,
          trend: 'Normal · stable',
          trendDir: '↗',
          selector: (p) => p.heartRate,
        ),
        _Vital(
          key: 'spo2',
          label: 'SpO₂',
          name: 'Saturation O₂',
          unit: '%',
          icon: Icons.air_rounded,
          color: AppColors.oxy,
          trend: 'Excellent',
          trendDir: '✓',
          selector: (p) => p.spo2,
        ),
        _Vital(
          key: 'hrv',
          label: 'HRV',
          name: 'Variabilité',
          unit: 'ms',
          icon: Icons.graphic_eq_rounded,
          color: AppColors.hrv,
          trend: 'Bas · repos requis',
          trendDir: '↘',
          selector: (p) => p.hrv,
        ),
      ];

  @override
  Widget build(BuildContext context) {
    final deviceAsync = ref.watch(deviceProvider);
    final vitalsAsync = ref.watch(vitalsProvider(_apiRange));

    return Scaffold(
      backgroundColor: AppColors.surface0,
      body: SafeArea(
        child: deviceAsync.when(
          loading: () => _SyncingState(onDone: () {}),
          error: (_, __) => _NoDeviceState(
            onConnect: () => ref.invalidate(deviceProvider),
          ),
          data: (device) {
            if (device == null || !device.paired) {
              return _NoDeviceState(
                onConnect: () => ref.invalidate(deviceProvider),
              );
            }
            return vitalsAsync.when(
              loading: () => _SyncingState(onDone: () {}),
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
                  return Center(
                    child: Text(
                      'Aucune donnée biométrique',
                      style: AppFonts.body(
                          color: AppColors.textMuted, fontSize: 13),
                    ),
                  );
                }
                return _DataDashboard(
                  vitals: _vitals,
                  activeKey: _activeKey,
                  onActive: (k) => setState(() => _activeKey = k),
                  range: _range,
                  onRange: (r) => setState(() => _range = r),
                  latest: data.last,
                  sampled: _sample(data),
                  device: device,
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

  const _DataDashboard({
    required this.vitals,
    required this.activeKey,
    required this.onActive,
    required this.range,
    required this.onRange,
    required this.latest,
    required this.sampled,
    required this.device,
  });

  num _liveValue(_Vital v) {
    switch (v.key) {
      case 'spo2':
        return latest.spo2.round();
      case 'hrv':
        return latest.hrv.round();
      default:
        return latest.heartRate.round();
    }
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
                      'IOT · SYNC IL Y A 12S',
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
              Container(
                width: 38,
                height: 38,
                decoration: BoxDecoration(
                  color: AppColors.surface1,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: AppColors.line),
                ),
                child: const Icon(
                  Icons.more_horiz_rounded,
                  size: 18,
                  color: AppColors.text1,
                ),
              ),
            ],
          ),
        ),
        Expanded(
          child: ListView(
            padding: EdgeInsets.zero,
            children: [
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
                    return MetricCard(
                      icon: v.icon,
                      label: v.label,
                      name: v.name,
                      value: _liveValue(v),
                      unit: v.unit,
                      color: v.color,
                      trend: v.trend,
                      trendDir: v.trendDir,
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

  const _ChartCard({
    required this.vital,
    required this.range,
    required this.onRange,
    required this.latest,
    required this.sampled,
  });

  @override
  Widget build(BuildContext context) {
    final v = vital.selector(latest);
    final avg = (v * 0.94).round();
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
                          '${v.toStringAsFixed(0)}${vital.unit}',
                          style: AppFonts.display(
                            color: vital.color,
                            fontSize: 22,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        const SizedBox(width: 6),
                        Text(
                          'moy. $avg${vital.unit}',
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
              valueSelector: (p) => vital.selector(p).toDouble(),
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

class _InsightCard extends StatelessWidget {
  const _InsightCard();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.surface1,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.line),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 36,
            height: 36,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: AppColors.hrv.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Icon(Icons.auto_awesome,
                color: Color(0xFFA78BFA), size: 18),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  'INSIGHT IA · XGBOOST',
                  style: AppFonts.mono(
                    color: const Color(0xFFA5B4FC),
                    fontSize: 9.5,
                    letterSpacing: 1.4,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  'Votre HRV diurne est en baisse de 18% sur 7 jours. Compatible avec un déficit de sommeil — visez 7h cette nuit.',
                  style: AppFonts.body(
                    color: AppColors.textPrimary,
                    fontSize: 13,
                    height: 1.5,
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
  final VoidCallback onConnect;
  const _NoDeviceState({required this.onConnect});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 32),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
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
        ],
      ),
    );
  }
}

class _SyncingState extends StatefulWidget {
  final VoidCallback onDone;
  const _SyncingState({required this.onDone});

  @override
  State<_SyncingState> createState() => _SyncingStateState();
}

class _SyncingStateState extends State<_SyncingState> {
  @override
  void initState() {
    super.initState();
    Future.delayed(const Duration(seconds: 3), () {
      if (mounted) widget.onDone();
    });
  }

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
