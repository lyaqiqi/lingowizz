import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:sqflite/sqflite.dart' as sqflite;
import 'package:path_provider/path_provider.dart';
import '../models/video_model.dart';
import 'api_service.dart';

class VideoService {
  // 与 ApiService 使用同一个后端地址
  static String get baseUrl => ApiService.serverBaseUrl;

  static sqflite.Database? _database;

  // 初始化数据库
  static Future<sqflite.Database> get database async {
    if (_database != null) return _database!;

    final docsDir = await getApplicationDocumentsDirectory();
    final dbPath = '${docsDir.path}/video_search.db';

    _database = await sqflite.openDatabase(
      dbPath,
      version: 2,
      onCreate: (db, version) async {
        await db.execute('''
          CREATE TABLE videos (
            video_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            url TEXT,
            duration TEXT,
            tags TEXT,
            thumbnail_url TEXT,
            play_count INTEGER,
            up TEXT
          )
        ''');
      },
      onUpgrade: (db, oldVersion, newVersion) async {
        await db.execute('DROP TABLE IF EXISTS videos');
        await db.execute('''
          CREATE TABLE videos (
            video_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            url TEXT,
            duration TEXT,
            tags TEXT,
            thumbnail_url TEXT,
            play_count INTEGER,
            up TEXT
          )
        ''');
      },
    );
    return _database!;
  }

  // 从后端获取视频并存入数据库
  static Future<List<VideoModel>> fetchVideos(List<String> tags) async {
    try {
      print('请求URL: $baseUrl/api/recommend');
      print('请求参数: $tags');

      final response = await http.post(
        Uri.parse('$baseUrl/api/recommend'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({'tags': tags}),
      );

      print('响应状态码: ${response.statusCode}');
      print('响应内容: ${response.body}');

      if (response.statusCode != 200) {
        throw Exception('网络请求失败，状态码: ${response.statusCode}');
      }

      final List<dynamic> data = json.decode(response.body)['videos'];
      final videos = data.map((item) => VideoModel.fromJson(item)).toList();

      // 存入数据库
      final db = await database;
      await db.transaction((txn) async {
        for (final video in videos) {
          await txn.insert(
            'videos',
            video.toMap(),
            conflictAlgorithm: sqflite.ConflictAlgorithm.replace,
          );
        }
      });

      return videos;
    } catch (e) {
      throw Exception('获取视频失败: $e');
    }
  }

  // 从数据库读取缓存视频
  static Future<List<VideoModel>> getCachedVideos() async {
    final db = await database;
    final List<Map<String, dynamic>> maps = await db.query('videos');

    return maps.map((map) {
      return VideoModel(
        id: map['video_id'].toString(),
        title: map['title'],
        cover: map['thumbnail_url'],
        url: map['url'],
        duration: map['duration'],
        playCount: map['play_count'] ?? 0,
        up: map['up'] ?? '',
        tags: (map['tags'] ?? '').split(','),
      );
    }).toList();
  }
} 