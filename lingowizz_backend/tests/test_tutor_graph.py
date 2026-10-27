"""
对话导师流程的离线测试：用按脚本回复的假模型代替 GLM，不调用任何外部 API。

运行：在 lingowizz_backend 目录下执行  python -m pytest tests -q
"""

import os
import sys

import pytest
from flask import Flask
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import db  # noqa: E402
from src.models.vocabulary import VocabularyItem, WordMastery  # noqa: E402
from src.services import tutor_tools  # noqa: E402
from src.services.tutor_graph import MAX_TOOL_CALLS_PER_TURN, TutorService  # noqa: E402


class ScriptedChatModel(BaseChatModel):
    """依次返回预先写好的回复；记录每次收到的消息，便于断言"""
    responses: list
    calls: list = []

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls.append(messages)
        reply = self.responses.pop(0) if self.responses else AIMessage(content="(no more scripted replies)")
        return ChatResult(generations=[ChatGeneration(message=reply)])


def tool_call(name, args, call_id):
    return AIMessage(content="", tool_calls=[{'name': name, 'args': args, 'id': call_id, 'type': 'tool_call'}])


@pytest.fixture()
def app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
    db.init_app(app)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()


def make_service(tmp_path, responses):
    llm = ScriptedChatModel(responses=list(responses), calls=[])
    return TutorService(llm=llm, checkpoint_path=str(tmp_path / 'checkpoints.db')), llm


def test_small_talk_needs_no_tools(app, tmp_path):
    service, _ = make_service(tmp_path, [AIMessage(content="Nice! What do you like to cook?")])
    reply, trace = service.run_turn('s1', 'I like cooking.')
    assert reply == "Nice! What do you like to cook?"
    assert trace == []


def test_explain_then_save_word(app, tmp_path, monkeypatch):
    monkeypatch.setattr(tutor_tools.image_recognition_service, 'generate_word_definition_zhipu',
                        lambda word, raise_on_error=False: {'word': word, 'definition': 'a board for cutting food'})
    service, _ = make_service(tmp_path, [
        tool_call('explain_word', {'word': 'cutting board'}, 'c1'),
        AIMessage(content="A cutting board is a board for cutting food. Save it?"),
        tool_call('save_to_vocabulary', {'word': 'cutting board', 'definition': 'a board for cutting food'}, 'c2'),
        AIMessage(content="Saved!"),
    ])
    _, trace1 = service.run_turn('s2', "What does 'cutting board' mean?")
    assert [t['tool'] for t in trace1] == ['explain_word'] and trace1[0]['ok']

    reply, trace2 = service.run_turn('s2', 'Yes, please save it.')
    assert reply == "Saved!"
    assert [t['tool'] for t in trace2] == ['save_to_vocabulary']  # 每轮的轨迹单独计算
    assert VocabularyItem.query.count() == 1
    assert WordMastery.query.filter_by(word='cutting board').first().level == 0


def test_quiz_updates_mastery_and_profile(app, tmp_path):
    db.session.add(VocabularyItem(word='apple', definition='a fruit'))
    db.session.add(VocabularyItem(word='knife', definition='a tool for cutting'))
    db.session.commit()
    service, llm = make_service(tmp_path, [
        tool_call('get_learner_profile', {}, 'c1'),
        tool_call('ask_quiz', {'word': 'knife', 'question': 'What is a knife used for?'}, 'c2'),
        AIMessage(content="Quiz: what is a knife used for?"),
        tool_call('record_answer', {'word': 'knife', 'correct': False}, 'c3'),
        AIMessage(content="Not quite: it is for cutting."),
    ])
    _, trace = service.run_turn('s3', 'Quiz me!')
    assert [t['tool'] for t in trace] == ['get_learner_profile', 'ask_quiz']
    assert 'knife' in trace[0]['result_preview']
    get_state = lambda: service._get_graph().get_state({'configurable': {'thread_id': 's3'}}).values
    assert get_state()['pending_quiz'] == 'knife'

    service.run_turn('s3', 'It is for eating.')
    # 下一轮的 system prompt 明确告知有待作答的题目；记录答案后清除
    assert "quiz about 'knife' is pending" in llm.calls[-2][0].content
    assert get_state()['pending_quiz'] is None

    profile = tutor_tools.build_learner_profile()
    assert profile['vocabulary_size'] == 2
    assert profile['recent_mistakes'] == ['knife']
    assert profile['words_to_review'][0]['word'] in ('apple', 'knife')


def test_tool_error_is_returned_to_model(app, tmp_path):
    service, llm = make_service(tmp_path, [
        tool_call('look_at_image', {'question': 'What is on the table?'}, 'c1'),
        AIMessage(content="I can't see a photo here. Could you describe it?"),
    ])
    reply, trace = service.run_turn('s4', "What's on the table?")  # 该会话没有图片
    assert trace[0]['ok'] is False and 'No photo' in trace[0]['result_preview']
    assert reply.startswith("I can't see a photo")
    tool_msgs = [m for m in llm.calls[-1] if isinstance(m, ToolMessage) and m.tool_call_id == 'c1']
    assert tool_msgs and tool_msgs[0].status == 'error'


def test_invalid_arguments_do_not_crash(app, tmp_path):
    service, _ = make_service(tmp_path, [
        tool_call('record_answer', {'word': 'apple'}, 'c1'),  # 缺少 correct 参数
        AIMessage(content="Let's try again."),
    ])
    reply, trace = service.run_turn('s5', 'Apple is a fruit.')
    assert trace[0]['ok'] is False and reply == "Let's try again."


def test_tool_budget_forces_an_answer(app, tmp_path):
    looping = [tool_call('get_learner_profile', {}, f'c{i}') for i in range(MAX_TOOL_CALLS_PER_TURN + 3)]
    service, _ = make_service(tmp_path, looping)
    reply, trace = service.run_turn('s6', 'Quiz me again and again.')
    assert len(trace) == MAX_TOOL_CALLS_PER_TURN
    assert reply  # 模型仍想调用工具时，finalize 给出兜底回复

    # 检查持久化的历史：每个工具调用都有对应的 ToolMessage
    state = service._get_graph().get_state({'configurable': {'thread_id': 's6'}}).values
    requested = {c['id'] for m in state['messages'] if isinstance(m, AIMessage) for c in m.tool_calls}
    answered = {m.tool_call_id for m in state['messages'] if isinstance(m, ToolMessage)}
    assert requested == answered


def test_recommend_videos_once_per_topic(app, tmp_path, monkeypatch):
    found = [{'title': '点咖啡英语口语', 'duration': '3:00', 'author': 'a', 'url': 'u', 'cover': 'c',
              'seconds': 180, 'play': 9999}]
    monkeypatch.setattr(tutor_tools.video_finder, 'search', lambda keywords, topic='', limit=3: found)
    args = {'topic': 'ordering coffee', 'search_keywords': '点咖啡 英语口语'}
    service, _ = make_service(tmp_path, [
        tool_call('recommend_videos', args, 'c1'),
        AIMessage(content="Say: 'A latte with less sugar, please.' Here is a video."),
        tool_call('recommend_videos', args, 'c2'),  # 同一话题再次推荐
        AIMessage(content="Try: 'Less ice, please.'"),
    ])
    _, trace = service.run_turn('s8', "I don't know how to order coffee in English.")
    assert trace[0]['ok'] and trace[0]['videos'][0]['url'] == 'u'
    assert 'seconds' not in trace[0]['videos'][0]  # 只把展示需要的字段交给模型和 App

    _, trace2 = service.run_turn('s8', "I also don't know how to ask for less ice.")
    assert trace2[0]['ok'] is False and 'already recommended' in trace2[0]['result_preview']


def test_video_finder_filters_and_ranks():
    from src.services.video_search import LearningVideoFinder

    class FakeFinder(LearningVideoFinder):
        def _fetch(self, query):
            self.last_query = query
            return [
                {'bvid': 'BV1', 'title': '<em class="keyword">点咖啡</em> 英语口语', 'duration': '4:10', 'play': 20000, 'pic': '//i0/a.jpg'},
                {'bvid': 'BV2', 'title': '咖啡店英语口语 全集', 'duration': '1:20:00', 'play': 90000, 'pic': ''},  # 太长
                {'bvid': 'BV3', 'title': '手冲咖啡教程', 'duration': '5:00', 'play': 50000, 'pic': ''},  # 不是英语学习
                {'bvid': 'BV4', 'title': 'English for travel', 'duration': '6:00', 'play': 100, 'pic': ''},  # 太冷门
                {'bvid': 'BV5', 'title': '旅游英语 100 句', 'duration': '9:59', 'play': 30000, 'pic': ''},
            ]

    finder = FakeFinder()
    videos = finder.search('点咖啡', topic='ordering coffee')
    assert finder.last_query == '点咖啡 英语口语'
    assert [v['url'][-3:] for v in videos] == ['BV1', 'BV5']  # 关键词命中的排在前面
    assert videos[0]['title'] == '点咖啡 英语口语' and videos[0]['cover'] == 'https://i0/a.jpg'


def test_history_persists_across_turns(app, tmp_path):
    service, llm = make_service(tmp_path, [AIMessage(content="Hi!"), AIMessage(content="You said hello.")])
    service.run_turn('s7', 'Hello')
    service.run_turn('s7', 'What did I say?')
    contents = [m.content for m in llm.calls[-1]]
    assert 'Hello' in contents and 'Hi!' in contents

    service.reset_session('s7')
    state = service._get_graph().get_state({'configurable': {'thread_id': 's7'}})
    assert not state.values
