import 'package:flutter/material.dart';
import '../models/vocabulary_item.dart';
import '../utils/app_theme.dart';
import '../services/api_service.dart';

class VocabularyCard extends StatelessWidget {
  final VocabularyItem vocabularyItem;
  final VoidCallback onTap;

  const VocabularyCard({
    super.key,
    required this.vocabularyItem,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              // Image
              Container(
                width: 60,
                height: 60,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(12),
                  color: AppTheme.primaryColor.withValues(alpha: 0.1),
                ),
                child: vocabularyItem.segmentedImagePath != null
                    ? ClipRRect(
                        borderRadius: BorderRadius.circular(12),
                        child: Image.network(
                          ApiService.serverBaseUrl +
                              vocabularyItem.segmentedImagePath!,
                          fit: BoxFit.cover,
                          errorBuilder: (context, error, stackTrace) {
                            return const Icon(
                              Icons.image,
                              color: AppTheme.primaryColor,
                              size: 30,
                            );
                          },
                        ),
                      )
                    : const Icon(
                        Icons.image,
                        color: AppTheme.primaryColor,
                        size: 30,
                      ),
              ),

              const SizedBox(width: 16),

              // Content
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Word
                    Text(
                      vocabularyItem.word.toUpperCase(),
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: AppTheme.textPrimaryColor,
                      ),
                    ),

                    const SizedBox(height: 4),

                    // Definition (truncated)
                    Text(
                      vocabularyItem.definition,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontSize: 14,
                        color: AppTheme.textSecondaryColor,
                        height: 1.3,
                      ),
                    ),

                    const SizedBox(height: 8),

                    // Date
                    if (vocabularyItem.createdAt != null)
                      Text(
                        _formatDate(vocabularyItem.createdAt!),
                        style: const TextStyle(
                          fontSize: 12,
                          color: AppTheme.textLightColor,
                        ),
                      ),
                  ],
                ),
              ),

              // Arrow icon
              const Icon(
                Icons.arrow_forward_ios,
                size: 16,
                color: AppTheme.textLightColor,
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _formatDate(DateTime date) {
    final now = DateTime.now();
    final difference = now.difference(date);

    if (difference.inDays == 0) {
      return 'Today';
    } else if (difference.inDays == 1) {
      return 'Yesterday';
    } else if (difference.inDays < 7) {
      return '${difference.inDays} days ago';
    } else {
      return '${date.day}/${date.month}/${date.year}';
    }
  }
}
