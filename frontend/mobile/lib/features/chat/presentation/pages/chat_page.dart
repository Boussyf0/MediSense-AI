import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_fonts.dart';
import '../../../auth/presentation/providers/auth_provider.dart';
import '../../data/models/chat_models.dart';
import '../providers/chat_provider.dart';
import '../widgets/ai_bubble.dart';
import '../widgets/chat_input_bar.dart';
import '../widgets/urgency_banner.dart';
import '../widgets/user_bubble.dart';

class ChatPage extends ConsumerStatefulWidget {
  const ChatPage({super.key});

  @override
  ConsumerState<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends ConsumerState<ChatPage> {
  final _scrollCtrl = ScrollController();

  @override
  void dispose() {
    _scrollCtrl.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollCtrl.hasClients) {
        _scrollCtrl.animateTo(
          _scrollCtrl.position.maxScrollExtent,
          duration: const Duration(milliseconds: 250),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(chatProvider);
    ref.listen<ChatState>(chatProvider, (prev, next) {
      if (next.messages.length != (prev?.messages.length ?? 0) ||
          (next.messages.isNotEmpty &&
              next.messages.last.content !=
                  (prev?.messages.isNotEmpty == true
                      ? prev!.messages.last.content
                      : null))) {
        _scrollToBottom();
      }
    });

    return Scaffold(
      backgroundColor: AppColors.surface0,
      body: Column(
        children: [
          _Header(
            onMore: () => _showMoreMenu(context),
          ),
          if (state.isUrgent && !state.isEmpty)
            UrgencyBanner(
              onCall: () {},
            ),
          Expanded(
            child: state.isEmpty
                ? _ChatEmpty(
                    firstName: ref.watch(authProvider).user?.firstName ?? '',
                    onSuggest: (q) =>
                        ref.read(chatProvider.notifier).sendMessage(q),
                  )
                : ListView.separated(
                    controller: _scrollCtrl,
                    padding: const EdgeInsets.fromLTRB(0, 14, 0, 8),
                    itemCount: state.messages.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 14),
                    itemBuilder: (_, i) {
                      final msg = state.messages[i];
                      if (msg.role == MessageRole.user) {
                        return UserBubble(content: msg.content);
                      }
                      return AIBubble(message: msg);
                    },
                  ),
          ),
          ChatInputBar(
            enabled: !state.isStreaming,
            onSend: (text) =>
                ref.read(chatProvider.notifier).sendMessage(text),
          ),
        ],
      ),
    );
  }

  void _showMoreMenu(BuildContext context) {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      useRootNavigator: true,
      builder: (ctx) => Container(
        decoration: const BoxDecoration(
          color: AppColors.surface1,
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Center(
              child: Container(
                width: 40,
                height: 4,
                margin: const EdgeInsets.only(bottom: 14),
                decoration: BoxDecoration(
                  color: AppColors.surface3,
                  borderRadius: BorderRadius.circular(99),
                ),
              ),
            ),
            ListTile(
              leading: const Icon(Icons.add_circle_outline,
                  color: AppColors.textSecondary),
              title: Text(
                'Nouvelle conversation',
                style: AppFonts.body(
                    color: AppColors.textSecondary, fontSize: 14),
              ),
              onTap: () {
                ref.read(chatProvider.notifier).newConversation();
                Navigator.pop(ctx);
              },
            ),
            ListTile(
              leading: const Icon(Icons.history_rounded,
                  color: AppColors.textSecondary),
              title: Text(
                'Historique',
                style: AppFonts.body(
                    color: AppColors.textSecondary, fontSize: 14),
              ),
              onTap: () {
                Navigator.pop(ctx);
                context.push('/home/history');
              },
            ),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Header
// ─────────────────────────────────────────────────────────────────────────────

class _Header extends StatelessWidget {
  final VoidCallback onMore;
  const _Header({required this.onMore});

  @override
  Widget build(BuildContext context) {
    final topPad = MediaQuery.of(context).padding.top;
    return ClipRect(
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
        child: Container(
          padding: EdgeInsets.only(top: topPad + 6, bottom: 12),
          decoration: const BoxDecoration(
            color: Color(0xD90A0D14),
            border: Border(
              bottom: BorderSide(color: AppColors.line),
            ),
          ),
          child: Row(
            children: [
              const SizedBox(width: 16),
              ClipOval(
                child: Image.asset(
                  'assets/branding/app_icon.png',
                  width: 36,
                  height: 36,
                  fit: BoxFit.cover,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      'Assistant IA',
                      style: AppFonts.display(
                        color: AppColors.textPrimary,
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                        letterSpacing: -0.16,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Row(
                      children: [
                        Container(
                          width: 6,
                          height: 6,
                          decoration: BoxDecoration(
                            color: AppColors.riskSafe,
                            shape: BoxShape.circle,
                            boxShadow: [
                              BoxShadow(
                                color:
                                    AppColors.riskSafe.withValues(alpha: 0.6),
                                blurRadius: 6,
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(width: 5),
                        Text(
                          'en ligne · mistral-7B',
                          style: AppFonts.mono(
                            color: AppColors.textSecondary,
                            fontSize: 10,
                            letterSpacing: 0.4,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              IconButton(
                onPressed: onMore,
                icon: const Icon(Icons.more_horiz_rounded,
                    color: AppColors.text1, size: 22),
              ),
              const SizedBox(width: 4),
            ],
          ),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Empty state
// ─────────────────────────────────────────────────────────────────────────────

class _ChatEmpty extends StatefulWidget {
  final String firstName;
  final void Function(String) onSuggest;
  const _ChatEmpty({required this.firstName, required this.onSuggest});

  @override
  State<_ChatEmpty> createState() => _ChatEmptyState();
}

class _ChatEmptyState extends State<_ChatEmpty>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2400),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          AnimatedBuilder(
            animation: _ctrl,
            builder: (_, __) {
              final t = Curves.easeInOut.transform(_ctrl.value);
              return Transform.scale(
                scale: 0.96 + 0.06 * t,
                child: Container(
                  width: 96,
                  height: 96,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: RadialGradient(
                      colors: [
                        AppColors.aiTo.withValues(alpha: 0.4),
                        AppColors.aiFrom.withValues(alpha: 0.1),
                        Colors.transparent,
                      ],
                      stops: const [0.0, 0.5, 1.0],
                    ),
                  ),
                  child: const Icon(
                    Icons.auto_awesome,
                    color: Color(0xFFC4B5FD),
                    size: 32,
                  ),
                ),
              );
            },
          ),
          const SizedBox(height: 20),
          Text(
            widget.firstName.isNotEmpty ? 'Bonjour ${widget.firstName} 👋' : 'Bonjour 👋',
            textAlign: TextAlign.center,
            style: AppFonts.display(
              color: AppColors.textPrimary,
              fontSize: 26,
              fontWeight: FontWeight.w600,
              letterSpacing: -0.26,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Décrivez vos symptômes ou posez une question médicale. Je réponds en FR, AR ou darija.',
            textAlign: TextAlign.center,
            style: AppFonts.body(
              color: AppColors.textSecondary,
              fontSize: 14,
              height: 1.5,
            ),
          ),
          const SizedBox(height: 28),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            alignment: WrapAlignment.center,
            children: [
              _SuggestChip(
                label: 'Mes symptômes',
                onTap: () => widget.onSuggest(
                  "Je sens une douleur dans la poitrine depuis 30 minutes, et j'ai du mal à respirer.",
                ),
              ),
              _SuggestChip(
                label: 'Mon traitement',
                onTap: () => widget.onSuggest(
                  'Quels effets secondaires pour le Coversyl 5mg ?',
                ),
              ),
              _SuggestChip(
                label: 'Urgence',
                onTap: () => widget.onSuggest(
                  'Mon père a une douleur thoracique aiguë, que faire ?',
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _SuggestChip extends StatelessWidget {
  final String label;
  final VoidCallback onTap;
  const _SuggestChip({required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
        decoration: BoxDecoration(
          color: const Color(0xB3111827),
          borderRadius: BorderRadius.circular(99),
          border: Border.all(
            color: AppColors.aiTo.withValues(alpha: 0.4),
          ),
          boxShadow: [
            BoxShadow(
              color: AppColors.aiFrom.withValues(alpha: 0.18),
              blurRadius: 14,
            ),
          ],
        ),
        child: Text(
          label,
          style: AppFonts.body(
            color: AppColors.textPrimary,
            fontSize: 12.5,
            fontWeight: FontWeight.w500,
          ),
        ),
      ),
    );
  }
}
