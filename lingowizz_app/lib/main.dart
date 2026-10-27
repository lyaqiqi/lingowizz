import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'screens/splash_screen.dart';
import 'screens/home_screen.dart';
import 'screens/vocabulary_screen.dart';
import 'screens/conversation_screen.dart';
import 'screens/video_screen.dart';
import 'services/api_service.dart';
import 'utils/app_theme.dart';

void main() {
  runApp(const LingoWizzApp());
}

class LingoWizzApp extends StatelessWidget {
  const LingoWizzApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        Provider<ApiService>(
          create: (_) => ApiService(),
        ),
      ],
      child: MaterialApp(
        title: 'LingoWizz',
        theme: AppTheme.lightTheme,
        darkTheme: AppTheme.darkTheme,
        themeMode: ThemeMode.system,
        home: const SplashScreen(),
        routes: {
          '/home': (context) => const HomeScreen(),
          '/vocabulary': (context) => const VocabularyScreen(),
          '/conversation': (context) => const ConversationScreen(),
          '/videos': (context) => const VideoScreen(),
        },
        debugShowCheckedModeBanner: false,
      ),
    );
  }
}

