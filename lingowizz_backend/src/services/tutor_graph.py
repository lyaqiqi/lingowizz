"""
情景对话导师：基于 LangGraph 的工具调用对话流程。

    START → tutor ──(有工具调用)──→ tools ──→ tutor ...
              │
              ├──(无工具调用)──────────────→ END
              └──(本轮工具调用已达上限)──→ finalize → END

- tutor：绑定工具的 GLM-4-flash，根据角色设定与教学规则决定直接回复或调用工具
- tools：逐个执行工具调用，捕获异常并作为 ToolMessage 回传，同时记录调用轨迹
- finalize：工具预算用完时，补齐未执行的调用并强制给出文字回复，防止循环
- 会话内的消息、工具调用历史与待回答的测验题由 SqliteSaver 按 session_id 持久化
"""

import json
import os
import sqlite3
import time
from typing import Annotated, Any, Dict, List, Optional, Tuple, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage, trim_messages
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from .tutor_tools import TOOLS, TOOLS_BY_NAME

MAX_TOOL_CALLS_PER_TURN = 4
MAX_HISTORY_MESSAGES = 24
ZHIPU_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"
CHECKPOINT_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                             'conversation_checkpoints.db')


class TutorState(TypedDict):
    messages: Annotated[list, add_messages]
    session_id: str
    image_path: Optional[str]
    scene: Optional[Dict[str, Any]]
    tool_calls_this_turn: int
    trace: List[Dict[str, Any]]
    pending_quiz: Optional[str]  # 已出题、等待用户作答的单词；跨轮保留
    recommended_topics: List[str]  # 本会话已推荐过视频的情景，避免重复推荐；跨轮保留


TOOL_RULES = """Tool rules (follow strictly):
- Call tools directly. Never write that you are going to call a tool, and never ask the learner to wait.
- Photo: whenever the learner's message refers to the photo or to something that may be in it (what, where, colour, how many, background), call look_at_image, or detect_objects to list everything. Never guess what the photo shows, and never ask the learner to describe it instead.
- Words: whenever the learner asks about a word or phrase (its meaning, pronunciation, part of speech or an example sentence), call explain_word first and base your answer on its result, because the app builds the learner's word card from that result. Do not answer word questions from memory.
- After explaining a word, offer to add it to the vocabulary book, and call save_to_vocabulary only after the learner agrees.
- Quiz: when the learner asks to be quizzed, tested or to review words, call get_learner_profile first, pick one of the weakest words, register the question with ask_quiz, then ask that ONE question.
- Answers: when a quiz is pending, the learner's message is their answer. Judge it and call record_answer for that word before replying.
- Stuck: when the learner says they don't know how to say something in English (or asks for videos to learn more), teach the expression directly in your reply, and also call recommend_videos with the situation in English and Chinese search keywords. Never recommend videos for single-word questions. Do not list the video titles or links in your reply; the app shows them as cards, so just mention them in one short sentence.
- Ordinary small talk needs no tools.
- If a tool returns an error, do not retry it with the same arguments; continue the conversation with what you already know."""

STYLE_RULES = """Style: stay in character, reply in 1-3 short sentences of simple English, and add a brief Chinese explanation only when introducing a new word."""


def _stringify(result: Any) -> str:
    return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, default=str)


def _demo_call(name: str, args: dict, call_id: str, result: Any) -> list:
    return [
        AIMessage(content="", tool_calls=[{'name': name, 'args': args, 'id': call_id, 'type': 'tool_call'}]),
        ToolMessage(content=_stringify(result), tool_call_id=call_id, name=name),
    ]


# 示范对话（few-shot）：仅靠文字规则时，GLM-4-flash 倾向于凭记忆回答词义、只口头说"我去查一下"，
# 给出一段完整的"提问 → 调用工具 → 依据结果回答"示范后，工具调用明显更稳定
FEW_SHOT_DEMO = [
    HumanMessage("What does 'anchor' mean?"),
    *_demo_call('explain_word', {'word': 'anchor'}, 'demo_1', {
        'word': 'anchor', 'definition': 'a heavy object dropped from a boat to stop it moving',
        'pronunciation': '/ˈæŋkər/', 'part_of_speech': 'noun',
        'example_sentence': 'The ship dropped its anchor near the island.'}),
    AIMessage("An anchor /ˈæŋkər/ is a heavy object a boat drops to stay in place (锚). "
              "Want me to add it to your vocabulary book?"),
    HumanMessage("Quiz me!"),
    *_demo_call('get_learner_profile', {}, 'demo_2', {
        'vocabulary_size': 3, 'words_to_review': [{'word': 'anchor', 'level': 0}]}),
    *_demo_call('ask_quiz', {'word': 'anchor', 'question': "What does an 'anchor' do for a boat?"}, 'demo_3',
                "Quiz registered for 'anchor'."),
    AIMessage("Quiz time! What does an 'anchor' do for a boat?"),
    HumanMessage("It keeps the boat from moving."),
    *_demo_call('record_answer', {'word': 'anchor', 'correct': True}, 'demo_4', {'word': 'anchor', 'level': 1}),
    AIMessage("Correct! An anchor stops the boat from drifting."),
    HumanMessage("I want to ask the captain to slow down, but I don't know how to say it."),
    *_demo_call('recommend_videos', {'topic': 'asking someone to slow down',
                                     'search_keywords': '请求别人慢一点 英语口语'}, 'demo_5', [
        {'title': '实用英语口语：礼貌地请别人慢一点', 'duration': '3:12', 'author': 'demo',
         'url': 'https://www.bilibili.com/video/BVdemo', 'cover': ''}]),
    AIMessage("You can say: \"Could you slow down a little, please?\" (能请您稍微慢一点吗？) "
              "I also found a short video on this for you to practise later."),
    SystemMessage("The conversation above was only an example. The real conversation starts now."),
]


def build_system_prompt(state: TutorState, budget_left: bool) -> str:
    scene = state.get('scene') or {}
    role = scene.get('role') or 'friendly English tutor'
    theme = scene.get('theme') or 'everyday conversation'
    background = scene.get('background') or ''

    if state.get('image_path'):
        photo = ("The learner has attached a photo of the scene. You cannot see it directly; "
                 "use look_at_image or detect_objects when you need to know what is in it.")
    else:
        photo = "No photo is attached to this conversation."

    parts = [
        f"You are a {role} in the scenario \"{theme}\". {background}".strip(),
        "You are also an English tutor helping a Chinese-speaking learner practise English through this role-play.",
        photo,
        TOOL_RULES,
        STYLE_RULES,
    ]
    if state.get('pending_quiz'):
        # 显式告知待作答的题目，不依赖模型从历史中自行推断
        parts.append(f"A quiz about '{state['pending_quiz']}' is pending: the learner's message is their answer. "
                     f"Judge it and call record_answer(word='{state['pending_quiz']}', correct=...) before replying.")
    if not budget_left:
        parts.append("The tool budget for this turn is used up. Answer now without calling any tool.")
    return "\n\n".join(parts)


def _recent_history(messages: list) -> list:
    # 只保留最近的消息；从用户消息处截断，保证工具调用与其结果成对出现
    return trim_messages(messages, strategy="last", token_counter=len,
                         max_tokens=MAX_HISTORY_MESSAGES, start_on="human", allow_partial=False)


def build_tutor_graph(llm, checkpointer=None):
    llm_with_tools = llm.bind_tools(TOOLS)

    def tutor(state: TutorState):
        budget_left = state.get('tool_calls_this_turn', 0) < MAX_TOOL_CALLS_PER_TURN
        prompt = ([SystemMessage(build_system_prompt(state, budget_left))] + FEW_SHOT_DEMO
                  + _recent_history(state['messages']))
        return {'messages': [llm_with_tools.invoke(prompt)]}

    def run_tools(state: TutorState):
        last = state['messages'][-1]
        outputs, trace = [], list(state.get('trace') or [])
        pending_quiz = state.get('pending_quiz')
        recommended = list(state.get('recommended_topics') or [])
        for call in last.tool_calls:
            start = time.perf_counter()
            try:
                tool = TOOLS_BY_NAME.get(call['name'])
                if tool is None:
                    raise ValueError(f"Unknown tool '{call['name']}'")
                result = tool.invoke({**call['args'], 'state': state})
                content, ok = _stringify(result), True
            except Exception as e:  # 参数校验失败或工具内部出错，都交给模型处理
                result, content, ok = None, f"Error: {type(e).__name__}: {e}", False
            outputs.append(ToolMessage(content=content, tool_call_id=call['id'], name=call['name'],
                                       status='success' if ok else 'error'))
            if ok and call['name'] == 'ask_quiz':
                pending_quiz = call['args'].get('word')
            elif ok and call['name'] == 'record_answer':
                pending_quiz = None
            elif ok and call['name'] == 'recommend_videos':
                recommended.append(call['args'].get('topic', ''))
            entry = {
                'tool': call['name'],
                'args': call['args'],
                'ok': ok,
                'latency_ms': round((time.perf_counter() - start) * 1000),
                'result_preview': content[:160],
            }
            if ok and call['name'] == 'recommend_videos':
                entry['videos'] = result  # 完整的视频信息供 App 展示卡片
            trace.append(entry)
        return {
            'messages': outputs,
            'tool_calls_this_turn': state.get('tool_calls_this_turn', 0) + len(last.tool_calls),
            'trace': trace,
            'pending_quiz': pending_quiz,
            'recommended_topics': recommended,
        }

    def finalize(state: TutorState):
        # 预算用完时，模型仍请求的工具调用不再执行，但必须补齐对应的 ToolMessage
        last = state['messages'][-1]
        skipped = [ToolMessage(content="Skipped: the tool budget for this turn is used up.",
                               tool_call_id=c['id'], name=c['name'], status='error') for c in last.tool_calls]
        prompt = ([SystemMessage(build_system_prompt(state, budget_left=False))] + FEW_SHOT_DEMO
                  + _recent_history(state['messages'] + skipped))
        reply = llm_with_tools.invoke(prompt)
        text = reply.content if isinstance(reply.content, str) and reply.content.strip() else \
            "Sorry, let's keep going with what we have. Could you say that again in another way?"
        return {'messages': skipped + [AIMessage(content=text)]}

    def route_after_tutor(state: TutorState):
        last = state['messages'][-1]
        if not getattr(last, 'tool_calls', None):
            return END
        if state.get('tool_calls_this_turn', 0) >= MAX_TOOL_CALLS_PER_TURN:
            return 'finalize'
        return 'tools'

    graph = StateGraph(TutorState)
    graph.add_node('tutor', tutor)
    graph.add_node('tools', run_tools)
    graph.add_node('finalize', finalize)
    graph.add_edge(START, 'tutor')
    graph.add_conditional_edges('tutor', route_after_tutor, ['tools', 'finalize', END])
    graph.add_edge('tools', 'tutor')
    graph.add_edge('finalize', END)
    return graph.compile(checkpointer=checkpointer)


def create_llm():
    from langchain_openai import ChatOpenAI
    api_key = os.getenv('ZHIPU_API_KEY')
    if not api_key:
        raise RuntimeError("ZHIPU_API_KEY is not set")
    return ChatOpenAI(
        model=os.getenv('TUTOR_MODEL', 'glm-4-flash-250414'),
        api_key=api_key,
        base_url=ZHIPU_BASE_URL,
        temperature=0.3,
        max_tokens=400,
        timeout=60,
        max_retries=2,
    )


class TutorService:
    """对外接口：按会话运行一轮对话，返回回复文本与工具调用轨迹"""

    def __init__(self, llm=None, checkpoint_path: str = CHECKPOINT_DB):
        self._llm = llm
        self._checkpoint_path = checkpoint_path
        self._graph = None
        self._checkpointer = None

    def _get_graph(self):
        if self._graph is None:
            conn = sqlite3.connect(self._checkpoint_path, check_same_thread=False)
            self._checkpointer = SqliteSaver(conn)
            self._graph = build_tutor_graph(self._llm or create_llm(), self._checkpointer)
        return self._graph

    def run_turn(self, session_id: str, user_message: str, image_path: Optional[str] = None,
                 scene: Optional[Dict[str, Any]] = None) -> Tuple[str, List[Dict[str, Any]]]:
        graph = self._get_graph()
        result = graph.invoke(
            {
                'messages': [HumanMessage(content=user_message)],
                'session_id': session_id,
                'image_path': image_path,
                'scene': scene,
                'tool_calls_this_turn': 0,
                'trace': [],
            },
            config={'configurable': {'thread_id': session_id}, 'recursion_limit': 20},
        )
        last = result['messages'][-1]
        reply = last.content if isinstance(last, AIMessage) and isinstance(last.content, str) else ""
        return reply.strip(), result.get('trace', [])

    def reset_session(self, session_id: str):
        self._get_graph()
        if hasattr(self._checkpointer, 'delete_thread'):
            self._checkpointer.delete_thread(session_id)


tutor_service = TutorService()
