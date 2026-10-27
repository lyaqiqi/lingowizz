from flask import Blueprint, request, jsonify
from datetime import datetime
import uuid
from ..models.vocabulary import ConversationSession, ConversationMessage
from src.models import db             # <-- 从中央位置导入 db
from ..services.conversation_ai import conversation_ai_service
from ..services.tutor_graph import tutor_service

'''
这是一个写得非常好的 API 蓝图，它清晰地定义了与对话会话（Session）相关的所有 CRUD 操作（创建、读取、更新/在这里是发送消息、删除）。
代码结构工整，包含了完善的错误处理，
并且将AI逻辑（conversation_ai_service）分离了出去，这是非常好的设计实践。
'''

conversation_bp = Blueprint('conversation', __name__)

@conversation_bp.route('/sessions', methods=['POST'])
def create_session():
    """创建对话会话"""
    try:
        data = request.get_json()
        theme_data = data.get('theme')
        image_path = data.get('image_path')
        
        if not theme_data:
            return jsonify({'success': False, 'error': 'Theme data is required'}), 400
        
        # 创建新的对话会话
        session = ConversationSession(
            session_id=str(uuid.uuid4()),
            theme=theme_data.get('title', 'General Chat'),
            background=theme_data.get('background'),
            role=theme_data.get('role'),
            image_path=image_path,
            created_at=datetime.utcnow()
        )
        
        db.session.add(session)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'session': {
                'id': session.id,
                'session_id': session.session_id,
                'theme': session.theme,
                'background': session.background,
                'role': session.role,
                'image_path': session.image_path,
                'created_at': session.created_at.isoformat() if session.created_at else None
            }
        }),201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@conversation_bp.route('/sessions/<session_id>/messages', methods=['POST'])
def send_message(session_id):
    """发送消息"""
    try:
        data = request.get_json()
        user_message = data.get('message')
        
        if not user_message:
            return jsonify({'success': False, 'error': 'Message is required'}), 400
        
        # 查找会话
        session = ConversationSession.query.filter_by(session_id=session_id).first()
        if not session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404
        
        # 保存用户消息
        user_msg = ConversationMessage(
            session_id=session_id,
            sender='user',
            message=user_message,
            timestamp=datetime.utcnow()
        )
        db.session.add(user_msg)
        # 先提交用户消息：工具执行中若发生回滚，不会连带丢失这条消息
        db.session.commit()

        # 生成AI回复：由对话导师按需调用工具（看图、查词、单词本、复习记录）
        scene = {
            'role': session.role,
            'theme': session.theme,
            'background': session.background
        }
        tool_trace = []
        try:
            ai_response, tool_trace = tutor_service.run_turn(
                session_id, user_message, image_path=session.image_path, scene=scene)
        except Exception as e:
            # 模型服务不可用时退回到原有的单轮对话逻辑
            print(f"Tutor turn failed, using fallback: {e}")
            ai_response = ''
        if not ai_response:
            ai_response = conversation_ai_service.generate_ai_response(
                user_message, {'session_id': session_id, **scene})

        # 保存AI回复
        ai_msg = ConversationMessage(
            session_id=session_id,
            sender='assistant',
            message=ai_response,
            timestamp=datetime.utcnow()
        )
        db.session.add(ai_msg)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'user_message': {
                'id': user_msg.id,
                'session_id': user_msg.session_id,
                'sender': user_msg.sender,
                'message': user_msg.message,
                'timestamp': user_msg.timestamp.isoformat() if user_msg.timestamp else None
            },
            'ai_message': {
                'id': ai_msg.id,
                'session_id': ai_msg.session_id,
                'sender': ai_msg.sender,
                'message': ai_msg.message,
                'timestamp': ai_msg.timestamp.isoformat() if ai_msg.timestamp else None
            },
            'tool_trace': [{k: v for k, v in t.items() if k != 'videos'} for t in tool_trace],
            'videos': [v for t in tool_trace for v in t.get('videos') or []]
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@conversation_bp.route('/sessions/<session_id>/messages', methods=['GET'])
def get_messages(session_id):
    """获取对话消息"""
    try:
        # 查找会话
        session = ConversationSession.query.filter_by(session_id=session_id).first()
        if not session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404
        
        # 获取消息
        messages = ConversationMessage.query.filter_by(session_id=session_id)\
                                          .order_by(ConversationMessage.timestamp.asc())\
                                          .all()
        
        message_list = []
        for msg in messages:
            message_list.append({
                'id': msg.id,
                'session_id': msg.session_id,
                'sender': msg.sender,
                'message': msg.message,
                'timestamp': msg.timestamp.isoformat() if msg.timestamp else None,
                'is_user': msg.sender == 'user'
            })
        
        return jsonify({
            'success': True,
            'messages': message_list
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@conversation_bp.route('/sessions', methods=['GET'])
def get_sessions():
    """获取所有对话会话"""
    try:
        sessions = ConversationSession.query.order_by(ConversationSession.created_at.desc()).all()
        
        session_list = []
        for session in sessions:
            session_list.append({
                'id': session.id,
                'session_id': session.session_id,
                'theme': session.theme,
                'background': session.background,
                'role': session.role,
                'image_path': session.image_path,
                'created_at': session.created_at.isoformat() if session.created_at else None
            })
        
        return jsonify({
            'success': True,
            'sessions': session_list
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@conversation_bp.route('/sessions/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    """删除对话会话"""
    try:
        # 查找会话
        session = ConversationSession.query.filter_by(session_id=session_id).first()
        if not session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404
        
        # 删除相关消息
        ConversationMessage.query.filter_by(session_id=session_id).delete()
        
        # 删除会话
        db.session.delete(session)
        
        # 清除AI服务中的对话历史
        conversation_ai_service.clear_conversation_history(session_id)
        try:
            tutor_service.reset_session(session_id)
        except Exception as e:
            print(f"Failed to clear tutor history for {session_id}: {e}")
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Session deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

