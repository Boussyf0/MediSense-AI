import 'package:flutter/material.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_fonts.dart';
import '../../../../core/widgets/anim/bubble_in.dart';
import '../../../../core/widgets/anim/border_travel.dart';
import '../../data/models/chat_models.dart';
import 'sources_bottom_sheet.dart';

/// AI chat bubble — left edge gradient (animated when streaming),
/// top-left asymmetric radius, meta row (lang, confidence, sources).
/// Mirrors `chat.jsx > AIBubble`.
class AIBubble extends StatefulWidget {
  final ChatMessage message;
  const AIBubble({super.key, required this.message});

  @override
  State<AIBubble> createState() => _AIBubbleState();
}

class _AIBubbleState extends State<AIBubble>
    with SingleTickerProviderStateMixin {
  late final AnimationController _cursorCtrl;

  @override
  void initState() {
    super.initState();
    _cursorCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1000),
    )..repeat();
  }

  @override
  void dispose() {
    _cursorCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final msg = widget.message;
    final hasSources = msg.sources?.isNotEmpty ?? false;

    final bubble = Stack(
      children: [
        // Bubble body
        Container(
          margin: const EdgeInsets.only(left: 16, right: 56),
          padding: const EdgeInsets.fromLTRB(17, 12, 14, 12),
          decoration: const BoxDecoration(
            color: AppColors.surface1,
            borderRadius: BorderRadius.only(
              topLeft: Radius.circular(4),
              topRight: Radius.circular(16),
              bottomLeft: Radius.circular(16),
              bottomRight: Radius.circular(16),
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              if (msg.content.isNotEmpty || msg.isStreaming)
                Text.rich(
                  TextSpan(
                    children: [
                      TextSpan(
                        text: msg.content,
                        style: AppFonts.body(
                          color: AppColors.textPrimary,
                          fontSize: 14,
                          height: 1.55,
                        ),
                      ),
                      if (msg.isStreaming)
                        WidgetSpan(
                          alignment: PlaceholderAlignment.middle,
                          child: AnimatedBuilder(
                            animation: _cursorCtrl,
                            builder: (_, __) => Opacity(
                              opacity: _cursorCtrl.value < 0.5 ? 1 : 0,
                              child: Container(
                                margin: const EdgeInsets.only(left: 2),
                                width: 8,
                                height: 16,
                                color: AppColors.aiTo,
                              ),
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              if (!msg.isStreaming && msg.content.isNotEmpty) ...[
                const SizedBox(height: 8),
                _MetaRow(message: msg, hasSources: hasSources),
              ],
            ],
          ),
        ),
        // Left gradient bar (top-left bubble border)
        Positioned(
          left: 16,
          top: 0,
          bottom: 0,
          child: ClipRRect(
            borderRadius: const BorderRadius.only(
              topLeft: Radius.circular(4),
              bottomLeft: Radius.circular(16),
            ),
            child: SizedBox(
              width: 3,
              child: Stack(
                children: [
                  const Positioned.fill(
                    child: DecoratedBox(
                      decoration: BoxDecoration(gradient: AppColors.aiGrad),
                    ),
                  ),
                  if (msg.isStreaming)
                    const Positioned.fill(
                      child: BorderTravel(
                        active: true,
                        radius: 2,
                        child: SizedBox.expand(),
                      ),
                    ),
                ],
              ),
            ),
          ),
        ),
      ],
    );

    return BubbleIn(
      duration: const Duration(milliseconds: 250),
      child: Padding(
        padding: const EdgeInsets.only(bottom: 4),
        child: bubble,
      ),
    );
  }
}

class _MetaRow extends StatelessWidget {
  final ChatMessage message;
  final bool hasSources;
  const _MetaRow({required this.message, required this.hasSources});

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 6,
      runSpacing: 6,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        if (message.language != null)
          _MetaPill(child: Text(
            message.language!.toUpperCase(),
            style: AppFonts.mono(
              color: AppColors.text1,
              fontSize: 10,
              letterSpacing: 0.4,
            ),
          )),
        if (message.confidence != null)
          _MetaPill(child: _ConfidenceBar(value: message.confidence!)),
        if (hasSources)
          _MetaPill(
            glow: true,
            onTap: () =>
                SourcesBottomSheet.show(context, message.sources!),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.link_rounded,
                    size: 11, color: AppColors.text1),
                const SizedBox(width: 3),
                Text(
                  'rag · ${message.sources!.length} sources',
                  style: AppFonts.mono(
                    color: AppColors.text1,
                    fontSize: 10,
                    letterSpacing: 0.4,
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }
}

class _MetaPill extends StatelessWidget {
  final Widget child;
  final VoidCallback? onTap;
  final bool glow;
  const _MetaPill({required this.child, this.onTap, this.glow = false});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
        decoration: BoxDecoration(
          color: const Color(0xD91C2333),
          borderRadius: BorderRadius.circular(99),
          border: Border.all(color: AppColors.line),
          boxShadow: glow
              ? [
                  BoxShadow(
                    color: AppColors.aiTo.withValues(alpha: 0.25),
                    blurRadius: 12,
                  ),
                ]
              : null,
        ),
        child: child,
      ),
    );
  }
}

class _ConfidenceBar extends StatelessWidget {
  final double value;
  const _ConfidenceBar({required this.value});

  @override
  Widget build(BuildContext context) {
    final pct = (value * 100).round();
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(99),
          child: SizedBox(
            width: 36,
            height: 4,
            child: Stack(
              children: [
                Container(color: const Color(0x2E94A3B8)),
                FractionallySizedBox(
                  alignment: Alignment.centerLeft,
                  widthFactor: value.clamp(0.0, 1.0),
                  child: Container(
                    decoration: const BoxDecoration(gradient: AppColors.aiGrad),
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(width: 6),
        Text(
          '$pct%',
          style: AppFonts.mono(
            color: AppColors.text1,
            fontSize: 10,
            letterSpacing: 0.4,
          ),
        ),
      ],
    );
  }
}
