import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../../core/api/dio_client.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_fonts.dart';
import '../../../../core/widgets/anim/bubble_in.dart';
import '../../data/models/appointment_model.dart';
import '../widgets/appointment_card.dart';

final appointmentsProvider =
    FutureProvider.family<List<AppointmentModel>, DateTime>(
  (ref, date) async {
    final dio = createDio();
    final dateStr = DateFormat('yyyy-MM-dd').format(date);
    try {
      final res =
          await dio.get('/appointments', queryParameters: {'date': dateStr});
      final list = res.data as List;
      return list
          .map((j) => AppointmentModel.fromJson(j as Map<String, dynamic>))
          .toList();
    } on DioException catch (e) {
      if (e.response?.statusCode == 404) return [];
      rethrow;
    }
  },
);

class AppointmentsPage extends ConsumerStatefulWidget {
  const AppointmentsPage({super.key});

  @override
  ConsumerState<AppointmentsPage> createState() => _AppointmentsPageState();
}

class _AppointmentsPageState extends ConsumerState<AppointmentsPage> {
  DateTime _selectedDate = DateTime.now();

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _selectedDate,
      firstDate: DateTime.now().subtract(const Duration(days: 365)),
      useRootNavigator: true,
      lastDate: DateTime.now().add(const Duration(days: 365)),
      builder: (ctx, child) => Theme(
        data: Theme.of(ctx).copyWith(
          colorScheme: const ColorScheme.dark(
            primary: AppColors.aiFrom,
            surface: AppColors.surface2,
          ),
        ),
        child: child!,
      ),
    );
    if (picked != null) setState(() => _selectedDate = picked);
  }

  @override
  Widget build(BuildContext context) {
    final apptAsync = ref.watch(appointmentsProvider(_selectedDate));
    final dateLabel =
        DateFormat('EEEE d MMMM', 'fr_FR').format(_selectedDate);
    final topPad = MediaQuery.of(context).padding.top;

    return Scaffold(
      backgroundColor: AppColors.surface0,
      floatingActionButton: Padding(
        padding: const EdgeInsets.only(bottom: 96, right: 4),
        child: FloatingActionButton.extended(
          heroTag: 'new-appointment-fab',
          backgroundColor: AppColors.aiFrom,
          foregroundColor: Colors.white,
          icon: const Icon(Icons.add),
          label: Text(
            'Nouveau RDV',
            style: AppFonts.body(
              color: Colors.white,
              fontSize: 13.5,
              fontWeight: FontWeight.w600,
            ),
          ),
          onPressed: () async {
            final created = await context.push<bool>('/appointments/new');
            if (created == true) {
              ref.invalidate(appointmentsProvider);
            }
          },
        ),
      ),
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ─── Header ──────────────────────────────────────────────
          Padding(
            padding: EdgeInsets.fromLTRB(20, topPad + 12, 20, 8),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                GestureDetector(
                  onTap: _pickDate,
                  child: Text(
                    '${dateLabel.toUpperCase()} · CABINET',
                    style: AppFonts.mono(
                      color: AppColors.textMuted,
                      fontSize: 10,
                      letterSpacing: 1.4,
                    ),
                  ),
                ),
                const SizedBox(height: 4),
                apptAsync.when(
                  loading: () => _titleRow(null),
                  error: (_, __) => _titleRow(null),
                  data: (list) => _titleRow(list.length),
                ),
              ],
            ),
          ),

          // ─── Body ────────────────────────────────────────────────
          Expanded(
            child: apptAsync.when(
              loading: _ShimmerList.new,
              error: (e, _) => Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.wifi_off,
                        color: AppColors.textMuted, size: 40),
                    const SizedBox(height: 12),
                    Text(
                      'Impossible de charger les rendez-vous',
                      style: AppFonts.body(
                        color: AppColors.textMuted,
                        fontSize: 13,
                      ),
                    ),
                  ],
                ),
              ),
              data: (appointments) {
                if (appointments.isEmpty) {
                  return _EmptyState(onPick: _pickDate);
                }

                final low = appointments
                    .where((a) => a.riskColor == RiskColor.green)
                    .length;
                final med = appointments
                    .where((a) => a.riskColor == RiskColor.orange)
                    .length;
                final high = appointments
                    .where((a) => a.riskColor == RiskColor.red)
                    .length;

                return ListView(
                  padding: const EdgeInsets.fromLTRB(20, 14, 20, 110),
                  children: [
                    _RiskSummaryCard(high: high, med: med, low: low),
                    const SizedBox(height: 16),
                    ...appointments.asMap().entries.map(
                          (e) => AppointmentCard(
                            appointment: e.value,
                            index: e.key,
                          ),
                        ),
                  ],
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _titleRow(int? total) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        Expanded(
          child: Text(
            'Agenda',
            style: AppFonts.display(
              color: AppColors.textPrimary,
              fontSize: 28,
              fontWeight: FontWeight.w600,
              letterSpacing: -0.56,
            ),
          ),
        ),
        if (total != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 6),
            child: Text(
              '$total pat.',
              style: AppFonts.mono(
                color: AppColors.textSecondary,
                fontSize: 10,
                letterSpacing: 0.4,
              ),
            ),
          ),
      ],
    );
  }
}

class _RiskSummaryCard extends StatelessWidget {
  final int high;
  final int med;
  final int low;
  const _RiskSummaryCard({
    required this.high,
    required this.med,
    required this.low,
  });

  @override
  Widget build(BuildContext context) {
    final cells = [
      _RiskCell(n: high, label: 'Élevé', color: AppColors.riskHigh, idx: 0),
      _RiskCell(n: med, label: 'Modéré', color: AppColors.riskWarn, idx: 1),
      _RiskCell(n: low, label: 'Faible', color: AppColors.riskSafe, idx: 2),
    ];
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 16),
      decoration: BoxDecoration(
        color: AppColors.surface1,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.line),
      ),
      child: Row(
        children: [
          for (var i = 0; i < cells.length; i++) ...[
            Expanded(child: cells[i]),
            if (i < cells.length - 1)
              Container(
                width: 1,
                height: 56,
                color: AppColors.line,
              ),
          ],
        ],
      ),
    );
  }
}

class _RiskCell extends StatelessWidget {
  final int n;
  final String label;
  final Color color;
  final int idx;
  const _RiskCell({
    required this.n,
    required this.label,
    required this.color,
    required this.idx,
  });

  @override
  Widget build(BuildContext context) {
    return BubbleIn(
      delay: Duration(milliseconds: 80 * idx),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            '$n',
            style: AppFonts.display(
              color: color,
              fontSize: 36,
              fontWeight: FontWeight.w600,
              height: 1,
              shadows: [
                Shadow(
                  color: color.withValues(alpha: 0.33),
                  blurRadius: 18,
                ),
              ],
            ),
          ),
          const SizedBox(height: 7),
          Text(
            label.toUpperCase(),
            style: AppFonts.mono(
              color: AppColors.textMuted,
              fontSize: 9.5,
              letterSpacing: 1.4,
            ),
          ),
        ],
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  final VoidCallback onPick;
  const _EmptyState({required this.onPick});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 84,
            height: 84,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: RadialGradient(
                colors: [
                  AppColors.aiTo.withValues(alpha: 0.3),
                  Colors.transparent,
                ],
              ),
            ),
            child: const Icon(
              Icons.calendar_month_outlined,
              color: AppColors.aiTo,
              size: 36,
            ),
          ),
          const SizedBox(height: 16),
          Text(
            'Aucun rendez-vous ce jour',
            style: AppFonts.display(
              color: AppColors.textPrimary,
              fontSize: 18,
              fontWeight: FontWeight.w600,
              letterSpacing: -0.2,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            'Sélectionnez une autre date.',
            style: AppFonts.body(
              color: AppColors.textMuted,
              fontSize: 12,
            ),
          ),
          const SizedBox(height: 14),
          GestureDetector(
            onTap: onPick,
            child: Container(
              padding: const EdgeInsets.symmetric(
                  horizontal: 16, vertical: 9),
              decoration: BoxDecoration(
                gradient: AppColors.aiGrad,
                borderRadius: BorderRadius.circular(99),
              ),
              child: Text(
                'Changer de date',
                style: AppFonts.body(
                  color: Colors.white,
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ShimmerList extends StatefulWidget {
  @override
  State<_ShimmerList> createState() => _ShimmerListState();
}

class _ShimmerListState extends State<_ShimmerList>
    with SingleTickerProviderStateMixin {
  late AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ListView.builder(
      padding: const EdgeInsets.fromLTRB(20, 14, 20, 110),
      itemCount: 5,
      itemBuilder: (_, __) => AnimatedBuilder(
        animation: _ctrl,
        builder: (_, __) => Container(
          height: 96,
          margin: const EdgeInsets.only(bottom: 10),
          decoration: BoxDecoration(
            color: Color.lerp(
              AppColors.surface1,
              AppColors.surface2,
              _ctrl.value,
            ),
            borderRadius: BorderRadius.circular(16),
          ),
        ),
      ),
    );
  }
}
