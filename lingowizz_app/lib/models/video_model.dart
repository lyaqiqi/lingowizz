class VideoModel {
  final String id;          // 对应数据库的 video_id
  final String title;
  final String cover;       // 对应数据库的 thumbnail_url
  final String url;
  
  final String duration;
  final int playCount;      // 对应数据库的 play_count
  final String up;
  final List<String> tags;

  VideoModel({
    required this.id,
    required this.title,
    required this.cover,
    required this.url,
    required this.duration,
    required this.playCount,
    required this.up,
    required this.tags,
  });

  // 转 Map，用于数据库存储（字段名与数据库表匹配）
  Map<String, dynamic> toMap() {
    return {      
      'title': title,
      'thumbnail_url': cover,      // 对应数据库的 thumbnail_url 字段
      'url': url,
      'duration': duration,
      'play_count': playCount,     // 数据库字段使用下划线命名
      'up': up,
      'tags': tags.join(','),      // 标签转字符串存储
    };
  }

  // 从数据库 Map 解析（字段名与数据库表匹配）
  factory VideoModel.fromMap(Map<String, dynamic> map) {
    return VideoModel(
      id: map['video_id'].toString(),  // 数据库 id 转为字符串
      title: map['title'] ?? '',
      cover: map['thumbnail_url'] ?? '',  // 从 thumbnail_url 读取封面
      url: map['url'] ?? '',
      duration: map['duration'] ?? '',
      playCount: map['play_count'] ?? 0, // 从 play_count 读取播放量
      up: map['up'] ?? '',
      tags: (map['tags'] ?? '').split(','), // 字符串转标签列表
    );
  }

  // 从后端 JSON 解析（字段名与后端返回匹配）
  factory VideoModel.fromJson(Map<String, dynamic> json) {
    return VideoModel(
      id: json['id'] ?? '',
      title: json['title'] ?? '',
      cover: json['cover'] ?? '',
      url: json['url'] ?? '',
      duration: json['duration'] ?? '',
      playCount: json['play_count'] is int
          ? json['play_count']
          : int.tryParse(json['play_count']?.toString() ?? '0') ?? 0,
      up: json['up'] ?? '',
      tags: (json['tags'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? [],
    );
  }
} 