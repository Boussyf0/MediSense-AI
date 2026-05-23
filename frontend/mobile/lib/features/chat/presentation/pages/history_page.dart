import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/widgets/anim/bubble_in.dart';
import '../providers/chat_provider.dart';

class _TagTone {
  final Color color;
  final Color background;
  const _TagTone(this.color, this.background);
}

const _tagTones = <String, _TagTone>{
  'urgence': _TagTone(Color(0xFFF43F5E), Color(0x1FF43F5E)),
  'traitement': _TagTone(Color(0xFFA78BFA), Color(0x1FA78BFA)),
  'symptômes': _TagTone(Color(0xFF38BDF8), Color(0x1F38BDF8)),
  'mesure': _TagTone(Color(0xFF22C55E), Color(0x1F22C55E)),
  'nutrition': _TagTone(Color(0xFFF59E0B), Color(0x1FF59E0B)),
  'prévention': _TagTone(Color(0xFF94A3B8), Color(0x1F94A3B8)),
};

const _filterIcons = <String, IconData>{
  'all': Icons.apps_rounded,
  'urgence': Icons.emergency_rounded,
  'traitement': Icons.medication_rounded,
  'symptômes': Icons.sick_rounded,
  'mesure': Icons.monitor_heart_rounded,
  'nutrition': Icons.restaurant_rounded,
  'prévention': Icons.shield_rounded,
};

class _Convo {
  final String id;
  final String title;
  final String preview;
  final String date;
  final String tag;
  final bool urgent;
  final int sources;
  const _Convo({
    required this.id,
    required this.title,
    required this.preview,
    required this.date,
    required this.tag,
    required this.sources,
    this.urgent = false,
  });

  factory _Convo.fromJson(Map<String, dynamic> j) {
    final preview = (j['preview'] as String?) ?? '';
    final rawTitle = j['title'] as String?;
    final title = (rawTitle != null && rawTitle.trim().isNotEmpty)
        ? rawTitle
        : (preview.isNotEmpty
            ? (preview.length > 60 ? '${preview.substring(0, 60)}…' : preview)
            : 'Nouvelle conversation');
    final searchText = ('$title $preview').toLowerCase();
    final derivedTag = _deriveTag(searchText);
    return _Convo(
      id: j['id']?.toString() ?? '',
      title: title,
      preview: preview,
      date: _formatDate(
          (j['last_message_at'] as String?) ?? (j['created_at'] as String?)),
      tag: derivedTag,
      urgent: searchText.contains('urgence') ||
          searchText.contains('samu') ||
          searchText.contains('141'),
      sources: (j['sources_count'] as num?)?.toInt() ?? 0,
    );
  }

  static String _deriveTag(String text) {
    if (text.contains('urgence') ||
        text.contains('samu') ||
        text.contains('141') ||
        text.contains('thoracique') ||
        text.contains('respirer')) {
      return 'urgence';
    }
    if (text.contains('doliprane') ||
        text.contains('paracetamol') ||
        text.contains('ibuprof') ||
        text.contains('antibiot') ||
        text.contains('posologie') ||
        text.contains('dosage') ||
        text.contains('médicament') ||
        text.contains('medicament') ||
        text.contains('comprim')) {
      return 'traitement';
    }
    if (text.contains('tension') ||
        text.contains('glycém') ||
        text.contains('glycem') ||
        text.contains('rythme') ||
        text.contains('mesure') ||
        text.contains('cardiaque')) {
      return 'mesure';
    }
    if (text.contains('aliment') ||
        text.contains('nutrition') ||
        text.contains('régime') ||
        text.contains('regime') ||
        text.contains('manger')) {
      return 'nutrition';
    }
    if (text.contains('prévention') ||
        text.contains('prevention') ||
        text.contains('vaccin') ||
        text.contains('hygiène') ||
        text.contains('hygiene')) {
      return 'prévention';
    }
    return 'symptômes';
  }

  static String _formatDate(String? iso) {
    if (iso == null) return '';
    try {
      final dt = DateTime.parse(iso).toLocal();
      final now = DateTime.now();
      final h = dt.hour.toString().padLeft(2, '0');
      final m = dt.minute.toString().padLeft(2, '0');
      if (dt.year == now.year &&
          dt.month == now.month &&
          dt.day == now.day) {
        return "Aujourd'hui · $h:$m";
      }
      final y = now.subtract(const Duration(days: 1));
      if (dt.year == y.year && dt.month == y.month && dt.day == y.day) {
        return 'Hier · $h:$m';
      }
      const months = [
        'janv', 'févr', 'mars', 'avr', 'mai', 'juin',
        'juil', 'août', 'sept', 'oct', 'nov', 'déc',
      ];
      return '${dt.day} ${months[dt.month - 1]} · $h:$m';
    } catch (_) {
      return iso;
    }
  }
}

final conversationsProvider =
    FutureProvider.autoDispose<List<_Convo>>((ref) async {
  final ds = ref.read(chatDatasourceProvider);
  final raw = await ds.getConversations();
  return raw.map(_Convo.fromJson).toList();
});

class HistoryPage extends ConsumerStatefulWidget {
  const HistoryPage({super.key});

  @override
  ConsumerState<HistoryPage> createState() => _HistoryPageState();
}

class _HistoryPageState extends ConsumerState<HistoryPage> {
  String _filter = 'all';

  @override
  Widget build(BuildContext context) {
    final filters = <String>['all', ..._tagTones.keys];
    final async = ref.watch(conversationsProvider);

    return Scaffold(
      backgroundColor: AppColors.surface0,
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    async.maybeWhen(
                      data: (d) => '${d.length} conversations · 30j',
                      orElse: () => '... conversations · 30j',
                    ),
                    style: GoogleFonts.jetBrainsMono(
                      fontSize: 10,
                      color: AppColors.textMuted,
                      letterSpacing: 1.4,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Historique',
                    style: GoogleFonts.spaceGrotesk(
                      fontSize: 28,
                      fontWeight: FontWeight.w600,
                      color: AppColors.textPrimary,
                      letterSpacing: -0.56,
                      height: 1.0,
                    ),
                  ),
                ],
              ),
            ),
            SizedBox(
              height: 56,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.fromLTRB(20, 10, 20, 10),
                itemCount: filters.length,
                separatorBuilder: (_, __) => const SizedBox(width: 8),
                itemBuilder: (context, i) {
                  final f = filters[i];
                  final active = f == _filter;
                  final icon = _filterIcons[f] ?? Icons.label_outline_rounded;
                  final tone = _tagTones[f];
                  final fg = active
                      ? Colors.white
                      : (tone?.color ?? AppColors.textPrimary);
                  return GestureDetector(
                    onTap: () => setState(() => _filter = f),
                    child: Container(
                      alignment: Alignment.center,
                      padding: const EdgeInsets.symmetric(
                          horizontal: 14, vertical: 8),
                      decoration: BoxDecoration(
                        gradient: active ? AppColors.aiGrad : null,
                        color: active
                            ? null
                            : (tone?.background ?? AppColors.surface1),
                        borderRadius: BorderRadius.circular(99),
                        border: active
                            ? null
                            : Border.all(
                                color: (tone?.color ?? AppColors.line)
                                    .withValues(alpha: 0.4),
                                width: 1,
                              ),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(icon, size: 14, color: fg),
                          const SizedBox(width: 6),
                          Text(
                            f == 'all' ? 'TOUT' : f.toUpperCase(),
                            style: GoogleFonts.jetBrainsMono(
                              fontSize: 11,
                              fontWeight: FontWeight.w700,
                              letterSpacing: 0.6,
                              color: fg,
                              height: 1.0,
                            ),
                          ),
                        ],
                      ),
                    ),
                  );
                },
              ),
            ),
            Expanded(
              child: async.when(
                loading: () => ListView.separated(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 110),
                  itemCount: 3,
                  separatorBuilder: (_, __) => const SizedBox(height: 8),
                  itemBuilder: (_, __) => const _SkeletonCard(),
                ),
                error: (e, _) => Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.cloud_off_outlined,
                          color: AppColors.textMuted, size: 36),
                      const SizedBox(height: 12),
                      Text(
                        'Impossible de charger l\'historique',
                        style: GoogleFonts.inter(
                          fontSize: 13,
                          color: AppColors.textSecondary,
                        ),
                      ),
                      const SizedBox(height: 16),
                      ElevatedButton(
                        onPressed: () =>
                            ref.invalidate(conversationsProvider),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppColors.surface2,
                        ),
                        child: const Text('Réessayer',
                            style:
                                TextStyle(color: AppColors.textPrimary)),
                      ),
                    ],
                  ),
                ),
                data: (all) {
                  final list = _filter == 'all'
                      ? all
                      : all.where((c) => c.tag == _filter).toList();
                  if (list.isEmpty) {
                    return Center(
                      child: Text(
                        'Aucune conversation pour ce filtre',
                        style: GoogleFonts.inter(
                          color: AppColors.textMuted,
                          fontSize: 13,
                        ),
                      ),
                    );
                  }
                  return ListView.separated(
                    padding: const EdgeInsets.fromLTRB(16, 8, 16, 110),
                    itemCount: list.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 8),
                    itemBuilder: (context, idx) {
                      final c = list[idx];
                      final tone = _tagTones[c.tag]!;
                      return BubbleIn(
                        delay: Duration(milliseconds: idx * 40),
                        child: _HistoryCard(convo: c, tone: tone),
                      );
                    },
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

class _SkeletonCard extends StatelessWidget {
  const _SkeletonCard();

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 110,
      decoration: BoxDecoration(
        color: AppColors.surface1,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.line),
      ),
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            height: 12,
            width: 80,
            color: AppColors.surface2,
          ),
          const SizedBox(height: 10),
          Container(
            height: 14,
            width: 200,
            color: AppColors.surface2,
          ),
          const SizedBox(height: 6),
          Container(
            height: 10,
            width: double.infinity,
            color: AppColors.surface2,
          ),
        ],
      ),
    );
  }
}

class _HistoryCard extends StatelessWidget {
  final _Convo convo;
  final _TagTone tone;
  const _HistoryCard({required this.convo, required this.tone});

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(14),
      child: Stack(
        children: [
          Container(
            decoration: BoxDecoration(
              color: AppColors.surface1,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(
                color: convo.urgent
                    ? const Color(0x59F43F5E)
                    : AppColors.line,
                width: 1,
              ),
            ),
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: tone.background,
                        borderRadius: BorderRadius.circular(99),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            _filterIcons[convo.tag] ??
                                Icons.label_outline_rounded,
                            size: 11,
                            color: tone.color,
                          ),
                          const SizedBox(width: 4),
                          Text(
                            convo.tag.toUpperCase(),
                            style: GoogleFonts.jetBrainsMono(
                              fontSize: 9.5,
                              fontWeight: FontWeight.w700,
                              letterSpacing: 0.8,
                              color: tone.color,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const Spacer(),
                    Text(
                      convo.date,
                      style: GoogleFonts.jetBrainsMono(
                        fontSize: 10,
                        color: AppColors.textMuted,
                        letterSpacing: 0.4,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  convo.title,
                  style: GoogleFonts.spaceGrotesk(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: AppColors.textPrimary,
                    letterSpacing: -0.07,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  convo.preview,
                  style: GoogleFonts.inter(
                    fontSize: 12,
                    color: AppColors.textSecondary,
                    height: 1.5,
                  ),
                ),
                const SizedBox(height: 10),
                Row(
                  children: [
                    Container(
                      width: 6,
                      height: 6,
                      decoration: const BoxDecoration(
                        shape: BoxShape.circle,
                        color: Color(0xFFA5B4FC),
                      ),
                    ),
                    const SizedBox(width: 4),
                    Text(
                      '${convo.sources} sources rag',
                      style: GoogleFonts.jetBrainsMono(
                        fontSize: 10,
                        color: AppColors.textMuted,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          if (convo.urgent)
            Positioned(
              left: 0,
              top: 0,
              bottom: 0,
              child: Container(
                width: 3,
                decoration: BoxDecoration(
                  color: AppColors.pulse,
                  boxShadow: [
                    BoxShadow(
                      color: AppColors.pulse.withValues(alpha: 0.5),
                      blurRadius: 12,
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}
