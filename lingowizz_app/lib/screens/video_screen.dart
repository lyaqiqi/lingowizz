import 'package:flutter/material.dart';
import '../models/video_model.dart';
import '../services/video_service.dart';
import '../utils/app_theme.dart';
import '../widgets/video_list.dart';

class VideoScreen extends StatefulWidget {
  const VideoScreen({super.key});

  @override
  State<VideoScreen> createState() => _VideoScreenState();
}

class _VideoScreenState extends State<VideoScreen> {
  final TextEditingController _tagController = TextEditingController();
  List<VideoModel> _videos = [];
  bool _isLoading = false;

  // 搜索视频（优先查缓存，再查网络）
  Future<void> _searchVideos() async {
    setState(() {
      _isLoading = true;
    });

    try {
      final tags = _tagController.text.split(',').map((t) => t.trim()).toList();
      // 先查数据库缓存
      final cachedVideos = await VideoService.getCachedVideos();
      if (cachedVideos.isNotEmpty) {
        setState(() {
          _videos = cachedVideos;
          _isLoading = false;
        });
        return; // 有缓存则直接返回
      }

      // 缓存为空，查网络
      final result = await VideoService.fetchVideos(tags);
      setState(() {
        _videos = result;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _isLoading = false;
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('加载失败: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          '视频搜索',
          style: TextStyle(
            color: AppTheme.textPrimaryColor,
            fontWeight: FontWeight.bold,
          ),
        ),
        backgroundColor: Colors.white,
        elevation: 0,
        iconTheme: const IconThemeData(color: AppTheme.textPrimaryColor),
        actions: [
          IconButton(
            icon: const Icon(Icons.search),
            onPressed: () {
              showSearch(
                context: context,
                delegate: TagSearchDelegate(_searchVideos),
              );
            },
          ),
        ],
      ),
      body: Container(
        color: Colors.white,
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            children: [
              // 搜索栏
              Container(
                decoration: BoxDecoration(
                  color: AppTheme.primaryColor.withValues(alpha: 0.05),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: TextField(
                  controller: _tagController,
                  decoration: InputDecoration(
                    hintText: '输入标签（如 sports, run）',
                    hintStyle: const TextStyle(color: AppTheme.textSecondaryColor),
                    border: InputBorder.none,
                    contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    suffixIcon: IconButton(
                      icon: const Icon(Icons.clear, color: AppTheme.textSecondaryColor),
                      onPressed: () => _tagController.clear(),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 12),
              // 搜索按钮
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: _isLoading ? null : _searchVideos,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.primaryColor,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  child: _isLoading
                      ? const SizedBox(
                          height: 20,
                          width: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                          ),
                        )
                      : const Text(
                          '搜索视频',
                          style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                        ),
                ),
              ),
              const SizedBox(height: 20),
              // 视频列表
              Expanded(
                child: _videos.isEmpty
                    ? Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(
                              Icons.video_library_outlined,
                              size: 80,
                              color: AppTheme.textLightColor,
                            ),
                            const SizedBox(height: 16),
                            Text(
                              '请输入标签搜索视频',
                              style: TextStyle(
                                fontSize: 16,
                                color: AppTheme.textSecondaryColor,
                              ),
                            ),
                          ],
                        ),
                      )
                    : VideoList(videos: _videos),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// 搜索代理（简化版，可扩展历史记录）
class TagSearchDelegate extends SearchDelegate<String> {
  final Function() onSearch;

  TagSearchDelegate(this.onSearch);

  @override
  List<Widget>? buildActions(BuildContext context) {
    return [
      IconButton(
        icon: const Icon(Icons.clear),
        onPressed: () => query = '',
      )
    ];
  }

  @override
  Widget? buildLeading(BuildContext context) {
    return IconButton(
      icon: const Icon(Icons.arrow_back),
      onPressed: () => close(context, ''),
    );
  }

  @override
  Widget buildResults(BuildContext context) {
    close(context, query); // 关闭搜索页，执行搜索
    onSearch(); // 触发主界面的搜索逻辑
    return const SizedBox();
  }

  @override
  Widget buildSuggestions(BuildContext context) {
    // 可扩展：显示热门标签、历史记录
    return const SizedBox();
  }
} 