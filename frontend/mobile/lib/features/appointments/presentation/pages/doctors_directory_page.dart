import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/api/dio_client.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_fonts.dart';
import '../../../../core/widgets/anim/bubble_in.dart';
import '../../data/models/doctor_model.dart';

final _doctorsDirectoryProvider =
    FutureProvider.autoDispose<List<DoctorModel>>((ref) async {
  final dio = createDio();
  try {
    final res = await dio.get('/doctors');
    final list = res.data as List;
    return list
        .map((j) => DoctorModel.fromJson(j as Map<String, dynamic>))
        .toList();
  } on DioException catch (e) {
    if (e.response?.statusCode == 401 || e.response?.statusCode == 403) {
      throw Exception('Session expirée — reconnectez-vous');
    }
    throw Exception(e.message ?? 'Erreur réseau');
  }
});

class DoctorsDirectoryPage extends ConsumerStatefulWidget {
  const DoctorsDirectoryPage({super.key});

  @override
  ConsumerState<DoctorsDirectoryPage> createState() =>
      _DoctorsDirectoryPageState();
}

class _DoctorsDirectoryPageState extends ConsumerState<DoctorsDirectoryPage> {
  String _query = '';
  String? _specialtyFilter;

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(_doctorsDirectoryProvider);
    final topPad = MediaQuery.of(context).padding.top;

    return Scaffold(
      backgroundColor: AppColors.surface0,
      body: SafeArea(
        top: false,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: EdgeInsets.fromLTRB(20, topPad + 12, 20, 8),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      GestureDetector(
                        onTap: () => Navigator.of(context).maybePop(),
                        child: const Icon(Icons.arrow_back_rounded,
                            color: AppColors.textPrimary, size: 22),
                      ),
                      const SizedBox(width: 12),
                      Text(
                        'Annuaire des médecins',
                        style: AppFonts.display(
                          color: AppColors.textPrimary,
                          fontSize: 22,
                          fontWeight: FontWeight.w600,
                          letterSpacing: -0.4,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    onChanged: (v) => setState(() => _query = v.trim()),
                    style: AppFonts.body(
                      color: AppColors.textPrimary,
                      fontSize: 14,
                    ),
                    decoration: InputDecoration(
                      hintText: 'Rechercher un médecin…',
                      hintStyle: AppFonts.body(
                        color: AppColors.textMuted,
                        fontSize: 14,
                      ),
                      prefixIcon: const Icon(
                        Icons.search_rounded,
                        color: AppColors.textMuted,
                        size: 20,
                      ),
                      filled: true,
                      fillColor: AppColors.surface1,
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(14),
                        borderSide: const BorderSide(color: AppColors.line),
                      ),
                      enabledBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(14),
                        borderSide: const BorderSide(color: AppColors.line),
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(14),
                        borderSide:
                            const BorderSide(color: AppColors.aiFrom),
                      ),
                    ),
                  ),
                ],
              ),
            ),
            Expanded(
              child: async.when(
                loading: () => const Center(
                  child: CircularProgressIndicator(color: AppColors.aiFrom),
                ),
                error: (e, _) => Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Text(
                      e.toString().replaceFirst('Exception: ', ''),
                      textAlign: TextAlign.center,
                      style: AppFonts.body(
                        color: AppColors.textMuted,
                        fontSize: 13,
                      ),
                    ),
                  ),
                ),
                data: (doctors) {
                  final specialties = <String>{
                    for (final d in doctors)
                      if (d.specialty != null && d.specialty!.isNotEmpty)
                        d.specialty!,
                  }.toList()
                    ..sort();

                  final filtered = doctors.where((d) {
                    final matchesQ = _query.isEmpty ||
                        d.displayName
                            .toLowerCase()
                            .contains(_query.toLowerCase()) ||
                        (d.specialty ?? '')
                            .toLowerCase()
                            .contains(_query.toLowerCase());
                    final matchesS = _specialtyFilter == null ||
                        d.specialty == _specialtyFilter;
                    return matchesQ && matchesS;
                  }).toList();

                  return ListView(
                    padding: const EdgeInsets.fromLTRB(20, 4, 20, 32),
                    children: [
                      if (specialties.isNotEmpty)
                        SizedBox(
                          height: 36,
                          child: ListView(
                            scrollDirection: Axis.horizontal,
                            children: [
                              _SpecialtyChip(
                                label: 'Toutes',
                                selected: _specialtyFilter == null,
                                onTap: () =>
                                    setState(() => _specialtyFilter = null),
                              ),
                              for (final s in specialties)
                                _SpecialtyChip(
                                  label: s,
                                  selected: _specialtyFilter == s,
                                  onTap: () =>
                                      setState(() => _specialtyFilter = s),
                                ),
                            ],
                          ),
                        ),
                      const SizedBox(height: 12),
                      if (filtered.isEmpty)
                        Padding(
                          padding: const EdgeInsets.symmetric(vertical: 48),
                          child: Center(
                            child: Text(
                              'Aucun médecin trouvé',
                              style: AppFonts.body(
                                color: AppColors.textMuted,
                                fontSize: 13,
                              ),
                            ),
                          ),
                        ),
                      ...filtered.asMap().entries.map(
                            (e) => _DoctorTile(
                              doctor: e.value,
                              index: e.key,
                              onBook: () => context.push(
                                '/appointments/new',
                                extra: e.value,
                              ),
                            ),
                          ),
                    ],
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SpecialtyChip extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;
  const _SpecialtyChip({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final c = selected ? AppColors.aiFrom : AppColors.textMuted;
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
          decoration: BoxDecoration(
            color: selected
                ? AppColors.aiFrom.withValues(alpha: 0.15)
                : AppColors.surface1,
            borderRadius: BorderRadius.circular(99),
            border: Border.all(
              color: selected ? AppColors.aiFrom : AppColors.line,
            ),
          ),
          child: Center(
            child: Text(
              label,
              style: AppFonts.body(
                color: c,
                fontSize: 12,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _DoctorTile extends StatelessWidget {
  final DoctorModel doctor;
  final int index;
  final VoidCallback onBook;
  const _DoctorTile({
    required this.doctor,
    required this.index,
    required this.onBook,
  });

  @override
  Widget build(BuildContext context) {
    final initials = doctor.displayName
        .replaceFirst('Dr. ', '')
        .split(' ')
        .where((p) => p.isNotEmpty)
        .take(2)
        .map((p) => p[0].toUpperCase())
        .join();

    return BubbleIn(
      delay: Duration(milliseconds: 30 * index),
      child: Container(
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.fromLTRB(14, 14, 14, 14),
        decoration: BoxDecoration(
          color: AppColors.surface1,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppColors.line),
        ),
        child: Row(
          children: [
            Container(
              width: 46,
              height: 46,
              alignment: Alignment.center,
              decoration: const BoxDecoration(
                shape: BoxShape.circle,
                gradient: AppColors.aiGrad,
              ),
              child: Text(
                initials.isEmpty ? 'Dr' : initials,
                style: AppFonts.display(
                  color: Colors.white,
                  fontSize: 14,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    doctor.displayName,
                    style: AppFonts.display(
                      color: AppColors.textPrimary,
                      fontSize: 15,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    doctor.specialty ?? 'Médecine générale',
                    style: AppFonts.body(
                      color: AppColors.textSecondary,
                      fontSize: 12,
                    ),
                  ),
                ],
              ),
            ),
            GestureDetector(
              onTap: onBook,
              child: Container(
                padding: const EdgeInsets.symmetric(
                    horizontal: 14, vertical: 8),
                decoration: BoxDecoration(
                  gradient: AppColors.aiGrad,
                  borderRadius: BorderRadius.circular(99),
                ),
                child: Text(
                  'Réserver',
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
    );
  }
}
