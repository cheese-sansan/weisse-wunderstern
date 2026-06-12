"""
Lite Agent Orchestrator - 主编排引擎

零依赖轻量级智能体任务编排引擎，支持：
- 多任务顺序/动态编排
- 外部文件导入与分析（T0 预处理）
- 状态持久化与断点续跑
- 基于内容感知的动态任务分支
- LLM增强 + Mock兜底双模式
"""

import os
import sys
import json
from datetime import datetime
from utils.env_loader import load_env
from utils.state_manager import ensure_output_dir, init_state, update_task_status, load_state, save_state, now_str
from utils.context_manager import save_context
from tasks.t0_document_parsing import run as t0_run
from tasks.t1_keyword_extraction import run as t1_run
from tasks.t2_literature_search import run as t2_run
from tasks.t3_summary_generation import run as t3_run
from tasks.t4_report_framework import run as t4_run


load_env()

TASK_ORDER = ["T0", "T1", "T2", "T3", "T4", "T5", "T6"]
TASK_INDEX = {tid: i for i, tid in enumerate(TASK_ORDER)}


def should_run(task_id, next_task_id):
    """基于索引判断任务是否应执行，避免字符串比较在 T10 之后出错。"""
    return TASK_INDEX[task_id] >= TASK_INDEX[next_task_id]


def get_last_completed_task(output_dir):
  """
  获取最后一个已完成的任务ID，用于断点续跑。

  参数:
    output_dir: 输出目录路径

  返回:
    str | None: 最后完成的任务ID，无状态时返回 None
  """
  state_file = os.path.join(output_dir, "task_state.json")
  if not os.path.exists(state_file):
    return None
  with open(state_file, 'r', encoding='utf-8') as f:
    content = f.read().strip()
    if not content:
      return None
  try:
    state = json.loads(content)
  except json.JSONDecodeError:
    return None

  last_done = None
  for tid in TASK_ORDER:
    for t in state["task_list"]:
      if t["task_id"] == tid and t["status"] == "完成":
        last_done = tid
  return last_done


def log_resume(last_task, output_dir):
  """
  记录续跑日志，用于追踪每次运行的恢复情况。

  参数:
    last_task: 上次完成的任务ID
    output_dir: 输出目录路径
  """
  log_file = os.path.join(output_dir, "resume_log.txt")
  now = now_str()
  mode = "a" if os.path.exists(log_file) else "w"
  with open(log_file, mode, encoding="utf-8") as f:
    if last_task:
      f.write(f"[续跑时间] {now}\n[恢复执行] 从 {last_task} 之后开始\n")
    else:
      f.write(f"[启动时间] {now}\n[全新执行] 从 T0 开始\n")


def ensure_all_tasks_in_state(output_dir):
  """
  确保状态文件中包含所有基础任务节点。
  用于处理旧版状态文件可能缺少新增任务的情况。

  参数:
    output_dir: 输出目录路径
  """
  state_file = os.path.join(output_dir, "task_state.json")
  if not os.path.exists(state_file):
    return
  with open(state_file, 'r', encoding='utf-8') as f:
    state = json.load(f)
  existing_ids = {t["task_id"] for t in state["task_list"]}
  base_tasks = [
    ("T0", "文档内容提取"),
    ("T1", "关键词提取"),
    ("T2", "文献检索"),
    ("T3", "摘要生成"),
    ("T4", "报告框架搭建"),
    ("T5", "技术案例分析"),
    ("T6", "政策影响评估")
  ]
  changed = False
  for tid, name in base_tasks:
    if tid not in existing_ids:
      state["task_list"].append({
        "task_id": tid,
        "task_name": name,
        "status": "未开始",
        "status_history": [{"status": "未开始", "timestamp": now_str()}]
      })
      changed = True
  if changed:
    with open(state_file, 'w', encoding='utf-8') as f:
      json.dump(state, f, ensure_ascii=False, indent=2)


def run_pipeline(topic="", output_dir="outputs", file_path=None):
  """
  运行完整的智能体编排管道。

  管道包含以下任务节点：
  - T0: 文档内容提取（可选，仅当提供 file_path 时执行）
  - T1: 关键词提取
  - T2: 文献检索
  - T3: 摘要生成（文献不足时跳过）
  - T4: 报告框架搭建
  - T5: 技术案例分析（动态追加，条件触发）
  - T6: 政策影响评估（动态追加，条件触发）

  参数:
    topic: 研究主题（若提供 file_path，可从中自动提取）
    output_dir: 输出目录路径，默认为 "outputs"
    file_path: 可选的外部文件路径，支持 TXT/MD/JSON/PDF/DOCX
  """
  os.makedirs(output_dir, exist_ok=True)

  import utils.state_manager as sm
  sm.OUTPUT_DIR = output_dir
  sm.STATE_FILE = os.path.join(output_dir, "task_state.json")

  last_done = get_last_completed_task(output_dir)
  log_resume(last_done, output_dir)

  if last_done is None:
    init_state()
    next_task = "T0"
  else:
    ensure_all_tasks_in_state(output_dir)
    idx = TASK_ORDER.index(last_done)
    next_task = TASK_ORDER[idx + 1] if idx + 1 < len(TASK_ORDER) else None
    if next_task is None:
      print(f" [OK] 所有任务已完成，无需重复执行。")
      return

  print(f" [主题] {topic if topic else '(待从文件中提取)'}")
  print(f" [目录] {output_dir}")
  if file_path:
    print(f" [文件] {file_path}")
  print()

  # T0: 文档内容提取（仅当提供文件时执行）
  if should_run("T0", next_task) and file_path:
    print(" -> [T0] 文档内容提取...")
    update_task_status("T0", "进行中")
    doc_result = t0_run(file_path)
    save_context("T0", doc_result, output_dir)
    update_task_status("T0", "完成")
    print(f" [完成] [T0] 文件: {doc_result['file_name']} | 类型: {doc_result['file_type']} | 长度: {doc_result['content_length']} 字符")
    # 若未指定 topic，从文档摘要中尝试提取
    if not topic:
      topic = doc_result.get("file_name", "文档分析")
    next_task = "T1"
  elif should_run("T0", next_task):
    # 无文件输入，跳过 T0
    if next_task == "T0":
      update_task_status("T0", "完成")
      print(" [跳过] [T0] 未提供外部文件，跳过文档提取")
      next_task = "T1"

  if not topic and should_run("T1", next_task):
    print(" [ERROR] 未指定主题且未提供文件，无法继续。")
    print("  用法: python main.py --topic \"研究主题\"  或  python main.py --file 文档路径")
    sys.exit(1)

  # T1: 关键词提取
  if should_run("T1", next_task):
    print(" -> [T1] 关键词提取...")
    update_task_status("T1", "进行中")
    keywords = t1_run(topic)
    save_context("T1", keywords, output_dir)
    update_task_status("T1", "完成")
    print(f" [完成] [T1] 关键词: {keywords}")
    next_task = "T2"

  # T2: 文献检索
  if should_run("T2", next_task):
    print(" -> [T2] 文献检索...")
    update_task_status("T2", "进行中")
    literature = t2_run(keywords)
    save_context("T2", literature, output_dir)
    update_task_status("T2", "完成")
    print(f" [完成] [T2] 检索结果长度: {len(literature)} 字符")
    next_task = "T3"

    # 动态任务路由：根据文献内容决定是否追加 T5/T6
    state = load_state()
    has_t5 = any(t["task_id"] == "T5" for t in state["task_list"])
    has_t6 = any(t["task_id"] == "T6" for t in state["task_list"])
    need_t5 = "技术突破" in literature or "创新案例" in literature
    need_t6 = any(kw in literature for kw in ["政策法规", "监管", "合规", "法律", "标准"])

    if need_t5 and not has_t5:
      state["task_list"].append({
        "task_id": "T5",
        "task_name": "技术案例分析",
        "status": "未开始",
        "status_history": [{"status": "未开始", "timestamp": now_str()}]
      })
      print(" [动态路由] 检测到技术突破/创新案例 -> 追加 T5 任务")
    if need_t6 and not has_t6:
      state["task_list"].append({
        "task_id": "T6",
        "task_name": "政策影响评估",
        "status": "未开始",
        "status_history": [{"status": "未开始", "timestamp": now_str()}]
      })
      print(" [动态路由] 检测到政策法规相关内容 -> 追加 T6 任务")
    if need_t5 or need_t6:
      save_state(state)

  # T3: 摘要生成
  if should_run("T3", next_task):
    if "文献不足" in literature:
      print(" [跳过] [T3] 文献不足，跳过摘要生成")
      next_task = "T4"
    else:
      print(" -> [T3] 摘要生成...")
      update_task_status("T3", "进行中")
      summary = t3_run(literature)
      save_context("T3", summary, output_dir)
      update_task_status("T3", "完成")
      print(f" [完成] [T3] 摘要长度: {len(summary)} 字符")
      next_task = "T4"

  # T4: 报告框架搭建
  if should_run("T4", next_task):
    print(" -> [T4] 报告框架搭建...")
    update_task_status("T4", "进行中")
    if "文献不足" in literature:
      report = "# 报告框架\n\n## 摘要\n文献不足，建议补充检索\n\n## 分点提纲\n（无内容）"
    else:
      report = t4_run(topic, summary)
    with open(os.path.join(output_dir, "report_framework.md"), "w", encoding="utf-8") as f:
      f.write(report)
    update_task_status("T4", "完成")
    print(f" [完成] [T4] 报告已保存至 {output_dir}/report_framework.md")
    next_task = "T5"

  # T5: 技术案例分析（动态任务，条件触发）
  if should_run("T5", next_task):
    state = load_state()
    if any(t["task_id"] == "T5" and t["status"] == "未开始" for t in state["task_list"]):
      print(" -> [T5] 技术案例分析...")
      update_task_status("T5", "进行中")
      t5_result = f"针对'{topic}'的技术案例分析完成。"
      save_context("T5", t5_result, output_dir)
      update_task_status("T5", "完成")
      print(f" [完成] [T5]")
    next_task = "T6"

  # T6: 政策影响评估（动态任务，条件触发）
  if should_run("T6", next_task):
    state = load_state()
    if any(t["task_id"] == "T6" and t["status"] == "未开始" for t in state["task_list"]):
      print(" -> [T6] 政策影响评估...")
      update_task_status("T6", "进行中")
      t6_result = f"针对'{topic}'的政策影响评估完成。"
      save_context("T6", t6_result, output_dir)
      update_task_status("T6", "完成")
      print(f" [完成] [T6]")

  print()
  print(f" [成功] 管道执行完毕！所有结果已保存至: {output_dir}/")


if __name__ == "__main__":
  import argparse

  parser = argparse.ArgumentParser(
      description="Lite Agent Orchestrator - 零依赖轻量级智能体编排引擎",
      formatter_class=argparse.RawDescriptionHelpFormatter,
      epilog="""
示例:
  python main.py --topic "2025 自动驾驶行业趋势"
  python main.py --file ./documents/report.pdf
  python main.py --file ./data/notes.txt --topic "AI安全合规分析"
  python main.py --file ./doc.docx --output results/
      """
  )
  parser.add_argument("--topic", "-t", default="", help="研究主题")
  parser.add_argument("--file", "-f", default=None, help="外部文件路径（支持 TXT/MD/JSON/PDF/DOCX）")
  parser.add_argument("--output", "-o", default="outputs", help="输出目录（默认: outputs）")

  args = parser.parse_args()

  if not args.topic and not args.file:
    parser.print_help()
    print("\n [提示] 请至少指定 --topic 或 --file 参数。")
    sys.exit(1)

  print("=" * 50)
  print(" Lite Agent Orchestrator")
  print(" 零依赖轻量级智能体编排引擎")
  print("=" * 50)
  print()

  run_pipeline(topic=args.topic, output_dir=args.output, file_path=args.file)
