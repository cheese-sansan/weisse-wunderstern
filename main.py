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
from utils.state_manager import now_str
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


def _ensure_all_tasks_in_state(smgr):
  """确保状态中包含所有基础任务节点（用于旧状态升级）。"""
  state = smgr.load_state()
  existing_ids = {t["task_id"] for t in state["task_list"]}
  base_tasks = [
    ("T0", "文档内容提取"), ("T1", "关键词提取"),
    ("T2", "文献检索"), ("T3", "摘要生成"),
    ("T4", "报告框架搭建"), ("T5", "技术案例分析"),
    ("T6", "政策影响评估"),
  ]
  changed = False
  for tid, name in base_tasks:
    if tid not in existing_ids:
      state["task_list"].append({
        "task_id": tid, "task_name": name, "status": "未开始",
        "status_history": [{"status": "未开始", "timestamp": now_str()}]
      })
      changed = True
  if changed:
    smgr.save_state(state)


def run_pipeline(topic="", output_dir="outputs", file_path=None):
  """
  运行完整的智能体编排管道。

  参数:
    topic: 研究主题（若提供 file_path，可从中自动提取）
    output_dir: 输出目录路径，默认为 "outputs"
    file_path: 可选的外部文件路径，支持 TXT/MD/JSON/PDF/DOCX
  """
  from utils.state_manager import StateManager
  from utils.context_manager import ContextStore

  job_id = os.path.basename(output_dir.rstrip("/\\"))
  smgr = StateManager(job_id)
  ctx = ContextStore(job_id)

  os.makedirs(output_dir, exist_ok=True)

  # 断点续跑检测
  last_done = smgr.get_last_completed_task()
  log_resume(last_done, output_dir)

  if last_done is None:
    smgr.init_state()
    next_task = "T0"
  else:
    _ensure_all_tasks_in_state(smgr)
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
    smgr.update_task_status("T0", "进行中")
    doc_result = t0_run(file_path)
    ctx.save("T0", doc_result)
    smgr.update_task_status("T0", "完成")
    meta = doc_result.get("metadata", {})
    text_len = len(doc_result.get("raw_text", ""))
    print(f" [完成] [T0] 文件: {meta.get('file_name')} | 类型: {meta.get('file_type')} | 长度: {text_len} 字符")
    if doc_result.get("warnings"):
      for w in doc_result["warnings"]:
        print(f"  [WARNING] {w}")
    if not topic:
      topic = meta.get("file_name", "文档分析")
    next_task = "T1"
  elif should_run("T0", next_task):
    if next_task == "T0":
      smgr.update_task_status("T0", "完成")
      print(" [跳过] [T0] 未提供外部文件，跳过文档提取")
      next_task = "T1"

  if not topic and should_run("T1", next_task):
    print(" [ERROR] 未指定主题且未提供文件，无法继续。")
    print("  用法: python main.py --topic \"研究主题\"  或  python main.py --file 文档路径")
    sys.exit(1)

  # T1: 关键词与学术实体提取
  if should_run("T1", next_task):
    print(" -> [T1] 关键词与学术实体提取...")
    smgr.update_task_status("T1", "进行中")
    t1_output = t1_run(topic)
    ctx.save("T1", t1_output)
    smgr.update_task_status("T1", "完成")
    keywords = t1_output.get("keywords", [])
    entities = t1_output.get("academic_entities", {})
    print(f" [完成] [T1] 关键词: {keywords} | 实体: {json.dumps({k: v for k, v in entities.items() if k != 'relations'}, ensure_ascii=False)}")
    next_task = "T2"

  # T2: 结构化文献检索
  if should_run("T2", next_task):
    print(" -> [T2] 文献检索...")
    smgr.update_task_status("T2", "进行中")
    t2_output = t2_run(t1_output)
    ctx.save("T2", t2_output)
    smgr.update_task_status("T2", "完成")
    lit_results = t2_output.get("literature_results", [])
    print(f" [完成] [T2] 检索到 {len(lit_results)} 条文献")
    next_task = "T3"

    # 动态任务路由：基于学术实体字段判断是否追加 T5/T6
    state = smgr.load_state()
    has_t5 = any(t["task_id"] == "T5" for t in state["task_list"])
    has_t6 = any(t["task_id"] == "T6" for t in state["task_list"])
    methods = [m.lower() for m in entities.get("methods", [])]
    domains = [d.lower() for d in entities.get("domains", [])]
    policy_domains = {"policy", "law", "legal", "regulation", "governance", "compliance"}
    need_t5 = bool(methods) or any(
        kw in " ".join(methods + domains) for kw in ["transformer", "diffusion", "gan", "rl", "reinforcement"]
    )
    need_t6 = bool(set(domains) & policy_domains) or any(
        kw in str(keywords) for kw in ["政策", "法规", "监管", "合规", "法律", "标准"]
    )

    if need_t5 and not has_t5:
      state["task_list"].append({
        "task_id": "T5",
        "task_name": "技术案例分析",
        "status": "未开始",
        "status_history": [{"status": "未开始", "timestamp": now_str()}]
      })
      print(" [动态路由] 检测到技术方法实体 -> 追加 T5 任务")
    if need_t6 and not has_t6:
      state["task_list"].append({
        "task_id": "T6",
        "task_name": "政策影响评估",
        "status": "未开始",
        "status_history": [{"status": "未开始", "timestamp": now_str()}]
      })
      print(" [动态路由] 检测到政策/监管领域 -> 追加 T6 任务")
    if need_t5 or need_t6:
      smgr.save_state(state)

  # T3: 摘要生成
  literature_is_empty = len(lit_results) == 0
  if should_run("T3", next_task):
    if literature_is_empty:
      print(" [跳过] [T3] 文献不足，跳过摘要生成")
      next_task = "T4"
    else:
      print(" -> [T3] 摘要生成...")
      smgr.update_task_status("T3", "进行中")
      summary = t3_run(t2_output)
      ctx.save("T3", summary)
      smgr.update_task_status("T3", "完成")
      print(f" [完成] [T3] 摘要长度: {len(summary)} 字符")
      next_task = "T4"

  # T4: 报告框架搭建
  if should_run("T4", next_task):
    print(" -> [T4] 报告框架搭建...")
    smgr.update_task_status("T4", "进行中")
    if literature_is_empty:
      report = "# 报告框架\n\n## 摘要\n文献不足，建议补充检索\n\n## 分点提纲\n（无内容）"
    else:
      report = t4_run(topic, summary)
    report_path = os.path.join(output_dir, "report_framework.md")
    with open(report_path, "w", encoding="utf-8") as f:
      f.write(report)
    smgr.update_task_status("T4", "完成")
    print(f" [完成] [T4] 报告已保存至 {report_path}")
    next_task = "T5"

  # T5: 技术案例分析（动态任务，条件触发）
  if should_run("T5", next_task):
    state = smgr.load_state()
    if any(t["task_id"] == "T5" and t["status"] == "未开始" for t in state["task_list"]):
      print(" -> [T5] 技术案例分析...")
      smgr.update_task_status("T5", "进行中")
      t5_result = f"针对'{topic}'的技术案例分析完成。"
      ctx.save("T5", t5_result)
      smgr.update_task_status("T5", "完成")
      print(f" [完成] [T5]")
    next_task = "T6"

  # T6: 政策影响评估（动态任务，条件触发）
  if should_run("T6", next_task):
    state = smgr.load_state()
    if any(t["task_id"] == "T6" and t["status"] == "未开始" for t in state["task_list"]):
      print(" -> [T6] 政策影响评估...")
      smgr.update_task_status("T6", "进行中")
      t6_result = f"针对'{topic}'的政策影响评估完成。"
      ctx.save("T6", t6_result)
      smgr.update_task_status("T6", "完成")
      print(f" [完成] [T6]")

  smgr.set_completed()
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
