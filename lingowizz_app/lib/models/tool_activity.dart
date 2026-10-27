/// 一轮对话中 AI 调用过的工具（用于在气泡上方显示小标签）
class ToolCall {
  final String tool;
  final bool ok;

  const ToolCall({required this.tool, required this.ok});

  factory ToolCall.fromJson(Map<String, dynamic> json) => ToolCall(
        tool: json['tool'] as String? ?? '',
        ok: json['ok'] as bool? ?? false,
      );
}

/// 对话中推荐的 B 站学习视频
class RecommendedVideo {
  final String title;
  final String duration;
  final String author;
  final String url;
  final String cover;

  const RecommendedVideo({
    required this.title,
    required this.duration,
    required this.author,
    required this.url,
    required this.cover,
  });

  factory RecommendedVideo.fromJson(Map<String, dynamic> json) =>
      RecommendedVideo(
        title: json['title'] as String? ?? '',
        duration: json['duration'] as String? ?? '',
        author: json['author'] as String? ?? '',
        url: json['url'] as String? ?? '',
        cover: json['cover'] as String? ?? '',
      );
}
