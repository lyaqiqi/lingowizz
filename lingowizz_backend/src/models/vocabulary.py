#from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json
from . import db  # <-- 添加这行，从 models/__init__.py 导入共享的 db
#定义了三个 SQLAlchemy 数据模型，它们将映射到你 PostgreSQL 数据库中的表
#db = SQLAlchemy()

class VocabularyItem(db.Model):
    __tablename__ = 'vocabulary_items'
    
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(100), nullable=False)
    definition = db.Column(db.Text, nullable=False)
    example_sentence = db.Column(db.Text, nullable=True)
    image_path = db.Column(db.String(255), nullable=True)
    segmented_image_path = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'word': self.word,
            'definition': self.definition,
            'example_sentence': self.example_sentence,
            'image_path': self.image_path,
            'segmented_image_path': self.segmented_image_path,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class ConversationSession(db.Model):
    __tablename__ = 'conversation_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), unique=True, nullable=False)
    theme = db.Column(db.String(200), nullable=False)
    background = db.Column(db.Text, nullable=True)
    role = db.Column(db.String(100), nullable=True)
    image_path = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 关联对话消息
    messages = db.relationship('ConversationMessage', backref='session', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'theme': self.theme,
            'background': self.background,
            'role': self.role,
            'image_path': self.image_path,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'messages': [msg.to_dict() for msg in self.messages]
        }

class ConversationMessage(db.Model):
    __tablename__ = 'conversation_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), db.ForeignKey('conversation_sessions.session_id'), nullable=False)
    sender = db.Column(db.String(20), nullable=False)  # 'user' or 'assistant'
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'sender': self.sender,
            'message': self.message,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }


class WordMastery(db.Model):
    """单词掌握度：跨会话的长期学习记录（简化 Leitner 规则，等级 0-5）"""
    __tablename__ = 'word_mastery'

    MAX_LEVEL = 5

    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(100), unique=True, nullable=False)
    level = db.Column(db.Integer, default=0, nullable=False)
    review_count = db.Column(db.Integer, default=0, nullable=False)
    correct_count = db.Column(db.Integer, default=0, nullable=False)
    last_correct = db.Column(db.Boolean, nullable=True)
    last_reviewed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def record(self, correct: bool):
        """记录一次复习：答对升一级，答错降一级"""
        self.review_count = (self.review_count or 0) + 1
        if correct:
            self.correct_count = (self.correct_count or 0) + 1
            self.level = min(self.MAX_LEVEL, (self.level or 0) + 1)
        else:
            self.level = max(0, (self.level or 0) - 1)
        self.last_correct = correct
        self.last_reviewed_at = datetime.utcnow()

    def to_dict(self):
        return {
            'word': self.word,
            'level': self.level,
            'review_count': self.review_count,
            'correct_count': self.correct_count,
            'last_correct': self.last_correct,
            'last_reviewed_at': self.last_reviewed_at.isoformat() if self.last_reviewed_at else None
        }
