import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../../core/api/dio_client.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_fonts.dart';
import '../../../../core/widgets/anim/bubble_in.dart';
import '../../../../services/appointment_reminder_scheduler.dart';
import '../../../auth/presentation/providers/auth_provider.dart';
import '../../data/models/appointment_model.dart';
import '../widgets/appointment_card.dart';

enum _ViewMode { day, upcoming }

String _dioErrorMessage(DioException e) {
  return switch (e.type) {
    DioExceptionType.connectionTimeout =>
      'Délai de connexion dépassé. Vérifiez votre réseau.',
    DioExceptionType.connectionError =>
      'Impossible de joindre le serveur (${e.message?.split(":").last.trim() ?? ""})',
    DioExceptionType.receiveTimeout =>
      'Le serveur met trop de temps à répondre.',
    _ => e.message ?? 'Erreur réseau inconnue',
  };
}

final appointmentsProvider =
    FutureProvider.autoDispose.family<List<AppointmentModel>, DateTime>(
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
      if (e.response?.statusCode == 401) {
        throw Exception('Session expirée. Veuillez vous reconnecter.');
      }
      throw Exception(_dioErrorMessage(e));
    }
  },
);

/// Unbounded "à venir" feed — fetches every appointment for the caller and
/// keeps only the ones whose end-time hasn't passed.
final upcomingAppointmentsProvider =
    FutureProvider.autoDispose<List<AppointmentModel>>((ref) async {
  final dio = createDio();
  try {
    final res = await dio.get('/appointments');
    final list = res.data as List;
    final all = list
        .map((j) => AppointmentModel.fromJson(j as Map<String, dynamic>))
        .toList();
    final now = DateTime.now();
    all.retainWhere((a) {
      final at = a.scheduledAt;
      if (at == null) return false;
      final endsAt = at.add(Duration(minutes: a.durationMinutes));
      return endsAt.isAfter(now);
    });
    all.sort((a, b) => a.scheduledAt!.compareTo(b.scheduledAt!));
    return all;
  } on DioException catch (e) {
    if (e.response?.statusCode == 404) return [];
    if (e.response?.statusCode == 401) {
      throw Exception('Session expirée. Veuillez vous reconnecter.');
    }
    throw Exception(_dioErrorMessage(e));
  }
});


class AppointmentsPage extends ConsumerStatefulWidget {
  const AppointmentsPage({super.key});

  @override
  ConsumerState<AppointmentsPage> createState() => _AppointmentsPageState();
}

class _AppointmentsPageState extends ConsumerState<AppointmentsPage> {
  DateTime _selectedDate = DateTime.now();
  _ViewMode _mode = _ViewMode.day;

  bool _canCancel(AppointmentModel a) =>
      a.status == AppointmentStatus.scheduled ||
      a.status == AppointmentStatus.confirmed;

  void _scheduleReminders(List<AppointmentModel> appointments) {
    // Fire-and-forget — never block UI on the local-notif plugin.
    // ignore: unawaited_futures
    AppointmentReminderScheduler.instance.syncFromAppointments(appointments);
  }

  Future<void> _refresh() async {
    if (_mode == _ViewMode.day) {
      ref.invalidate(appointmentsProvider);
      await ref.read(appointmentsProvider(_selectedDate).future);
    } else {
      ref.invalidate(upcomingAppointmentsProvider);
      await ref.read(upcomingAppointmentsProvider.future);
    }
  }

  void _openTeleconsult(AppointmentModel a) {
    // Placeholder — until a real meeting URL is wired into the appointment
    // schema, surface a hint so the demo doesn't break.
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          'Téléconsultation avec ${a.doctorName} — lien à venir.',
        ),
      ),
    );
  }

  Future<void> _confirmCancel(AppointmentModel a) async {
    final ok = await showModalBottomSheet<bool>(
      context: context,
      backgroundColor: AppColors.surface1,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 20, 20, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'Annuler ce rendez-vous ?',
                style: AppFonts.display(
                  color: AppColors.textPrimary,
                  fontSize: 17,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                '${a.doctorName} · ${a.time}',
                style: AppFonts.body(
                  color: AppColors.textSecondary,
                  fontSize: 13,
                ),
              ),
              const SizedBox(height: 18),
              ElevatedButton(
                onPressed: () => Navigator.of(ctx).pop(true),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.riskHigh,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                ),
                child: const Text('Confirmer l\'annulation'),
              ),
              const SizedBox(height: 8),
              TextButton(
                onPressed: () => Navigator.of(ctx).pop(false),
                child: Text(
                  'Garder le rendez-vous',
                  style: AppFonts.body(
                    color: AppColors.textSecondary,
                    fontSize: 13,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
    if (ok != true || !mounted) return;

    final dio = createDio();
    try {
      await dio.patch('/appointments/${a.id}/cancel');
      ref.invalidate(appointmentsProvider);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Rendez-vous annulé')),
        );
      }
    } on DioException catch (e) {
      if (!mounted) return;
      final detail = e.response?.data is Map
          ? (e.response!.data as Map)['detail']?.toString()
          : e.message;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Échec annulation: ${detail ?? "réessayez"}')),
      );
    }
  }

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
    final isPatient =
        ref.watch(authProvider).user?.role == 'patient';
    final apptAsync = _mode == _ViewMode.day
        ? ref.watch(appointmentsProvider(_selectedDate))
        : ref.watch(upcomingAppointmentsProvider);
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
              ref.invalidate(upcomingAppointmentsProvider);
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
                  onTap: _mode == _ViewMode.day ? _pickDate : null,
                  child: Text(
                    _mode == _ViewMode.day
                        ? '${dateLabel.toUpperCase()} · CABINET'
                        : 'À VENIR · CABINET',
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
                const SizedBox(height: 12),
                _ViewModeToggle(
                  mode: _mode,
                  onChanged: (m) => setState(() => _mode = m),
                ),
                const SizedBox(height: 10),
                _DoctorsDirectoryEntry(
                  onTap: () => context.push('/appointments/doctors'),
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
                    const SizedBox(height: 6),
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 32),
                      child: Text(
                        e.toString().replaceFirst('Exception: ', ''),
                        textAlign: TextAlign.center,
                        style: AppFonts.mono(
                          color: AppColors.textMuted,
                          fontSize: 10,
                        ),
                      ),
                    ),
                    const SizedBox(height: 16),
                    GestureDetector(
                      onTap: _refresh,
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 20, vertical: 10),
                        decoration: BoxDecoration(
                          gradient: AppColors.aiGrad,
                          borderRadius: BorderRadius.circular(99),
                        ),
                        child: Text(
                          'Réessayer',
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
              ),
              data: (appointments) {
                _scheduleReminders(appointments);

                if (appointments.isEmpty) {
                  return RefreshIndicator(
                    onRefresh: _refresh,
                    color: AppColors.aiFrom,
                    child: ListView(
                      physics:
                          const AlwaysScrollableScrollPhysics(),
                      children: [
                        SizedBox(
                          height: MediaQuery.of(context).size.height * 0.5,
                          child: _EmptyState(onPick: _pickDate),
                        ),
                      ],
                    ),
                  );
                }

                final summaryCard = isPatient
                    ? _StatusSummaryCard(appointments: appointments)
                    : _RiskSummaryCard(
                        high: appointments
                            .where((a) => a.riskColor == RiskColor.red)
                            .length,
                        med: appointments
                            .where((a) => a.riskColor == RiskColor.orange)
                            .length,
                        low: appointments
                            .where((a) => a.riskColor == RiskColor.green)
                            .length,
                      );

                final nextUpcoming = _nextUpcoming(appointments);

                return RefreshIndicator(
                  onRefresh: _refresh,
                  color: AppColors.aiFrom,
                  child: ListView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.fromLTRB(20, 14, 20, 110),
                    children: [
                      summaryCard,
                      if (nextUpcoming != null) ...[
                        const SizedBox(height: 12),
                        _CountdownBanner(appointment: nextUpcoming),
                      ],
                      const SizedBox(height: 16),
                      if (_mode == _ViewMode.upcoming)
                        ..._buildGroupedCards(appointments, isPatient)
                      else
                        ...appointments.asMap().entries.map(
                              (e) => AppointmentCard(
                                appointment: e.value,
                                index: e.key,
                                isPatientView: isPatient,
                                onTap: _canCancel(e.value)
                                    ? () => _confirmCancel(e.value)
                                    : null,
                              ),
                            ),
                    ],
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  /// Pick the next appointment whose start is still in the future.
  AppointmentModel? _nextUpcoming(List<AppointmentModel> all) {
    final now = DateTime.now();
    AppointmentModel? best;
    for (final a in all) {
      final at = a.scheduledAt;
      if (at == null) continue;
      if (!at.isAfter(now)) continue;
      if (a.status == AppointmentStatus.cancelled) continue;
      if (best == null ||
          at.isBefore(best.scheduledAt ?? DateTime(9999))) {
        best = a;
      }
    }
    return best;
  }

  List<Widget> _buildGroupedCards(
    List<AppointmentModel> appointments,
    bool isPatient,
  ) {
    // Group consecutively because `appointments` is already sorted in the
    // provider; this keeps a stable header per day without an extra sort.
    final result = <Widget>[];
    String? currentKey;
    var idx = 0;
    for (final a in appointments) {
      final at = a.scheduledAt;
      if (at == null) continue;
      final key = DateFormat('yyyy-MM-dd').format(at);
      if (key != currentKey) {
        currentKey = key;
        result.add(_DayHeader(date: at));
      }
      result.add(
        AppointmentCard(
          appointment: a,
          index: idx++,
          isPatientView: isPatient,
          onTap: _canCancel(a)
              ? () => _confirmCancel(a)
              : (a.isTeleconsult ? () => _openTeleconsult(a) : null),
        ),
      );
    }
    return result;
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
              '$total RDV',
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

class _ViewModeToggle extends StatelessWidget {
  final _ViewMode mode;
  final ValueChanged<_ViewMode> onChanged;
  const _ViewModeToggle({required this.mode, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: AppColors.surface1,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.line),
      ),
      child: Row(
        children: [
          Expanded(
            child: _ViewModeTab(
              label: 'Jour',
              selected: mode == _ViewMode.day,
              onTap: () => onChanged(_ViewMode.day),
            ),
          ),
          Expanded(
            child: _ViewModeTab(
              label: 'À venir',
              selected: mode == _ViewMode.upcoming,
              onTap: () => onChanged(_ViewMode.upcoming),
            ),
          ),
        ],
      ),
    );
  }
}

class _ViewModeTab extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;
  const _ViewModeTab({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        padding: const EdgeInsets.symmetric(vertical: 8),
        decoration: BoxDecoration(
          gradient: selected ? AppColors.aiGrad : null,
          borderRadius: BorderRadius.circular(9),
        ),
        alignment: Alignment.center,
        child: Text(
          label,
          style: AppFonts.body(
            color: selected ? Colors.white : AppColors.textSecondary,
            fontSize: 13,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    );
  }
}

class _DoctorsDirectoryEntry extends StatelessWidget {
  final VoidCallback onTap;
  const _DoctorsDirectoryEntry({required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
        decoration: BoxDecoration(
          color: AppColors.surface1,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppColors.aiFrom.withValues(alpha: 0.4)),
        ),
        child: Row(
          children: [
            Container(
              width: 40,
              height: 40,
              alignment: Alignment.center,
              decoration: const BoxDecoration(
                shape: BoxShape.circle,
                gradient: AppColors.aiGrad,
              ),
              child: const Icon(
                Icons.person_search_rounded,
                color: Colors.white,
                size: 22,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    'Annuaire des médecins',
                    style: AppFonts.display(
                      color: AppColors.textPrimary,
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    'Parcourir par spécialité et réserver',
                    style: AppFonts.body(
                      color: AppColors.textMuted,
                      fontSize: 11.5,
                    ),
                  ),
                ],
              ),
            ),
            const Icon(
              Icons.arrow_forward_ios_rounded,
              color: AppColors.aiFrom,
              size: 14,
            ),
          ],
        ),
      ),
    );
  }
}

class _CountdownBanner extends StatefulWidget {
  final AppointmentModel appointment;
  const _CountdownBanner({required this.appointment});

  @override
  State<_CountdownBanner> createState() => _CountdownBannerState();
}

class _CountdownBannerState extends State<_CountdownBanner> {
  late final Stream<DateTime> _ticker;

  @override
  void initState() {
    super.initState();
    _ticker = Stream<DateTime>.periodic(
      const Duration(seconds: 30),
      (_) => DateTime.now(),
    );
  }

  String _format(Duration d) {
    if (d.inDays >= 1) {
      final hours = d.inHours.remainder(24);
      return 'Dans ${d.inDays}j ${hours}h';
    }
    if (d.inHours >= 1) {
      final mins = d.inMinutes.remainder(60);
      return 'Dans ${d.inHours}h ${mins.toString().padLeft(2, '0')}min';
    }
    if (d.inMinutes >= 1) {
      return 'Dans ${d.inMinutes} min';
    }
    return 'Imminent';
  }

  @override
  Widget build(BuildContext context) {
    final at = widget.appointment.scheduledAt;
    if (at == null) return const SizedBox.shrink();

    return StreamBuilder<DateTime>(
      stream: _ticker,
      builder: (_, __) {
        final remaining = at.difference(DateTime.now());
        if (remaining.isNegative) return const SizedBox.shrink();
        final label = _format(remaining);
        return Container(
          padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
          decoration: BoxDecoration(
            gradient: LinearGradient(
              colors: [
                AppColors.aiFrom.withValues(alpha: 0.18),
                AppColors.aiTo.withValues(alpha: 0.10),
              ],
            ),
            borderRadius: BorderRadius.circular(14),
            border:
                Border.all(color: AppColors.aiFrom.withValues(alpha: 0.45)),
          ),
          child: Row(
            children: [
              const Icon(
                Icons.schedule_rounded,
                color: AppColors.aiFrom,
                size: 18,
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      label,
                      style: AppFonts.display(
                        color: AppColors.textPrimary,
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      '${widget.appointment.doctorName} · ${widget.appointment.time}',
                      style: AppFonts.body(
                        color: AppColors.textSecondary,
                        fontSize: 11.5,
                      ),
                    ),
                  ],
                ),
              ),
              if (widget.appointment.isTeleconsult)
                const Icon(
                  Icons.videocam_rounded,
                  color: AppColors.aiTo,
                  size: 18,
                ),
            ],
          ),
        );
      },
    );
  }
}

class _DayHeader extends StatelessWidget {
  final DateTime date;
  const _DayHeader({required this.date});

  @override
  Widget build(BuildContext context) {
    final now = DateTime.now();
    final isToday = date.year == now.year &&
        date.month == now.month &&
        date.day == now.day;
    final tomorrow = now.add(const Duration(days: 1));
    final isTomorrow = date.year == tomorrow.year &&
        date.month == tomorrow.month &&
        date.day == tomorrow.day;

    final base = DateFormat('EEEE d MMMM', 'fr_FR').format(date);
    final label = isToday
        ? "Aujourd'hui · $base"
        : (isTomorrow ? 'Demain · $base' : base);

    return Padding(
      padding: const EdgeInsets.fromLTRB(2, 12, 2, 8),
      child: Text(
        label.toUpperCase(),
        style: AppFonts.mono(
          color: AppColors.textMuted,
          fontSize: 10,
          letterSpacing: 1.2,
        ),
      ),
    );
  }
}

class _StatusSummaryCard extends StatelessWidget {
  final List<AppointmentModel> appointments;
  const _StatusSummaryCard({required this.appointments});

  @override
  Widget build(BuildContext context) {
    int count(AppointmentStatus s) =>
        appointments.where((a) => a.status == s).length;

    final cells = [
      _RiskCell(
        n: count(AppointmentStatus.confirmed) +
            count(AppointmentStatus.scheduled),
        label: 'Planifié',
        color: AppColors.aiFrom,
        idx: 0,
      ),
      _RiskCell(
        n: count(AppointmentStatus.completed),
        label: 'Terminé',
        color: AppColors.riskSafe,
        idx: 1,
      ),
      _RiskCell(
        n: count(AppointmentStatus.cancelled) +
            count(AppointmentStatus.noShow),
        label: 'Annulé',
        color: AppColors.riskHigh,
        idx: 2,
      ),
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
              Container(width: 1, height: 56, color: AppColors.line),
          ],
        ],
      ),
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
