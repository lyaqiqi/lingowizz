import 'package:flutter/material.dart';
import '../utils/app_theme.dart';
import '../services/api_service.dart';

class ObjectCard extends StatelessWidget {
  final Map<String, dynamic> object;
  final VoidCallback onAddToVocabulary;

  const ObjectCard({
    super.key,
    required this.object,
    required this.onAddToVocabulary,
  });

  @override
  Widget build(BuildContext context) {
    final confidence = (object['confidence'] * 100).toInt();

    final String? imagePath = object['segmented_image'];

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            // Object image (if available)
            Container(
              width: 60,
              height: 60,
              decoration: BoxDecoration(
                color: AppTheme.primaryColor.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: imagePath != null && imagePath.isNotEmpty
                  ? ClipRRect(
                      borderRadius: BorderRadius.circular(12),
                      child: Image.network(
                        ApiService.serverBaseUrl + imagePath,
                        fit: BoxFit.cover,
                        errorBuilder: (context, error, stackTrace) {
                          debugPrint('Image load error: $error');
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

            // Object info
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    object['name'].toString().toUpperCase(),
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: AppTheme.textPrimaryColor,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      Icon(
                        Icons.verified,
                        size: 16,
                        color: _getConfidenceColor(confidence),
                      ),
                      const SizedBox(width: 4),
                      Text(
                        '$confidence% confidence',
                        style: TextStyle(
                          fontSize: 12,
                          color: _getConfidenceColor(confidence),
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Container(
                    height: 4,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(2),
                      color: Colors.grey[200],
                    ),
                    child: FractionallySizedBox(
                      alignment: Alignment.centerLeft,
                      widthFactor: confidence / 100,
                      child: Container(
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(2),
                          color: _getConfidenceColor(confidence),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(width: 16),

            // Add to vocabulary button
            ElevatedButton(
              onPressed: onAddToVocabulary,
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.primaryColor,
                foregroundColor: Colors.white,
                padding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
              ),
              child: const Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.add, size: 16),
                  SizedBox(width: 4),
                  Text(
                    'Add',
                    style: TextStyle(fontSize: 12),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Color _getConfidenceColor(int confidence) {
    if (confidence >= 80) {
      return AppTheme.successColor;
    } else if (confidence >= 60) {
      return AppTheme.warningColor;
    } else {
      return AppTheme.errorColor;
    }
  }
}
