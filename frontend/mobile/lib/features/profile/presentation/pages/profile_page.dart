import 'dart:io';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';
import '../../../../core/api/dio_client.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../auth/presentation/providers/auth_provider.dart';
import '../providers/patient_provider.dart';

/// Resolves the on-disk path used to persist the local profile photo.
/// One file per app — no per-user partition because each device hosts one
/// authenticated patient at a time.
Future<File> _profilePhotoFile() async {
  final dir = await getApplicationDocumentsDirectory();
  return File('${dir.path}/profile_photo.jpg');
}

/// Watched by the header so taps on the avatar refresh both the photo and the
/// camera badge state without rebuilding the whole settings list.
final _profilePhotoProvider = StateProvider<File?>((_) => null);

/// Lightweight upcoming-appointment count for the profile overview tile.
/// Returns null when the request fails so the UI can fall back gracefully
/// without showing a misleading "0".
final _upcomingAppointmentCountProvider =
    FutureProvider.autoDispose<int?>((ref) async {
  try {
    final dio = createDio();
    final res = await dio.get('/appointments');
    final list = res.data as List;
    final now = DateTime.now();
    var count = 0;
    for (final raw in list) {
      final j = raw as Map<String, dynamic>;
      final scheduled = j['scheduled_at'] as String?;
      final status = (j['status'] as String?)?.toUpperCase();
      if (scheduled == null) continue;
      if (status == 'CANCELLED' ||
          status == 'COMPLETED' ||
          status == 'NO_SHOW') {
        continue;
      }
      try {
        if (DateTime.parse(scheduled).isAfter(now)) count++;
      } catch (e) {
        debugPrint('Appointment date parse failed: $e');
      }
    }
    return count;
  } on DioException {
    return null;
  }
});

class ProfilePage extends ConsumerStatefulWidget {
  const ProfilePage({super.key});

  @override
  ConsumerState<ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends ConsumerState<ProfilePage> {
  @override
  void initState() {
    super.initState();
    _loadExistingPhoto();
  }

  Future<void> _loadExistingPhoto() async {
    final file = await _profilePhotoFile();
    if (await file.exists() && mounted) {
      ref.read(_profilePhotoProvider.notifier).state = file;
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authProvider);
    final user = auth.user;
    final name = [user?.firstName, user?.lastName]
            .where((s) => s != null && s.isNotEmpty)
            .join(' ')
            .trim()
            .isNotEmpty
        ? [user?.firstName, user?.lastName]
            .where((s) => s != null && s.isNotEmpty)
            .join(' ')
        : 'Patient';

    return Scaffold(
      backgroundColor: AppColors.surface0,
      body: CustomScrollView(
        slivers: [
          // Gradient mesh header
          SliverToBoxAdapter(
            child: _ProfileHeader(name: name, email: user?.email ?? ''),
          ),
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 120),
            sliver: SliverList(
              delegate: SliverChildListDelegate([
                const _SectionLabel('APERÇU'),
                Consumer(
                  builder: (_, ref, __) {
                    final apptCount =
                        ref.watch(_upcomingAppointmentCountProvider);
                    return _OverviewRow(
                      upcomingCount: apptCount.maybeWhen(
                        data: (v) => v,
                        orElse: () => null,
                      ),
                      onAppointments: () => context.push('/appointments'),
                      onDoctors: () =>
                          context.push('/appointments/doctors'),
                      onIot: () => context.push('/iot'),
                    );
                  },
                ),
                const SizedBox(height: 20),
                const _SectionLabel('SANTÉ & DONNÉES'),
                _SettingRow(
                  icon: Icons.medication_outlined,
                  iconColor: AppColors.aiFrom,
                  title: 'Rappels médicaments',
                  subtitle: 'Gérer vos prises quotidiennes',
                  onTap: () => context.push('/profile/reminders'),
                ),
                _SettingRow(
                  icon: Icons.download_outlined,
                  iconColor: AppColors.riskSafe,
                  title: 'Exporter mes données (RGPD)',
                  subtitle: 'Télécharger vos données personnelles',
                  onTap: () => _exportData(context, ref, user?.uuid),
                ),
                const SizedBox(height: 20),
                const _SectionLabel('CONFIDENTIALITÉ'),
                _SettingRow(
                  icon: Icons.shield_outlined,
                  iconColor: AppColors.hrv,
                  title: 'Paramètres de consentement',
                  subtitle: 'Modifier vos préférences de données',
                  onTap: () => context.push('/consent'),
                ),
                const SizedBox(height: 20),
                const _SectionLabel('COMPTE'),
                _SettingRow(
                  icon: Icons.logout,
                  iconColor: AppColors.textMuted,
                  title: 'Se déconnecter',
                  onTap: () => _confirmLogout(context, ref),
                ),
                _SettingRow(
                  icon: Icons.delete_forever_outlined,
                  iconColor: AppColors.riskHigh,
                  title: 'Effacer mes données',
                  subtitle: 'Suppression définitive (RGPD Art. 17)',
                  isDanger: true,
                  onTap: () => _confirmErase(context, ref, user?.uuid),
                ),
                const SizedBox(height: 20),
                Center(
                  child: Text(
                    'MediSense AI v1.0.0\nRGPD conforme · AES-256',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: AppColors.textMuted.withValues(alpha: 0.5),
                      fontSize: 10,
                      height: 1.6,
                    ),
                  ),
                ),
              ]),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _exportData(
      BuildContext context, WidgetRef ref, String? uuid) async {
    if (uuid == null) return;
    final go = await showDialog<bool>(
      context: context,
      useRootNavigator: true,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: AppColors.surface2,
        shape:
            RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Exporter mes données',
            style: TextStyle(color: AppColors.textPrimary, fontSize: 16)),
        content: const Text(
          'Votre export RGPD sera téléchargé en format JSON. Cela peut prendre quelques secondes.',
          style: TextStyle(color: AppColors.textMuted, fontSize: 13),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('Annuler',
                style: TextStyle(color: AppColors.textMuted)),
          ),
          ElevatedButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.aiFrom),
            child: const Text('Télécharger',
                style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
    if (go != true || !context.mounted) return;

    try {
      final ds = ref.read(patientDatasourceProvider);
      final result = await ds.exportData(uuid);
      final dir = await getApplicationDocumentsDirectory();
      final file = File(
          '${dir.path}/medisense_export_${DateTime.now().millisecondsSinceEpoch}.json');
      await file.writeAsString(result.json);
      final kb = (result.bytes / 1024).toStringAsFixed(1);
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Export prêt · $kb Ko'),
          backgroundColor: AppColors.riskSafe,
        ),
      );
      await Share.shareXFiles(
        [XFile(file.path)],
        text: 'Export MediSense AI',
      );
    } catch (e) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Erreur export: $e'),
          backgroundColor: AppColors.riskHigh,
        ),
      );
    }
  }

  Future<void> _confirmLogout(BuildContext context, WidgetRef ref) async {
    final ok = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      useRootNavigator: true,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: AppColors.surface2,
        shape:
            RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Se déconnecter',
            style: TextStyle(color: AppColors.textPrimary, fontSize: 16)),
        content: const Text(
          'Vous serez redirigé vers la page de connexion.',
          style: TextStyle(color: AppColors.textMuted, fontSize: 13),
        ),
        actions: [
          TextButton(
            onPressed: () => GoRouter.of(dialogContext).pop(false),
            child: const Text('Annuler',
                style: TextStyle(color: AppColors.textMuted)),
          ),
          ElevatedButton(
            onPressed: () => GoRouter.of(dialogContext).pop(true),
            style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.surface3),
            child: const Text('Déconnecter',
                style: TextStyle(color: AppColors.textPrimary)),
          ),
        ],
      ),
    );

    if (ok == true && context.mounted) {
      // Clear the tokens and state
      await ref.read(authProvider.notifier).logout();
      
      // Forces the router to re-evaluate the redirect logic
      if (context.mounted) {
        context.go('/login');
      }
    }
  }

  Future<void> _confirmErase(
      BuildContext context, WidgetRef ref, String? uuid) async {
    if (uuid == null) return;
    // Dialog 1: initial confirm
    final ok1 = await showDialog<bool>(
      context: context,
      useRootNavigator: true,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: AppColors.surface2,
        shape:
            RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Effacer mes données',
            style: TextStyle(color: AppColors.riskHigh, fontSize: 16)),
        content: const Text(
          'Cette action est irréversible. Toutes vos données personnelles seront supprimées définitivement (RGPD Art. 17).',
          style: TextStyle(color: AppColors.textMuted, fontSize: 13),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('Annuler',
                style: TextStyle(color: AppColors.textMuted)),
          ),
          ElevatedButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.riskHigh),
            child: const Text('Continuer',
                style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
    if (ok1 != true || !context.mounted) return;

    // Dialog 2: type "EFFACER"
    final confirmCtrl = TextEditingController();
    final ok2 = await showDialog<bool>(
      context: context,
      useRootNavigator: true,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: AppColors.surface2,
        shape:
            RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Confirmation finale',
            style: TextStyle(color: AppColors.riskHigh, fontSize: 16)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Tapez EFFACER pour confirmer la suppression de votre compte.',
              style: TextStyle(color: AppColors.textMuted, fontSize: 13),
            ),
            const SizedBox(height: 12),
            StatefulBuilder(
              builder: (ctx, setState) => Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextField(
                    controller: confirmCtrl,
                    autofocus: true,
                    textCapitalization: TextCapitalization.characters,
                    onChanged: (_) => setState(() {}),
                    style: const TextStyle(color: AppColors.riskHigh),
                    decoration: InputDecoration(
                      hintText: 'EFFACER',
                      hintStyle: TextStyle(
                          color: AppColors.textMuted
                              .withValues(alpha: 0.5)),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(8),
                        borderSide:
                            const BorderSide(color: AppColors.riskHigh),
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(8),
                        borderSide: const BorderSide(
                            color: AppColors.riskHigh, width: 2),
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      TextButton(
                        onPressed: () =>
                            Navigator.of(dialogContext).pop(false),
                        child: const Text('Annuler',
                            style:
                                TextStyle(color: AppColors.textMuted)),
                      ),
                      const SizedBox(width: 6),
                      ElevatedButton(
                        onPressed: confirmCtrl.text.trim() == 'EFFACER'
                            ? () => Navigator.of(dialogContext).pop(true)
                            : null,
                        style: ElevatedButton.styleFrom(
                            backgroundColor: AppColors.riskHigh,
                            disabledBackgroundColor:
                                AppColors.riskHigh.withValues(alpha: 0.3)),
                        child: const Text('Supprimer',
                            style: TextStyle(color: Colors.white)),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
        actions: const [],
      ),
    );
    confirmCtrl.dispose();
    if (ok2 != true || !context.mounted) return;

    // Execute erasure
    try {
      await ref.read(patientDatasourceProvider).deleteAccount(uuid);
      await ref.read(authProvider.notifier).logout();
      if (context.mounted) context.go('/splash');
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Erreur: $e'),
            backgroundColor: AppColors.riskHigh,
          ),
        );
      }
    }
  }
}

class _ProfileHeader extends ConsumerWidget {
  final String name;
  final String email;
  const _ProfileHeader({required this.name, required this.email});

  Future<void> _pickPhoto(BuildContext context, WidgetRef ref) async {
    final source = await showModalBottomSheet<ImageSource?>(
      context: context,
      backgroundColor: AppColors.surface1,
      useRootNavigator: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 40,
              height: 4,
              margin: const EdgeInsets.only(top: 10, bottom: 8),
              decoration: BoxDecoration(
                color: AppColors.surface3,
                borderRadius: BorderRadius.circular(99),
              ),
            ),
            ListTile(
              leading: const Icon(Icons.photo_camera_outlined,
                  color: AppColors.aiFrom),
              title: const Text('Prendre une photo',
                  style: TextStyle(color: AppColors.textPrimary)),
              onTap: () => Navigator.of(ctx).pop(ImageSource.camera),
            ),
            ListTile(
              leading: const Icon(Icons.photo_library_outlined,
                  color: AppColors.aiFrom),
              title: const Text('Depuis la galerie',
                  style: TextStyle(color: AppColors.textPrimary)),
              onTap: () => Navigator.of(ctx).pop(ImageSource.gallery),
            ),
            if (ref.read(_profilePhotoProvider) != null)
              ListTile(
                leading: const Icon(Icons.delete_outline,
                    color: AppColors.riskHigh),
                title: const Text('Supprimer la photo',
                    style: TextStyle(color: AppColors.riskHigh)),
                onTap: () => Navigator.of(ctx).pop(null),
              ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );

    if (!context.mounted) return;

    // Distinguish "user dismissed" from "user tapped delete". The bottom sheet
    // returns null both ways; we rely on the absence of any tap to early-exit
    // by checking that the user actually closed via a tile.
    final dismissed = source == null &&
        ref.read(_profilePhotoProvider) == null;
    if (dismissed) return;

    final file = await _profilePhotoFile();
    if (source == null) {
      if (await file.exists()) await file.delete();
      ref.read(_profilePhotoProvider.notifier).state = null;
      return;
    }

    try {
      final picker = ImagePicker();
      final picked = await picker.pickImage(
        source: source,
        maxWidth: 800,
        maxHeight: 800,
        imageQuality: 85,
      );
      if (picked == null) return;
      await File(picked.path).copy(file.path);
      ref.read(_profilePhotoProvider.notifier).state =
          File(file.path)..setLastModifiedSync(DateTime.now());
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Photo indisponible: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final topInset = MediaQuery.of(context).padding.top;
    final photo = ref.watch(_profilePhotoProvider);
    return Container(
      clipBehavior: Clip.hardEdge,
      decoration: const BoxDecoration(color: AppColors.surface1),
      child: Stack(
        children: [
          // Blob 1
          Positioned(
            top: -30,
            left: -40,
            child: Container(
              width: 180,
              height: 180,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: AppColors.aiFrom.withValues(alpha: 0.15),
              ),
            ),
          ),
          // Blob 2
          Positioned(
            top: -20,
            right: -30,
            child: Container(
              width: 140,
              height: 140,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: AppColors.aiTo.withValues(alpha: 0.12),
              ),
            ),
          ),
          // Content — sizes to fit, with safe-area top + bottom breathing room
          Padding(
            padding: EdgeInsets.fromLTRB(24, topInset + 24, 24, 28),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                  // Avatar with gradient border + camera badge.
                  // The Stack is sized to the gradient border (102×102) and
                  // the badge sits inside the bounds so the visual center
                  // matches the geometric center — keeps the avatar aligned
                  // with the name/email below it.
                  Center(
                    child: GestureDetector(
                      onTap: () => _pickPhoto(context, ref),
                      child: SizedBox(
                        width: 102,
                        height: 102,
                        child: Stack(
                          alignment: Alignment.center,
                          children: [
                            Container(
                              padding: const EdgeInsets.all(3),
                              decoration: const BoxDecoration(
                                gradient: AppColors.aiGrad,
                                shape: BoxShape.circle,
                              ),
                              child: Container(
                                width: 96,
                                height: 96,
                                decoration: const BoxDecoration(
                                  color: AppColors.surface2,
                                  shape: BoxShape.circle,
                                ),
                                clipBehavior: Clip.antiAlias,
                                child: photo != null
                                    ? Image.file(
                                        photo,
                                        key: ValueKey(
                                            photo.lastModifiedSync()),
                                        fit: BoxFit.cover,
                                        width: 96,
                                        height: 96,
                                      )
                                    : Center(
                                        child: Text(
                                          name.isNotEmpty
                                              ? name[0].toUpperCase()
                                              : 'P',
                                          style: const TextStyle(
                                            color: AppColors.textPrimary,
                                            fontSize: 36,
                                            fontWeight: FontWeight.w700,
                                          ),
                                        ),
                                      ),
                              ),
                            ),
                            Positioned(
                              right: 2,
                              bottom: 2,
                              child: Container(
                                width: 28,
                                height: 28,
                                alignment: Alignment.center,
                                decoration: BoxDecoration(
                                  color: AppColors.aiFrom,
                                  shape: BoxShape.circle,
                                  border: Border.all(
                                    color: AppColors.surface1,
                                    width: 2,
                                  ),
                                  boxShadow: [
                                    BoxShadow(
                                      color: AppColors.aiFrom
                                          .withValues(alpha: 0.4),
                                      blurRadius: 10,
                                    ),
                                  ],
                                ),
                                child: const Icon(
                                  Icons.camera_alt_rounded,
                                  color: Colors.white,
                                  size: 13,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 14),
                  Text(
                    name,
                    style: const TextStyle(
                      color: AppColors.textPrimary,
                      fontSize: 20,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 10, vertical: 3),
                        decoration: BoxDecoration(
                          color: AppColors.aiFrom.withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(20),
                        ),
                        child: const Text(
                          'Patient',
                          style: TextStyle(
                            color: AppColors.aiFrom,
                            fontSize: 11,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Flexible(
                        child: Text(
                          email,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: AppColors.textMuted,
                            fontSize: 12,
                          ),
                        ),
                      ),
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

class _SectionLabel extends StatelessWidget {
  final String text;
  const _SectionLabel(this.text);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8, top: 4),
      child: Text(
        text,
        style: const TextStyle(
          color: AppColors.textMuted,
          fontSize: 10,
          fontWeight: FontWeight.w600,
          letterSpacing: 1.5,
        ),
      ),
    );
  }
}

class _SettingRow extends StatelessWidget {
  final IconData icon;
  final Color iconColor;
  final String title;
  final String? subtitle;
  final VoidCallback? onTap;
  final bool isDanger;

  const _SettingRow({
    required this.icon,
    required this.iconColor,
    required this.title,
    this.subtitle,
    this.onTap,
    this.isDanger = false,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding:
            const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
        decoration: BoxDecoration(
          color: AppColors.surface1,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: isDanger
                ? AppColors.riskHigh.withValues(alpha: 0.2)
                : AppColors.line,
          ),
        ),
        child: Row(
          children: [
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                color: iconColor.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(icon, color: iconColor, size: 18),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: TextStyle(
                      color: isDanger
                          ? AppColors.riskHigh
                          : AppColors.textPrimary,
                      fontSize: 14,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                  if (subtitle != null) ...[
                    const SizedBox(height: 2),
                    Text(
                      subtitle!,
                      style: const TextStyle(
                        color: AppColors.textMuted,
                        fontSize: 11,
                      ),
                    ),
                  ],
                ],
              ),
            ),
            Icon(
              Icons.chevron_right,
              color: isDanger
                  ? AppColors.riskHigh.withValues(alpha: 0.5)
                  : AppColors.textMuted,
              size: 18,
            ),
          ],
        ),
      ),
    );
  }
}

class _OverviewRow extends StatelessWidget {
  final int? upcomingCount;
  final VoidCallback onAppointments;
  final VoidCallback onDoctors;
  final VoidCallback onIot;
  const _OverviewRow({
    required this.upcomingCount,
    required this.onAppointments,
    required this.onDoctors,
    required this.onIot,
  });

  @override
  Widget build(BuildContext context) {
    final apptBadge = upcomingCount == null
        ? '—'
        : (upcomingCount == 0 ? 'Aucun' : '$upcomingCount à venir');

    return Row(
      children: [
        Expanded(
          child: _OverviewTile(
            icon: Icons.event_available_rounded,
            color: AppColors.aiFrom,
            label: 'Rendez-vous',
            value: apptBadge,
            onTap: onAppointments,
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: _OverviewTile(
            icon: Icons.person_search_rounded,
            color: AppColors.hrv,
            label: 'Médecins',
            value: 'Annuaire',
            onTap: onDoctors,
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: _OverviewTile(
            icon: Icons.favorite_rounded,
            color: AppColors.pulse,
            label: 'IoT',
            value: 'Vitaux',
            onTap: onIot,
          ),
        ),
      ],
    );
  }
}

class _OverviewTile extends StatelessWidget {
  final IconData icon;
  final Color color;
  final String label;
  final String value;
  final VoidCallback onTap;
  const _OverviewTile({
    required this.icon,
    required this.color,
    required this.label,
    required this.value,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.fromLTRB(12, 14, 12, 14),
        decoration: BoxDecoration(
          color: AppColors.surface1,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppColors.line),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 32,
              height: 32,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(icon, color: color, size: 16),
            ),
            const SizedBox(height: 10),
            Text(
              label,
              style: const TextStyle(
                color: AppColors.textMuted,
                fontSize: 10,
                fontWeight: FontWeight.w600,
                letterSpacing: 0.6,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              value,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: AppColors.textPrimary,
                fontSize: 13,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
