"""
对话导师的工具调用评测。

每条用例在独立会话中运行：先执行 setup 中的前置轮次，再发送被测消息，
比较被测轮次实际调用的工具集合与标注的期望集合。

指标：
- 工具选择准确率：实际工具集合与任一期望集合一致（match=includes 时只要求包含）
- 误调用率：不需要工具的轮次中调用了工具的比例
- 平均每轮工具调用次数、每轮端到端延迟（P50 / P90）
- 故障恢复率：注入工具异常后，仍给出非空回复且没有对同一工具重试超过一次

运行（需要 ZHIPU_API_KEY；使用独立的 SQLite，不会写入正式数据库）：
    python eval/run_eval.py
"""

import json
import os
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(BACKEND_ROOT, 'eval', 'results')
EVAL_DB = os.path.join(RESULTS_DIR, 'eval.db')
os.makedirs(RESULTS_DIR, exist_ok=True)
if os.path.exists(EVAL_DB):
    os.remove(EVAL_DB)
os.environ['DATABASE_URL'] = 'sqlite:///' + EVAL_DB.replace('\\', '/')  # 先于 load_dotenv 设置，不会被覆盖

os.chdir(BACKEND_ROOT)
sys.path.insert(0, BACKEND_ROOT)
sys.stdout.reconfigure(encoding='utf-8')

from src.main import app  # noqa: E402
from src.models import db  # noqa: E402
from src.models.vocabulary import VocabularyItem  # noqa: E402
from src.services import tutor_tools  # noqa: E402
from src.services.tutor_graph import TutorService  # noqa: E402

TEST_IMAGE = os.path.join(BACKEND_ROOT, 'src', 'services', 'test_images', 'test_image.webp')
SCENE = {'role': 'Marine Biologist', 'theme': 'Ocean Life Explorer',
         'background': 'We are looking at photos of sea animals together.'}
SEED_WORDS = [('whale', 'a very large sea mammal'), ('octopus', 'a sea animal with eight arms'),
              ('reef', 'a ridge of rock or coral near the surface of the sea'),
              ('dolphin', 'a smart sea mammal'), ('submarine', 'a ship that can travel underwater')]

INJECTABLE = {
    'explain_word': (tutor_tools.image_recognition_service, 'generate_word_definition_zhipu'),
    'look_at_image': (tutor_tools.image_recognition_service, 'answer_about_image'),
}


def percentile(values, q):
    values = sorted(values)
    if not values:
        return 0
    k = (len(values) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (k - lo)


def tools_match(called, case):
    called = set(called)
    for expected in case['expect_any']:
        expected = set(expected)
        if case.get('match') == 'includes':
            if expected <= called:
                return True
        elif called == expected:
            return True
    return False


def run_case(service, case):
    session_id = f"eval-{case['id']}-{int(time.time() * 1000)}"
    image = TEST_IMAGE if case.get('image') else None
    for message in case.get('setup', []):
        service.run_turn(session_id, message, image_path=image, scene=SCENE)

    patched = None
    if case.get('inject_error'):
        target, attr = INJECTABLE[case['inject_error']]
        patched = (target, attr, getattr(target, attr))

        def broken(*args, **kwargs):
            raise TimeoutError('simulated service timeout')
        setattr(target, attr, broken)
    try:
        start = time.perf_counter()
        reply, trace = service.run_turn(session_id, case['message'], image_path=image, scene=SCENE)
        latency = time.perf_counter() - start
    finally:
        if patched:
            setattr(*patched)

    called = [t['tool'] for t in trace]
    result = {
        'id': case['id'], 'category': case['category'], 'message': case['message'],
        'called': called, 'expected': case['expect_any'], 'correct': tools_match(called, case),
        'latency_s': round(latency, 2), 'reply': reply,
    }
    if case.get('inject_error'):
        # 只有故障工具确实被调用时才计入恢复率
        attempts = called.count(case['inject_error'])
        result['triggered'] = attempts > 0
        result['recovered'] = attempts > 0 and bool(reply) and attempts <= 2
    return result


def main():
    cases = json.load(open(os.path.join(BACKEND_ROOT, 'eval', 'cases.json'), encoding='utf-8'))
    with app.app_context():
        for word, definition in SEED_WORDS:
            db.session.add(VocabularyItem(word=word, definition=definition))
        db.session.commit()

        service = TutorService(checkpoint_path=os.path.join(RESULTS_DIR, 'eval_checkpoints.db'))
        results = []
        for case in cases:
            try:
                r = run_case(service, case)
            except Exception as e:
                r = {'id': case['id'], 'category': case['category'], 'called': [], 'correct': False,
                     'latency_s': None, 'error': f'{type(e).__name__}: {e}'}
            results.append(r)
            mark = '✓' if r['correct'] else '✗'
            print(f"{mark} {r['id']:<11} called={r['called']} {r.get('error', '')}")

    graded = [r for r in results if r['category'] != 'tool_failure']
    by_cat = defaultdict(list)
    for r in graded:
        by_cat[r['category']].append(r['correct'])
    no_tool = [r for r in graded if r['category'] == 'no_tool']
    latencies = [r['latency_s'] for r in results if r['latency_s'] is not None]
    failures = [r for r in results if r['category'] == 'tool_failure' and r.get('triggered')]

    summary = {
        'cases': len(results),
        'tool_selection_accuracy': round(sum(r['correct'] for r in graded) / len(graded), 3),
        'accuracy_by_category': {k: f"{sum(v)}/{len(v)}" for k, v in by_cat.items()},
        'false_call_rate': round(sum(bool(r['called']) for r in no_tool) / len(no_tool), 3) if no_tool else None,
        # 不该推荐视频的轮次（查词、闲聊等）中误推荐视频的比例
        'false_video_rate': round(
            sum('recommend_videos' in r['called'] for r in graded if r['category'] != 'video')
            / max(1, sum(r['category'] != 'video' for r in graded)), 3),
        'avg_tool_calls_per_turn': round(statistics.mean(len(r['called']) for r in results), 2),
        'latency_p50_s': round(percentile(latencies, 0.5), 2),
        'latency_p90_s': round(percentile(latencies, 0.9), 2),
        'failure_recovery': f"{sum(r.get('recovered', False) for r in failures)}/{len(failures)}",
        'model': os.getenv('TUTOR_MODEL', 'glm-4-flash-250414'),
    }
    print('\n' + json.dumps(summary, ensure_ascii=False, indent=2))

    out = os.path.join(RESULTS_DIR, f"eval_{datetime.now():%Y%m%d_%H%M%S}.json")
    with open(out, 'w', encoding='utf-8') as f:
        json.dump({'summary': summary, 'results': results}, f, ensure_ascii=False, indent=2)
    print(f'详细结果已保存到 {out}')


if __name__ == '__main__':
    main()
