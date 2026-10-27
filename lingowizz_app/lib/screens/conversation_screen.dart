import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:image_picker/image_picker.dart';
import 'dart:io';
import '../services/api_service.dart';
import '../models/conversation.dart';
import '../models/tool_activity.dart';
import '../utils/app_theme.dart';
import '../widgets/message_bubble.dart';
import 'conversation_themes_screen.dart';

class ConversationScreen extends StatefulWidget {
  final ConversationSession? session;
  // 进入会话后自动发送的第一条消息（如 Practice Quiz 的 "Quiz me"）
  final String? initialMessage;

  const ConversationScreen({super.key, this.session, this.initialMessage});

  @override
  State<ConversationScreen> createState() => _ConversationScreenState();
}

class _ConversationScreenState extends State<ConversationScreen> {
  final TextEditingController _messageController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final ImagePicker _picker = ImagePicker();

  List<ConversationMessage> _messages = [];
  ConversationSession? _currentSession;
  bool _isLoading = false;
  bool _isSending = false;
  // AI 回复的消息 id → 这一轮调用过的工具、推荐的视频
  final Map<int, List<ToolCall>> _toolCalls = {};
  final Map<int, List<RecommendedVideo>> _videos = {};

  @override
  void initState() {
    super.initState();
    _currentSession = widget.session;
    if (_currentSession != null) {
      _loadMessages().then((_) {
        if (widget.initialMessage != null && mounted) {
          _messageController.text = widget.initialMessage!;
          _sendMessage();
        }
      });
    }
  }

  @override
  void dispose() {
    _messageController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _loadMessages() async {
    if (_currentSession == null) return;

    try {
      setState(() {
        _isLoading = true;
      });

      final apiService = Provider.of<ApiService>(context, listen: false);
      final messages =
          await apiService.getConversationMessages(_currentSession!.sessionId);

      setState(() {
        _messages = messages;
        _isLoading = false;
      });

      _scrollToBottom();
    } catch (e) {
      setState(() {
        _isLoading = false;
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error loading messages: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_currentSession == null) {
      return _buildSessionSelection();
    }

    return Scaffold(
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              _currentSession!.theme,
              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
            ),
            if (_currentSession!.role != null)
              Text(
                _currentSession!.role!,
                style: const TextStyle(
                    fontSize: 12, color: AppTheme.textSecondaryColor),
              ),
          ],
        ),
        backgroundColor: Colors.transparent,
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadMessages,
          ),
          PopupMenuButton<String>(
            onSelected: (value) {
              if (value == 'new_session') {
                _startNewSession();
              }
            },
            itemBuilder: (context) => [
              const PopupMenuItem(
                value: 'new_session',
                child: Text('New Conversation'),
              ),
            ],
          ),
        ],
      ),
      body: Column(
        children: [
          // Messages
          Expanded(
            child: _isLoading
                ? const Center(
                    child: CircularProgressIndicator(
                      valueColor:
                          AlwaysStoppedAnimation<Color>(AppTheme.primaryColor),
                    ),
                  )
                : _messages.isEmpty
                    ? _buildEmptyState()
                    : _buildMessagesList(),
          ),

          // Input area
          _buildInputArea(),
        ],
      ),
    );
  }

  Widget _buildSessionSelection() {
    return Scaffold(
      appBar: AppBar(
        title: const Text('AI Conversation'),
        backgroundColor: Colors.transparent,
        elevation: 0,
      ),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 120,
              height: 120,
              decoration: BoxDecoration(
                color: AppTheme.primaryColor.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(60),
              ),
              child: const Icon(
                Icons.chat,
                size: 60,
                color: AppTheme.primaryColor,
              ),
            ),
            const SizedBox(height: 30),
            const Text(
              'Start a Conversation',
              style: TextStyle(
                fontSize: 24,
                fontWeight: FontWeight.bold,
                color: AppTheme.textPrimaryColor,
              ),
            ),
            const SizedBox(height: 10),
            const Text(
              'Upload an image to generate conversation themes\nor start with a text conversation',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 16,
                color: AppTheme.textSecondaryColor,
              ),
            ),
            const SizedBox(height: 30),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                ElevatedButton.icon(
                  onPressed: _uploadImageForThemes,
                  icon: const Icon(Icons.camera_alt),
                  label: const Text('Upload Image'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.primaryColor,
                    foregroundColor: Colors.white,
                  ),
                ),
                const SizedBox(width: 16),
                OutlinedButton.icon(
                  onPressed: _startTextConversation,
                  icon: const Icon(Icons.chat),
                  label: const Text('Text Chat'),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AppTheme.primaryColor,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(
            Icons.chat_bubble_outline,
            size: 64,
            color: AppTheme.textLightColor,
          ),
          const SizedBox(height: 20),
          const Text(
            'Start the conversation!',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w600,
              color: AppTheme.textSecondaryColor,
            ),
          ),
          const SizedBox(height: 10),
          Text(
            'Say hello to your ${_currentSession?.role ?? 'AI assistant'}',
            style: const TextStyle(
              fontSize: 14,
              color: AppTheme.textLightColor,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMessagesList() {
    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.all(16),
      itemCount: _messages.length,
      itemBuilder: (context, index) {
        final message = _messages[index];
        return MessageBubble(
          message: message,
          isUser: message.isUser,
          toolCalls: _toolCalls[message.id] ?? const [],
          videos: _videos[message.id] ?? const [],
        );
      },
    );
  }

  Widget _buildInputArea() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.1),
            blurRadius: 10,
            offset: const Offset(0, -5),
          ),
        ],
      ),
      child: Row(
        children: [
          // Image upload button
          IconButton(
            onPressed: _uploadContextImage,
            icon: const Icon(
              Icons.image,
              color: AppTheme.primaryColor,
            ),
          ),

          // Text input
          Expanded(
            child: TextField(
              controller: _messageController,
              decoration: InputDecoration(
                hintText: 'Type your message...',
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(25),
                  borderSide: BorderSide(color: Colors.grey.shade300),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(25),
                  borderSide: BorderSide(color: Colors.grey.shade300),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(25),
                  borderSide: const BorderSide(color: AppTheme.primaryColor),
                ),
                contentPadding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              ),
              maxLines: null,
              textInputAction: TextInputAction.send,
              onSubmitted: (_) => _sendMessage(),
            ),
          ),

          const SizedBox(width: 8),

          // Send button
          Container(
            decoration: const BoxDecoration(
              color: AppTheme.primaryColor,
              shape: BoxShape.circle,
            ),
            child: IconButton(
              onPressed: _isSending ? null : _sendMessage,
              icon: _isSending
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                      ),
                    )
                  : const Icon(
                      Icons.send,
                      color: Colors.white,
                    ),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _sendMessage() async {
    final message = _messageController.text.trim();
    if (message.isEmpty || _currentSession == null) return;

    setState(() {
      _isSending = true;
    });

    try {
      final apiService = Provider.of<ApiService>(context, listen: false);
      final result =
          await apiService.sendMessage(_currentSession!.sessionId, message);

      if (result['success']) {
        final aiMessage = ConversationMessage.fromJson(result['ai_message']);
        setState(() {
          _messages.add(ConversationMessage.fromJson(result['user_message']));
          _messages.add(aiMessage);
          if (aiMessage.id != null) {
            _toolCalls[aiMessage.id!] = (result['tool_trace'] as List? ?? [])
                .map((t) => ToolCall.fromJson(t as Map<String, dynamic>))
                .toList();
            _videos[aiMessage.id!] = (result['videos'] as List? ?? [])
                .map(
                    (v) => RecommendedVideo.fromJson(v as Map<String, dynamic>))
                .toList();
          }
        });

        _messageController.clear();
        _scrollToBottom();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error sending message: $e')),
        );
      }
    } finally {
      setState(() {
        _isSending = false;
      });
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _uploadImageForThemes() async {
    try {
      final XFile? image = await _picker.pickImage(source: ImageSource.gallery);
      if (image != null && mounted) {
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (context) => ConversationThemesScreen(
              imageFile: File(image.path),
            ),
          ),
        ).then((session) {
          if (session != null && mounted) {
            setState(() {
              _currentSession = session;
            });
            _loadMessages();
          }
        });
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error picking image: $e')),
        );
      }
    }
  }

  void _startTextConversation() {
    // Create a default conversation session
    final defaultTheme = ConversationTheme(
      id: 0,
      title: 'General Chat',
      description: 'A friendly AI assistant ready to help with any topic',
      role: 'Assistant',
      background: 'General conversation',
      scenario: 'general_chat',
    );

    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => ConversationThemesScreen(
          defaultTheme: defaultTheme,
        ),
      ),
    ).then((session) {
      if (session != null && mounted) {
        setState(() {
          _currentSession = session;
        });
        _loadMessages();
      }
    });
  }

  void _startNewSession() {
    setState(() {
      _currentSession = null;
      _messages.clear();
    });
  }

  Future<void> _uploadContextImage() async {
    try {
      final XFile? image = await _picker.pickImage(source: ImageSource.gallery);
      if (image != null) {
        // TODO: Upload context image and add to conversation
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Context image uploaded')),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error uploading image: $e')),
        );
      }
    }
  }
}
