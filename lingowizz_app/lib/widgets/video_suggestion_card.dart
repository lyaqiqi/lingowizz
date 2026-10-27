import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../models/tool_activity.dart';
import '../utils/app_theme.dart';

/// 对话中推荐的学习视频：封面 + 标题 + 时长，点击用浏览器 / B 站 App 打开
class VideoSuggestionCard extends StatelessWidget {
  final RecommendedVideo video;

  const VideoSuggestionCard({super.key, required this.video});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(top: 8),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => _open(context),
        child: Padding(
          padding: const EdgeInsets.all(8),
          child: Row(
            children: [
              ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: SizedBox(
                  width: 96,
                  height: 60,
                  child: Stack(
                    fit: StackFit.expand,
                    children: [
                      Image.network(
                        video.cover,
                        fit: BoxFit.cover,
                        errorBuilder: (context, error, stackTrace) => Container(
                          color: AppTheme.primaryColor.withValues(alpha: 0.1),
                          child: const Icon(Icons.video_library,
                              color: AppTheme.primaryColor),
                        ),
                      ),
                      const Center(
                        child: Icon(Icons.play_circle_fill,
                            color: Colors.white70, size: 28),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      video.title,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.textPrimaryColor,
                        height: 1.3,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      [video.duration, video.author]
                          .where((s) => s.isNotEmpty)
                          .join(' · '),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontSize: 11,
                        color: AppTheme.textLightColor,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _open(BuildContext context) async {
    final uri = Uri.tryParse(video.url);
    final opened = uri != null &&
        await launchUrl(uri, mode: LaunchMode.externalApplication);
    if (!opened && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Could not open the video')),
      );
    }
  }
}
