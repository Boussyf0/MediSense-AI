import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../theme/app_colors.dart';
import '../theme/app_fonts.dart';
import '../../features/auth/presentation/providers/auth_provider.dart';
import '../../services/alert_ws_provider.dart';

class MainShell extends ConsumerStatefulWidget {
  final Widget child;
  const MainShell({super.key, required this.child});

  @override
  ConsumerState<MainShell> createState() => _MainShellState();
}

class _MainShellState extends ConsumerState<MainShell> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (ref.read(authProvider).user == null) {
        ref.read(authProvider.notifier).loadUser();
      }
      // Ensure the alerts provider is initialised (auto-connects via auth).
      ref.read(alertsProvider);
    });
  }

  @override
  Widget build(BuildContext context) {
    final location = GoRouterState.of(context).matchedLocation;
    final routes = ['/home', '/appointments', '/iot', '/profile'];
    final idx = routes.indexWhere((r) => location.startsWith(r));
    final current = idx < 0 ? 0 : idx;

    final toast = ref.watch(alertsProvider).toast;

    return Scaffold(
      backgroundColor: AppColors.surface0,
      extendBody: true,
      body: Stack(
        children: [
          widget.child,
          // Real-time anomaly alert toast overlay
          if (toast != null)
            _AnomalyToast(
              payload: toast,
              onDismiss: () =>
                  ref.read(alertsProvider.notifier).dismissToast(),
            ),
        ],
      ),
      bottomNavigationBar: _CustomTabBar(
        current: current,
        onTap: (i) => context.go(routes[i]),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Anomaly alert toast — slides in from top, glassmorphic, narrative-first
// ─────────────────────────────────────────────────────────────────────────────

class _AnomalyToast extends StatefulWidget {
  final AlertPayload payload;
  final VoidCallback onDismiss;
  const _AnomalyToast({required this.payload, required this.onDismiss});

  @override
  State<_AnomalyToast> createState() => _AnomalyToastState();
}

class _AnomalyToastState extends State<_AnomalyToast>
    with SingleTickerProviderStateMixin {
  late final AnimationController _anim;
  late final Animation<Offset> _slide;
  late final Animation<double> _fade;

  @override
  void initState() {
    super.initState();
    _anim = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 400),
    );
    _slide = Tween<Offset>(
      begin: const Offset(0, -1.2),
      end: Offset.zero,
    ).animate(CurvedAnimation(parent: _anim, curve: Curves.easeOutCubic));
    _fade = Tween<double>(begin: 0, end: 1).animate(
      CurvedAnimation(parent: _anim, curve: const Interval(0, 0.6)),
    );
    _anim.forward();
  }

  @override
  void dispose() {
    _anim.dispose();
    super.dispose();
  }

  void _dismiss() async {
    await _anim.reverse();
    widget.onDismiss();
  }

  String _fmtTime(DateTime dt) {
    final h = dt.hour.toString().padLeft(2, '0');
    final m = dt.minute.toString().padLeft(2, '0');
    return '$h:$m';
  }

  @override
  Widget build(BuildContext context) {
    final p = widget.payload;
    final top = MediaQuery.of(context).padding.top;

    return Positioned(
      top: top + 8,
      left: 12,
      right: 12,
      child: SlideTransition(
        position: _slide,
        child: FadeTransition(
          opacity: _fade,
          child: GestureDetector(
            onVerticalDragEnd: (d) {
              if (d.primaryVelocity != null && d.primaryVelocity! < -100) {
                _dismiss();
              }
            },
            child: ClipRRect(
              borderRadius: BorderRadius.circular(16),
              child: BackdropFilter(
                filter: ImageFilter.blur(sigmaX: 20, sigmaY: 20),
                child: Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: const Color(0xDD1F1730),
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(
                      color: AppColors.pulse.withValues(alpha: 0.5),
                    ),
                    boxShadow: [
                      BoxShadow(
                        color: AppColors.pulse.withValues(alpha: 0.15),
                        blurRadius: 24,
                        offset: const Offset(0, 8),
                      ),
                      const BoxShadow(
                        color: Color(0x66000000),
                        blurRadius: 32,
                        offset: Offset(0, 12),
                      ),
                    ],
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      // Header row: badge + time + dismiss
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 3,
                            ),
                            decoration: BoxDecoration(
                              color: AppColors.pulse.withValues(alpha: 0.2),
                              borderRadius: BorderRadius.circular(99),
                              border: Border.all(
                                color: AppColors.pulse.withValues(alpha: 0.5),
                              ),
                            ),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Container(
                                  width: 6,
                                  height: 6,
                                  decoration: BoxDecoration(
                                    color: AppColors.pulse,
                                    shape: BoxShape.circle,
                                    boxShadow: [
                                      BoxShadow(
                                        color: AppColors.pulse
                                            .withValues(alpha: 0.8),
                                        blurRadius: 4,
                                      ),
                                    ],
                                  ),
                                ),
                                const SizedBox(width: 6),
                                Text(
                                  'CRITIQUE',
                                  style: AppFonts.mono(
                                    color: AppColors.pulse,
                                    fontSize: 9,
                                    fontWeight: FontWeight.w700,
                                    letterSpacing: 1.6,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(width: 8),
                          Text(
                            _fmtTime(p.receivedAt),
                            style: AppFonts.mono(
                              color: AppColors.textMuted,
                              fontSize: 10,
                            ),
                          ),
                          const Spacer(),
                          GestureDetector(
                            onTap: _dismiss,
                            behavior: HitTestBehavior.opaque,
                            child: Padding(
                              padding: const EdgeInsets.all(4),
                              child: Icon(
                                Icons.close_rounded,
                                size: 18,
                                color: AppColors.textMuted
                                    .withValues(alpha: 0.7),
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 10),
                      // Narrative headline
                      Text(
                        p.narrative ?? 'Anomalie détectée',
                        style: AppFonts.body(
                          color: AppColors.textPrimary,
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                          height: 1.35,
                        ),
                        maxLines: 3,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 8),
                      // Subline: patient + raw vitals
                      Row(
                        children: [
                          if (p.patientUuid != null) ...[
                            Text(
                              'Patient ${p.patientUuid!.substring(0, 8)}…',
                              style: AppFonts.mono(
                                color: AppColors.textFaint,
                                fontSize: 10,
                              ),
                            ),
                            const SizedBox(width: 8),
                          ],
                          if (p.hr != null)
                            _VitalChip(
                              icon: Icons.favorite_rounded,
                              value: '${p.hr!.round()}',
                              unit: 'bpm',
                              color: AppColors.pulse,
                            ),
                          if (p.spo2 != null) ...[
                            const SizedBox(width: 6),
                            _VitalChip(
                              icon: Icons.air_rounded,
                              value: '${p.spo2!.round()}',
                              unit: '%',
                              color: AppColors.oxy,
                            ),
                          ],
                          if (p.score5m != null) ...[
                            const Spacer(),
                            Text(
                              'score ${p.score5m!.toStringAsFixed(2)}',
                              style: AppFonts.mono(
                                color: AppColors.textFaint,
                                fontSize: 10,
                              ),
                            ),
                          ],
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Compact vital chip for the alert toast subline.
class _VitalChip extends StatelessWidget {
  final IconData icon;
  final String value;
  final String unit;
  final Color color;
  const _VitalChip({
    required this.icon,
    required this.value,
    required this.unit,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(99),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 10, color: color),
          const SizedBox(width: 3),
          Text(
            '$value$unit',
            style: AppFonts.mono(
              color: color,
              fontSize: 9.5,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}

class _TabSpec {
  final String label;
  final IconData icon;
  final IconData activeIcon;
  const _TabSpec(this.label, this.icon, this.activeIcon);
}

const _tabs = [
  _TabSpec('ASSISTANT', Icons.chat_bubble_outline_rounded, Icons.chat_bubble_rounded),
  _TabSpec('AGENDA', Icons.calendar_month_outlined, Icons.calendar_month_rounded),
  _TabSpec('BIOMÉTRIE', Icons.monitor_heart_outlined, Icons.monitor_heart),
  _TabSpec('PROFIL', Icons.person_outline_rounded, Icons.person_rounded),
];

class _CustomTabBar extends StatelessWidget {
  final int current;
  final void Function(int) onTap;
  const _CustomTabBar({required this.current, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return ClipRect(
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 14, sigmaY: 14),
        child: Container(
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [Colors.transparent, Color(0xEB0A0D14)],
              stops: [0.0, 0.35],
            ),
            border: Border(
              top: BorderSide(color: Color(0x1494A3B8)),
            ),
          ),
          child: SafeArea(
            top: false,
            child: Padding(
              padding: const EdgeInsets.only(top: 10, bottom: 6, left: 8, right: 8),
              child: Row(
                children: List.generate(_tabs.length, (i) {
                  final tab = _tabs[i];
                  final isActive = i == current;
                  return Expanded(
                    child: GestureDetector(
                      onTap: () => onTap(i),
                      behavior: HitTestBehavior.opaque,
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          // Gradient indicator bar at top
                          Center(
                            child: AnimatedContainer(
                              duration: const Duration(milliseconds: 200),
                              height: 3,
                              width: isActive ? 28 : 0,
                              decoration: isActive
                                  ? BoxDecoration(
                                      gradient: AppColors.aiGrad,
                                      borderRadius: BorderRadius.circular(99),
                                      boxShadow: [
                                        BoxShadow(
                                          color: const Color(0xFF8B5CF6)
                                              .withValues(alpha: 0.6),
                                          blurRadius: 12,
                                        ),
                                      ],
                                    )
                                  : const BoxDecoration(),
                            ),
                          ),
                          const SizedBox(height: 6),
                          Icon(
                            isActive ? tab.activeIcon : tab.icon,
                            size: 22,
                            color: isActive
                                ? AppColors.textPrimary
                                : const Color(0xFF64748B),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            tab.label,
                            style: TextStyle(
                              fontSize: 9,
                              letterSpacing: 0.9,
                              color: isActive
                                  ? AppColors.textPrimary
                                  : const Color(0xFF64748B),
                              fontWeight: isActive
                                  ? FontWeight.w600
                                  : FontWeight.w500,
                            ),
                          ),
                        ],
                      ),
                    ),
                  );
                }),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
