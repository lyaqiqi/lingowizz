import 'dart:convert';
import 'dart:developer';
import 'dart:io';
import 'package:http/http.dart' as http;
import '../models/vocabulary_item.dart';
import '../models/conversation.dart';

class ApiService {
  // 后端地址：默认连接本机后端（Android 模拟器中 10.0.2.2 即电脑本机）
  // 使用线上服务时编译加参数：--dart-define=API_BASE_URL=https://lingowizz-backend-3qbi.onrender.com/api
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:5000/api',
  );
  static String get serverBaseUrl => baseUrl.replaceAll('/api', '');

  // HTTP客户端配置
  final http.Client _client = http.Client();

  // 通用请求头
  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      };

  // 图片上传
  Future<Map<String, dynamic>> uploadImage(File imageFile) async {
    try {
      var request =
          http.MultipartRequest('POST', Uri.parse('$baseUrl/upload-image'));
      request.files
          .add(await http.MultipartFile.fromPath('image', imageFile.path));

      var response = await request.send();
      var responseData = await response.stream.bytesToString();

      if (response.statusCode == 200) {
        return json.decode(responseData);
      } else {
        throw Exception('图片上传失败: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('图片上传错误: $e');
    }
  }

  // 物品识别和分割
  Future<Map<String, dynamic>> segmentObjects(String imagePath) async {
    try {
      final response = await _client.post(
        Uri.parse('$baseUrl/segment-objects'),
        headers: _headers,
        body: json.encode({'image_path': imagePath}),
      );

      if (response.statusCode == 200) {
        return json.decode(response.body);
      } else {
        throw Exception('物品识别失败: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('物品识别错误: $e');
    }
  }

  // 生成单词信息
  Future<Map<String, dynamic>> generateWordInfo(String word) async {
    try {
      final response = await _client.post(
        Uri.parse('$baseUrl/generate-word-info'),
        headers: _headers,
        body: json.encode({'word': word}),
      );

      if (response.statusCode == 200) {
        return json.decode(response.body);
      } else {
        throw Exception('单词信息生成失败: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('单词信息生成错误: $e');
    }
  }

  // 图片理解
  Future<Map<String, dynamic>> understandImage(String imagePath) async {
    try {
      final response = await _client.post(
        Uri.parse('$baseUrl/understand-image'),
        headers: _headers,
        body: json.encode({'image_path': imagePath}),
      );

      if (response.statusCode == 200) {
        return json.decode(response.body);
      } else {
        throw Exception('图片理解失败: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('图片理解错误: $e');
    }
  }

  // 生成对话主题
  Future<List<ConversationTheme>> generateConversationThemes(
      Map<String, dynamic> understanding) async {
    try {
      final response = await _client.post(
        Uri.parse('$baseUrl/generate-conversation-themes'),
        headers: _headers,
        body: json.encode({'understanding': understanding}),
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        final themes = (data['themes'] as List)
            .map((theme) => ConversationTheme.fromJson(theme))
            .toList();
        return themes;
      } else {
        throw Exception('对话主题生成失败: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('对话主题生成错误: $e');
    }
  }

  // 单词本相关API

  // 获取单词本
  Future<List<VocabularyItem>> getVocabulary(
      {int page = 1, int perPage = 20}) async {
    try {
      final response = await _client.get(
        Uri.parse('$baseUrl/vocabulary?page=$page&per_page=$perPage'),
        headers: _headers,
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        final vocabulary = (data['vocabulary'] as List)
            .map((item) => VocabularyItem.fromJson(item))
            .toList();
        return vocabulary;
      } else {
        throw Exception('获取单词本失败: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('获取单词本错误: $e');
    }
  }

  // 添加单词到单词本
  Future<VocabularyItem> addVocabulary(VocabularyItem item) async {
    try {
      final response = await _client.post(
        Uri.parse('$baseUrl/vocabulary'),
        headers: _headers,
        body: json.encode(item.toJson()),
      );

      if (response.statusCode == 201) {
        final data = json.decode(response.body);
        return VocabularyItem.fromJson(data['vocabulary_item']);
      } else {
        throw Exception('添加单词失败: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('添加单词错误: $e');
    }
  }

  // 搜索单词
  Future<List<VocabularyItem>> searchVocabulary(String query) async {
    try {
      final response = await _client.get(
        Uri.parse('$baseUrl/vocabulary/search?q=$query'),
        headers: _headers,
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        final vocabulary = (data['vocabulary'] as List)
            .map((item) => VocabularyItem.fromJson(item))
            .toList();
        return vocabulary;
      } else {
        throw Exception('搜索单词失败: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('搜索单词错误: $e');
    }
  }

  // 对话相关API
  ///
  // 创建对话会话
  /*
  Future<ConversationSession> createConversationSession(ConversationTheme theme, String? imagePath) async {
    try {
      final response = await _client.post(
        Uri.parse('$baseUrl/conversation/sessions'),
        headers: _headers,
        body: json.encode({
          'theme': theme.title,
          'background': theme.background,
          'role': theme.role,
          'image_path': imagePath,
        }),
      );
      
      if (response.statusCode == 201) {
        final data = json.decode(response.body);
        return ConversationSession.fromJson(data['session']);
      } else {
        throw Exception('创建对话会话失败: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('创建对话会话错误: $e');
    }
  }
  */
// lib/services/api_service.dart

// ...

// 创建对话会话
  Future<ConversationSession> createConversationSession(
      ConversationTheme theme, String? imagePath) async {
    try {
      final response = await _client.post(
        // *** 确认这里的 URL 是正确的。你的路由文件没有'conversation'前缀 ***
        // 蓝图是 conversation_bp，但没有指定路径前缀，所以应该是 /api/sessions，wrong
        Uri.parse('$baseUrl/sessions'),
        headers: _headers,
        body: json.encode({
          // *** 修改这里：将整个 theme 对象作为 theme 键的值 ***
          'theme': {
            'id': theme.id, // 最好把 id 也传过去
            'title': theme.title,
            'description': theme.description,
            'role': theme.role,
            'background': theme.background,
            'scenario': theme.scenario,
          },
          'image_path': imagePath,
        }),
      );

      // 现在后端返回 201，这里就匹配了
      if (response.statusCode == 201) {
        final data = json.decode(response.body);
        return ConversationSession.fromJson(data['session']);
      } else {
        // 打印响应体以帮助调试
        log('Error body: ${response.body}');
        throw Exception('创建对话会话失败: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('创建对话会话错误: $e');
    }
  }

  // 发送消息
  Future<Map<String, dynamic>> sendMessage(
      String sessionId, String message) async {
    try {
      final response = await _client.post(
        Uri.parse('$baseUrl/sessions/$sessionId/messages'),
        headers: _headers,
        body: json.encode({'message': message}),
      );

      if (response.statusCode == 200) {
        return json.decode(response.body);
      } else {
        throw Exception('发送消息失败: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('发送消息错误: $e');
    }
  }

  // 获取对话消息
  Future<List<ConversationMessage>> getConversationMessages(
      String sessionId) async {
    try {
      final response = await _client.get(
        Uri.parse('$baseUrl/sessions/$sessionId/messages'),
        headers: _headers,
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        final messages = (data['messages'] as List)
            .map((message) => ConversationMessage.fromJson(message))
            .toList();
        return messages;
      } else {
        throw Exception('获取对话消息失败: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('获取对话消息错误: $e');
    }
  }

  // 获取对话会话列表
  Future<List<ConversationSession>> getConversationSessions() async {
    try {
      final response = await _client.get(
        Uri.parse('$baseUrl/sessions'),
        headers: _headers,
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        final sessions = (data['sessions'] as List)
            .map((session) => ConversationSession.fromJson(session))
            .toList();
        return sessions;
      } else {
        throw Exception('获取对话会话失败: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('获取对话会话错误: $e');
    }
  }

  void dispose() {
    _client.close();
  }
}
