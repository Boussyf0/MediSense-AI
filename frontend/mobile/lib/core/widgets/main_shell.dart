import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../theme/app_colors.dart';
import '../../features/auth/presentation/providers/auth_provider.dart';

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
    });
  }

  @override
  Widget build(BuildContext context) {
    final location = GoRouterState.of(context).matchedLocation;
    final routes = ['/home', '/appointments', '/iot', '/profile'];
    final idx = routes.indexWhere((r) => location.startsWith(r));
    final current = idx < 0 ? 0 : idx;

    return Scaffold(
      backgroundColor: AppColors.surface0,
      extendBody: true,
      body: widget.child,
      bottomNavigationBar: _CustomTabBar(
        current: current,
        onTap: (i) => context.go(routes[i]),
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
