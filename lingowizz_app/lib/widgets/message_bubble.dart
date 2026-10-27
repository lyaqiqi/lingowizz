import 'package:flutter/material.dart';
import '../models/conversation.dart';
import '../models/tool_activity.dart';
import '../utils/app_theme.dart';
import 'video_suggestion_card.dart';

class MessageBubble extends StatelessWidget {
  final ConversationMessage message;
  final bool isUser;
  // AI 回复时调用过的工具和推荐的视频（仅本次会话中新收到的回复会有）
  final List<ToolCall> toolCalls;
  final List<RecommendedVideo> videos;

  const MessageBubble({
    super.key,
    required this.message,
    required this.isUser,
    this.toolCalls = const [],
    this.videos = const [],
  });

  static const Map<String, (IconData, String)> _toolLabels = {
    'look_at_image': (Icons.photo_camera, 'Looked at photo'),
    'detect_objects': (Icons.center_focus_strong, 'Found objects'),
    'explain_word': (Icons.menu_book, 'Looked up word'),
    'save_to_vocabulary': (Icons.bookmark_added, 'Saved to vocabulary'),
    'get_learner_profile': (Icons.insights, 'Checked progress'),
    'ask_quiz': (Icons.quiz, 'Quiz'),
    'record_answer': (Icons.task_alt, 'Answer recorded'),
    'recommend_videos': (Icons.smart_display, 'Found videos'),
  };

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      child: Row(
        mainAxisAlignment:
            isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (!isUser) ...[
            // AI Avatar
            Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                color: AppTheme.primaryColor,
                borderRadius: BorderRadius.circular(16),
              ),
              child: const Icon(
                Icons.smart_toy,
                color: Colors.white,
                size: 18,
              ),
            ),
            const SizedBox(width: 8),
          ],

          // Message content
          Flexible(
            child: Column(
              crossAxisAlignment:
                  isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
              children: [
                if (toolCalls.isNotEmpty) _buildToolChips(),
                Container(
                  constraints: BoxConstraints(
                    maxWidth: MediaQuery.of(context).size.width * 0.75,
                  ),
                  padding:
                      const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  decoration: BoxDecoration(
                    color: isUser ? AppTheme.primaryColor : Colors.grey[100],
                    borderRadius: BorderRadius.only(
                      topLeft: const Radius.circular(16),
                      topRight: const Radius.circular(16),
                      bottomLeft: Radius.circular(isUser ? 16 : 4),
                      bottomRight: Radius.circular(isUser ? 4 : 16),
                    ),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        message.message,
                        style: TextStyle(
                          fontSize: 16,
                          color:
                              isUser ? Colors.white : AppTheme.textPrimaryColor,
                          height: 1.4,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        _formatTime(message.timestamp),
                        style: TextStyle(
                          fontSize: 12,
                          color:
                              isUser ? Colors.white70 : AppTheme.textLightColor,
                        ),
                      ),
                    ],
                  ),
                ),
                ...videos.map((video) => VideoSuggestionCard(video: video)),
              ],
            ),
          ),

          if (isUser) ...[
            const SizedBox(width: 8),
            // User Avatar
            Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                color: AppTheme.secondaryColor,
                borderRadius: BorderRadius.circular(16),
              ),
              child: const Icon(
                Icons.person,
                color: Colors.white,
                size: 18,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildToolChips() {
    // 同一个工具在一轮里调用多次时只显示一次
    final seen = <String>{};
    final unique = toolCalls.where((c) => seen.add(c.tool)).toList();
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Wrap(
        spacing: 6,
        runSpacing: 6,
        children: unique.map((call) {
          final (icon, label) =
              _toolLabels[call.tool] ?? (Icons.build, call.tool);
          final color =
              call.ok ? AppTheme.primaryColor : AppTheme.textLightColor;
          return Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(call.ok ? icon : Icons.error_outline,
                    size: 14, color: color),
                const SizedBox(width: 4),
                Text(
                  label,
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: color,
                  ),
                ),
              ],
            ),
          );
        }).toList(),
      ),
    );
  }

  String _formatTime(DateTime? timestamp) {
    if (timestamp == null) return '';

    final now = DateTime.now();
    final difference = now.difference(timestamp);

    if (difference.inMinutes < 1) {
      return 'Just now';
    } else if (difference.inHours < 1) {
      return '${difference.inMinutes}m ago';
    } else if (difference.inDays < 1) {
      return '${difference.inHours}h ago';
    } else {
      return '${timestamp.hour.toString().padLeft(2, '0')}:${timestamp.minute.toString().padLeft(2, '0')}';
    }
  }
}
