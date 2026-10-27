"""
对话导师可调用的工具：看图问答、物体检测、查词、单词本与学习记录。

每个工具都由模型在对话中按需调用；工具内部出错时直接抛出异常，
由 tutor_graph 中的工具执行节点捕获并把错误信息回传给模型。
"""

import os
from datetime import datetime
from typing import Annotated, Any, Dict, List

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from ..models import db
from ..models.vocabulary import VocabularyItem, WordMastery
from .image_recognition2 import image_recognition_service
from .video_search import LearningVideoFinder

video_finder = LearningVideoFinder()

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'uploads')

# 同一张图片只做一次检测（YOLO + 逐个物体的 GLM-4V 复核较慢）
_detection_cache: Dict[str, List[Dict[str, Any]]] = {}


def _require_image(state: dict) -> str:
    image_path = state.get('image_path')
    if not image_path or not os.path.exists(image_path):
        raise ValueError("No photo is attached to this conversation.")
    return image_path


def _find_vocabulary(word: str):
    return VocabularyItem.query.filter(db.func.lower(VocabularyItem.word) == word.lower()).first()


def _find_mastery(word: str):
    return WordMastery.query.filter(db.func.lower(WordMastery.word) == word.lower()).first()


@tool(parse_docstring=True)
def look_at_image(question: str, state: Annotated[dict, InjectedState]) -> str:
    """Look at the learner's photo for this conversation and answer a specific question about it.

    Use this whenever the learner refers to something in the photo (what it is, its colour,
    position or use) instead of guessing.

    Args:
        question: A specific question about the photo, in English.
    """
    image_path = _require_image(state)
    return image_recognition_service.answer_about_image(image_path, question)


@tool
def detect_objects(state: Annotated[dict, InjectedState]) -> List[Dict[str, Any]]:
    """List the objects visible in the learner's photo, with confidence and bounding box.

    Useful for picking vocabulary to teach from the scene.
    """
    image_path = _require_image(state)
    if image_path not in _detection_cache:
        objects = image_recognition_service.segment_and_identify_combined(image_path, upload_folder=UPLOAD_DIR)
        _detection_cache[image_path] = [
            {'name': o.get('name'), 'confidence': round(float(o.get('confidence', 0)), 2), 'bbox': o.get('bbox')}
            for o in objects
        ]
    return _detection_cache[image_path]


@tool(parse_docstring=True)
def explain_word(word: str) -> Dict[str, Any]:
    """Look up an English word or phrase: definition, example sentence, pronunciation and part of speech.

    Always use this for questions about a word instead of answering from memory; the app shows
    the learner a word card built from this result.

    Args:
        word: The English word or short phrase to explain.
    """
    return image_recognition_service.generate_word_definition_zhipu(word, raise_on_error=True)


@tool(parse_docstring=True)
def save_to_vocabulary(word: str, definition: str, state: Annotated[dict, InjectedState],
                       example_sentence: str = "") -> str:
    """Save a word to the learner's vocabulary book. Only call this after the learner agrees.

    Args:
        word: The word to save.
        definition: A short definition of the word.
        example_sentence: An example sentence using the word.
    """
    try:
        if _find_vocabulary(word):
            return f"'{word}' is already in the vocabulary book."
        db.session.add(VocabularyItem(
            word=word,
            definition=definition,
            example_sentence=example_sentence or None,
            image_path=state.get('image_path'),
        ))
        if not _find_mastery(word):
            db.session.add(WordMastery(word=word))
        db.session.commit()
        return f"Saved '{word}' to the vocabulary book."
    except Exception:
        db.session.rollback()
        raise


def build_learner_profile(limit: int = 5) -> Dict[str, Any]:
    """汇总学习者画像：单词本规模、最需要复习的词、最近答错的词"""
    vocab = {v.word.lower(): v for v in VocabularyItem.query.all()}
    mastery = {m.word.lower(): m for m in WordMastery.query.all()}

    entries = []
    for key, item in vocab.items():
        m = mastery.get(key)
        entries.append({
            'word': item.word,
            'definition': item.definition,
            'level': m.level if m else 0,
            'review_count': m.review_count if m else 0,
            'last_reviewed_at': m.last_reviewed_at if m else None,
        })

    # 等级低的优先；同等级时从未复习或很久没复习的优先
    entries.sort(key=lambda e: (e['level'], e['last_reviewed_at'] or datetime.min))
    to_review = [{k: e[k] for k in ('word', 'definition', 'level', 'review_count')} for e in entries[:limit]]

    recent_mistakes = (WordMastery.query.filter(WordMastery.last_correct.is_(False))
                       .order_by(WordMastery.last_reviewed_at.desc()).limit(limit).all())

    return {
        'vocabulary_size': len(vocab),
        'mastered': sum(1 for e in entries if e['level'] >= WordMastery.MAX_LEVEL),
        'words_to_review': to_review,
        'recent_mistakes': [m.word for m in recent_mistakes],
    }


@tool
def get_learner_profile() -> Dict[str, Any]:
    """Get the learner's study record: vocabulary size, the weakest words to review, and recent mistakes.

    Call this before quizzing the learner so the quiz targets words they have not mastered.
    """
    return build_learner_profile()


@tool(parse_docstring=True)
def ask_quiz(word: str, question: str) -> str:
    """Register a quiz question before asking it, so the learner's next message is graded as the answer.

    Args:
        word: The vocabulary word being quizzed.
        question: The quiz question you are about to ask the learner.
    """
    return f"Quiz registered for '{word}'. Now ask the learner: {question}"


@tool(parse_docstring=True)
def record_answer(word: str, correct: bool) -> Dict[str, Any]:
    """Record the result of a quiz question so the learner's mastery level is updated.

    Args:
        word: The word that was quizzed.
        correct: Whether the learner's answer was correct.
    """
    try:
        m = _find_mastery(word)
        if m is None:
            m = WordMastery(word=word)
            db.session.add(m)
        m.record(correct)
        db.session.commit()
        return {'word': m.word, 'level': m.level, 'review_count': m.review_count}
    except Exception:
        db.session.rollback()
        raise


@tool(parse_docstring=True)
def recommend_videos(topic: str, search_keywords: str,
                     state: Annotated[dict, InjectedState]) -> List[Dict[str, Any]]:
    """Find up to 3 short Bilibili videos that teach how to talk about a situation in English.

    Use this when the learner says they don't know how to say something in a situation, or asks
    for videos to learn more. Teach the expression yourself first; the videos are for practice
    afterwards. Do not use this for single-word questions.

    Args:
        topic: The situation in English, e.g. "ordering coffee".
        search_keywords: Chinese search keywords for Bilibili, e.g. "点咖啡 英语口语".
    """
    done = {t.lower() for t in (state.get('recommended_topics') or [])}
    if topic.strip().lower() in done:
        raise ValueError("Videos for this topic were already recommended in this conversation.")
    videos = video_finder.search(search_keywords, topic)
    if not videos:
        raise ValueError("No suitable videos were found.")
    return [{k: v[k] for k in ('title', 'duration', 'author', 'url', 'cover')} for v in videos]


TOOLS = [look_at_image, detect_objects, explain_word, save_to_vocabulary, get_learner_profile, ask_quiz,
         record_answer, recommend_videos]
TOOLS_BY_NAME = {t.name: t for t in TOOLS}
