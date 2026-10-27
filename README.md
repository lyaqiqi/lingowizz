# LingoWizz

情景式英语学习应用：拍一张身边场景的照片，识别其中的物体，生成词汇卡片，再围绕照片与 AI 角色进行多轮英语对话。

## 功能

- **场景识别**：YOLOv8 检测并裁剪物体，GLM-4V 逐个复核物体名称；GLM-4V 生成整图的结构化描述（场景、物体、氛围）
- **词汇卡片**：为识别出的物体生成释义、例句、音标和词性，可加入单词本
- **情景对话**：根据照片生成角色扮演主题（如厨师、导游）。对话导师基于 LangGraph 实现，在对话中按需调用工具：
  - `look_at_image` / `detect_objects`：针对用户的问题查看照片，避免凭空描述
  - `explain_word`：查词
  - `save_to_vocabulary`：经用户同意后存入单词本
  - `recommend_videos`：用户卡在某个情景不会表达时，先教表达，再从 B 站检索 1–3 个对口的英语学习短视频（补全检索词、按时长 / 播放量 / 关键词过滤排序、缓存 24 小时，同一话题只推荐一次）
  - `get_learner_profile` / `ask_quiz` / `record_answer`：读取学习记录、针对薄弱词出题并登记题目、判题后更新掌握度（待作答的题目保存在对话状态中，下一轮显式提示模型判题）
- **App 端**：AI 回复上方显示本轮调用了哪些工具，推荐的视频以卡片形式显示在回复下方，点击即可打开；首页 Practice Quiz 一键开始针对薄弱词的测验
- **视频推荐页**：根据标签检索 B 站视频（Videos 页面）
- **学习记录**：会话内历史由 SqliteSaver 持久化；跨会话的单词掌握度存于数据库（0–5 级，答对升级、答错降级）
- **稳定性**：单轮工具调用上限、工具异常回传给模型处理、参数结构校验；模型服务不可用时退回到普通对话

## 结构

```
lingowizz_app/        Flutter 客户端
lingowizz_backend/
  run.py              启动入口
  src/routes/         Flask 接口（图片处理、对话、单词本、学习记录）
  src/services/
    image_recognition2.py   YOLOv8 + GLM-4V 识别、查词
    tutor_graph.py          对话流程（LangGraph）
    tutor_tools.py          对话中可调用的工具
    video_search.py         B 站视频检索
  tests/              对话流程离线测试（不调用外部 API）
  eval/               工具调用评测（用例与脚本）
```

## 运行后端

```bash
cd lingowizz_backend
python -m venv .venv
.venv\Scripts\activate          # macOS / Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # 填入 ZHIPU_API_KEY；不填 DATABASE_URL 时使用本地 SQLite
python run.py
```

## 测试与评测

```bash
python -m pytest tests -q     # 离线测试
python eval/run_eval.py       # 调用真实模型，输出工具选择准确率、误调用率、延迟等
```
