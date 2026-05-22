import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../../core/api/dio_client.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_fonts.dart';
import '../../../auth/presentation/providers/auth_provider.dart';
import '../../data/models/doctor_model.dart';

final _doctorsProvider = FutureProvider.autoDispose<List<DoctorModel>>((ref) async {
  final auth = ref.watch(authProvider);
  if (auth.user == null) return <DoctorModel>[];

  final dio = createDio();
  try {
    final res = await dio.get('/doctors');
    final list = res.data as List;
    return list
        .map((j) => DoctorModel.fromJson(j as Map<String, dynamic>))
        .toList();
  } on DioException catch (e) {
    final status = e.response?.statusCode;
    if (status == 401 || status == 403) {
      throw Exception('Session expirée — reconnectez-vous');
    }
    if (e.type == DioExceptionType.connectionError ||
        e.type == DioExceptionType.connectionTimeout) {
      throw Exception('Serveur injoignable — vérifiez votre connexion');
    }
    throw Exception('Erreur ${status ?? "réseau"} — réessayez');
  }
});

class BookingPage extends ConsumerStatefulWidget {
  final DoctorModel? preselectedDoctor;
  const BookingPage({super.key, this.preselectedDoctor});

  @override
  ConsumerState<BookingPage> createState() => _BookingPageState();
}

class _BookingPageState extends ConsumerState<BookingPage> {
  DoctorModel? _doctor;
  DateTime _date = DateTime.now().add(const Duration(days: 1));
  TimeOfDay _time = const TimeOfDay(hour: 10, minute: 0);
  int _durationMinutes = 20;
  bool _submitting = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _doctor = widget.preselectedDoctor;
    // Hydrate auth user if we landed here without a populated provider
    // (e.g. hot reload, deep link, warm restart bypassing splash).
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (ref.read(authProvider).user == null) {
        ref.read(authProvider.notifier).loadUser();
      }
    });
  }

  DateTime get _scheduledAt =>
      DateTime(_date.year, _date.month, _date.day, _time.hour, _time.minute)
          .toUtc();

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _date,
      firstDate: DateTime.now(),
      lastDate: DateTime.now().add(const Duration(days: 365)),
      useRootNavigator: true,
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
    if (picked != null) setState(() => _date = picked);
  }

  Future<void> _pickTime() async {
    final picked = await showTimePicker(
      context: context,
      initialTime: _time,
      useRootNavigator: true,
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
    if (picked != null) setState(() => _time = picked);
  }

  Future<void> _submit() async {
    final patientUuid = ref.read(authProvider).user?.uuid;
    if (patientUuid == null) {
      setState(() => _error = 'Session expirée — reconnectez-vous');
      return;
    }
    if (_doctor == null) {
      setState(() => _error = 'Choisissez un docteur');
      return;
    }
    if (!_scheduledAt.isAfter(DateTime.now().toUtc())) {
      setState(() => _error = "La date doit être dans le futur");
      return;
    }

    setState(() {
      _submitting = true;
      _error = null;
    });

    try {
      final dio = createDio();
      await dio.post('/appointments', data: {
        'patient_uuid': patientUuid,
        'doctor_uuid': _doctor!.uuid,
        'scheduled_at': _scheduledAt.toIso8601String(),
        'duration_minutes': _durationMinutes,
      });
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Rendez-vous créé')),
      );
      context.pop(true); // signal success to caller
    } on DioException catch (e) {
      final status = e.response?.statusCode;
      final detail = e.response?.data is Map
          ? (e.response!.data['detail']?.toString())
          : null;
      setState(() {
        _error = switch (status) {
          409 => 'Ce créneau est déjà pris',
          404 => detail ?? 'Docteur ou patient introuvable',
          422 => detail ?? 'Données invalides',
          403 => 'Non autorisé',
          _ => 'Erreur réseau — réessayez',
        };
      });
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final doctorsAsync = ref.watch(_doctorsProvider);
    final topPad = MediaQuery.of(context).padding.top;
    final dateLabel = DateFormat('EEEE d MMMM y', 'fr_FR').format(_date);
    final timeLabel =
        '${_time.hour.toString().padLeft(2, '0')}:${_time.minute.toString().padLeft(2, '0')}';

    return Scaffold(
      backgroundColor: AppColors.surface0,
      body: SafeArea(
        top: false,
        child: ListView(
          padding: EdgeInsets.fromLTRB(20, topPad + 16, 20, 120),
          children: [
            Row(
              children: [
                IconButton(
                  icon: const Icon(Icons.arrow_back, color: AppColors.textPrimary),
                  onPressed: () => context.pop(),
                ),
                const SizedBox(width: 4),
                Text(
                  'Nouveau rendez-vous',
                  style: AppFonts.display(
                    color: AppColors.textPrimary,
                    fontSize: 22,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 24),

            const _Label('Docteur'),
            const SizedBox(height: 8),
            doctorsAsync.when(
              loading: () => _skeletonField(),
              error: (e, _) => Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _errorField(
                    e is Exception
                        ? e.toString().replaceFirst('Exception: ', '')
                        : 'Impossible de charger les docteurs',
                  ),
                  const SizedBox(height: 8),
                  GestureDetector(
                    onTap: () => ref.invalidate(_doctorsProvider),
                    child: Center(
                      child: Text(
                        'Réessayer',
                        style: AppFonts.body(
                          color: AppColors.aiFrom,
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
              data: (doctors) {
                if (doctors.isEmpty) {
                  return _errorField('Aucun docteur disponible');
                }
                _doctor ??= doctors.first;
                return _fieldShell(
                  child: DropdownButton<DoctorModel>(
                    value: _doctor,
                    isExpanded: true,
                    underline: const SizedBox.shrink(),
                    dropdownColor: AppColors.surface2,
                    iconEnabledColor: AppColors.textSecondary,
                    style: AppFonts.body(
                      color: AppColors.textPrimary,
                      fontSize: 14,
                    ),
                    items: doctors
                        .map((d) => DropdownMenuItem(
                              value: d,
                              child: Text(d.displayName),
                            ))
                        .toList(),
                    onChanged: (d) => setState(() => _doctor = d),
                  ),
                );
              },
            ),

            const SizedBox(height: 20),
            const _Label('Date'),
            const SizedBox(height: 8),
            _tapField(
              label: dateLabel,
              icon: Icons.calendar_today_outlined,
              onTap: _pickDate,
            ),

            const SizedBox(height: 20),
            const _Label('Heure'),
            const SizedBox(height: 8),
            _tapField(
              label: timeLabel,
              icon: Icons.access_time,
              onTap: _pickTime,
            ),

            const SizedBox(height: 20),
            const _Label('Durée'),
            const SizedBox(height: 8),
            _fieldShell(
              child: DropdownButton<int>(
                value: _durationMinutes,
                isExpanded: true,
                underline: const SizedBox.shrink(),
                dropdownColor: AppColors.surface2,
                iconEnabledColor: AppColors.textSecondary,
                style: AppFonts.body(
                  color: AppColors.textPrimary,
                  fontSize: 14,
                ),
                items: const [15, 20, 30, 45, 60]
                    .map((m) => DropdownMenuItem(
                          value: m,
                          child: Text('$m minutes'),
                        ))
                    .toList(),
                onChanged: (v) => setState(() => _durationMinutes = v ?? 20),
              ),
            ),

            if (_error != null) ...[
              const SizedBox(height: 18),
              Text(
                _error!,
                style: AppFonts.body(
                  color: AppColors.riskHigh,
                  fontSize: 13,
                ),
              ),
            ],

            const SizedBox(height: 28),
            SizedBox(
              height: 52,
              child: ElevatedButton(
                onPressed: _submitting ? null : _submit,
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.aiFrom,
                  foregroundColor: Colors.white,
                  disabledBackgroundColor:
                      AppColors.aiFrom.withValues(alpha: 0.4),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14),
                  ),
                ),
                child: _submitting
                    ? const SizedBox(
                        width: 22,
                        height: 22,
                        child: CircularProgressIndicator(
                          color: Colors.white,
                          strokeWidth: 2.4,
                        ),
                      )
                    : Text(
                        'Réserver',
                        style: AppFonts.body(
                          color: Colors.white,
                          fontSize: 15,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _fieldShell({required Widget child}) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
      decoration: BoxDecoration(
        color: AppColors.surface1,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.line),
      ),
      child: child,
    );
  }

  Widget _tapField({
    required String label,
    required IconData icon,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
        decoration: BoxDecoration(
          color: AppColors.surface1,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppColors.line),
        ),
        child: Row(
          children: [
            Icon(icon, color: AppColors.textSecondary, size: 18),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                label,
                style: AppFonts.body(
                  color: AppColors.textPrimary,
                  fontSize: 14,
                ),
              ),
            ),
            const Icon(Icons.chevron_right, color: AppColors.textMuted),
          ],
        ),
      ),
    );
  }

  Widget _skeletonField() => Container(
        height: 50,
        decoration: BoxDecoration(
          color: AppColors.surface1,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppColors.line),
        ),
      );

  Widget _errorField(String msg) => Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppColors.surface1,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppColors.line),
        ),
        child: Text(
          msg,
          style: AppFonts.body(
            color: AppColors.riskHigh,
            fontSize: 13,
          ),
        ),
      );
}

class _Label extends StatelessWidget {
  final String text;
  const _Label(this.text);

  @override
  Widget build(BuildContext context) {
    return Text(
      text.toUpperCase(),
      style: AppFonts.mono(
        color: AppColors.textMuted,
        fontSize: 10.5,
        letterSpacing: 1.4,
      ),
    );
  }
}
