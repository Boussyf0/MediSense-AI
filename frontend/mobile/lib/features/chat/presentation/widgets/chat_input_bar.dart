import 'dart:async';

import 'package:flutter/material.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;

import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_fonts.dart';
import 'voice_bars.dart';

/// Pill-shaped input row with mic + send buttons. When recording, swaps the
/// text field for animated waveform bars + elapsed counter. Mirrors
/// `chat.jsx`'s composer row.
class ChatInputBar extends StatefulWidget {
  final void Function(String) onSend;
  final bool enabled;
  const ChatInputBar({super.key, required this.onSend, this.enabled = true});

  @override
  State<ChatInputBar> createState() => _ChatInputBarState();
}

class _ChatInputBarState extends State<ChatInputBar> {
  final _ctrl = TextEditingController();
  final _speech = stt.SpeechToText();
  bool _listening = false;
  bool _hasText = false;
  Timer? _ticker;
  int _seconds = 0;

  @override
  void initState() {
    super.initState();
    _ctrl.addListener(() {
      final hasText = _ctrl.text.trim().isNotEmpty;
      if (hasText != _hasText) setState(() => _hasText = hasText);
    });
  }

  @override
  void dispose() {
    _ticker?.cancel();
    _ctrl.dispose();
    super.dispose();
  }

  Future<void> _toggleMic() async {
    if (_listening) {
      await _speech.stop();
      _ticker?.cancel();
      setState(() => _listening = false);
      return;
    }
    final available = await _speech.initialize(
      onError: (_) => setState(() => _listening = false),
      onStatus: (s) {
        if (s == 'done' || s == 'notListening') {
          _ticker?.cancel();
          if (mounted) setState(() => _listening = false);
        }
      },
    );
    if (!available) return;
    await _speech.listen(
      onResult: (r) {
        if (r.finalResult) {
          _ctrl.text = r.recognizedWords;
          _ctrl.selection = TextSelection.fromPosition(
            TextPosition(offset: _ctrl.text.length),
          );
          _ticker?.cancel();
          setState(() => _listening = false);
        }
      },
      localeId: 'fr_MA',
    );
    _seconds = 0;
    _ticker = Timer.periodic(const Duration(seconds: 1), (_) {
      if (!mounted) return;
      setState(() => _seconds += 1);
    });
    setState(() => _listening = true);
  }

  void _send() {
    final text = _ctrl.text.trim();
    if (text.isEmpty) return;
    _ctrl.clear();
    widget.onSend(text);
  }

  @override
  Widget build(BuildContext context) {
    final canSend = _hasText && widget.enabled;
    final secs = _seconds.toString().padLeft(2, '0');

    return Container(
      decoration: const BoxDecoration(
        color: Color(0xEB0A0D14),
        border: Border(top: BorderSide(color: AppColors.line)),
      ),
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
      child: SafeArea(
        top: false,
        child: Container(
          decoration: BoxDecoration(
            color: AppColors.surface1,
            borderRadius: BorderRadius.circular(24),
            border: Border.all(color: AppColors.line),
          ),
          padding: const EdgeInsets.fromLTRB(14, 4, 4, 4),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Expanded(
                child: _listening
                    ? Padding(
                        padding: const EdgeInsets.symmetric(vertical: 8),
                        child: Row(
                          children: [
                            const VoiceBars(),
                            const SizedBox(width: 10),
                            Text(
                              'écoute · 00:$secs',
                              style: AppFonts.mono(
                                color: AppColors.textSecondary,
                                fontSize: 11,
                                letterSpacing: 0.4,
                              ),
                            ),
                          ],
                        ),
                      )
                    : TextField(
                        controller: _ctrl,
                        enabled: widget.enabled,
                        maxLines: 4,
                        minLines: 1,
                        style: AppFonts.body(
                          color: AppColors.textPrimary,
                          fontSize: 14,
                        ),
                        textInputAction: TextInputAction.send,
                        onSubmitted: widget.enabled ? (_) => _send() : null,
                        decoration: InputDecoration(
                          hintText: 'Décrivez vos symptômes…',
                          hintStyle: AppFonts.body(
                            color: AppColors.textMuted,
                            fontSize: 14,
                          ),
                          isDense: true,
                          filled: false,
                          border: InputBorder.none,
                          enabledBorder: InputBorder.none,
                          focusedBorder: InputBorder.none,
                          contentPadding:
                              const EdgeInsets.symmetric(vertical: 10),
                        ),
                      ),
              ),
              const SizedBox(width: 4),
              _IconBtn(
                icon: Icons.mic_none_rounded,
                onTap: widget.enabled ? _toggleMic : null,
                active: _listening,
              ),
              const SizedBox(width: 4),
              _IconBtn(
                icon: Icons.arrow_upward_rounded,
                onTap: canSend ? _send : null,
                active: canSend || _listening,
                inactiveColor: AppColors.surface3,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _IconBtn extends StatelessWidget {
  final IconData icon;
  final VoidCallback? onTap;
  final bool active;
  final Color inactiveColor;
  const _IconBtn({
    required this.icon,
    required this.onTap,
    this.active = false,
    this.inactiveColor = Colors.transparent,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        width: 40,
        height: 40,
        decoration: BoxDecoration(
          gradient: active ? AppColors.aiGrad : null,
          color: active ? null : inactiveColor,
          shape: BoxShape.circle,
          boxShadow: active
              ? [
                  BoxShadow(
                    color: AppColors.aiTo.withValues(alpha: 0.5),
                    blurRadius: 16,
                  ),
                ]
              : null,
        ),
        child: Icon(
          icon,
          size: 18,
          color: active ? Colors.white : AppColors.textSecondary,
        ),
      ),
    );
  }
}
