"""
上下文管理工具模块

用于保存和加载各个任务节点的执行产物，实现任务之间的数据传递。
"""

import json
import os


def save_context(task_id, data, output_dir="outputs"):
  """
  保存指定任务的输出产物到全局上下文 JSON 文件中。

  参数:
    task_id: 任务ID (如 "T1")
    data: 任务产物内容 (可以是任何可 JSON 序列化的对象)
    output_dir: 输出目录路径
  """
  ctx_file = os.path.join(output_dir, "context_data.json")
  context = {}
  if os.path.exists(ctx_file):
    try:
      with open(ctx_file, 'r', encoding='utf-8') as f:
        context = json.load(f)
    except json.JSONDecodeError:
      pass
  context[f"{task_id}_output"] = {"result": data}
  with open(ctx_file, 'w', encoding='utf-8') as f:
    json.dump(context, f, ensure_ascii=False, indent=2)


def load_context(task_id, output_dir="outputs"):
  """
  加载指定任务的历史输出产物。

  参数:
    task_id: 任务ID (如 "T1")
    output_dir: 输出目录路径

  返回:
    any | None: 该任务之前保存的输出产物，如果不存在则返回 None
  """
  ctx_file = os.path.join(output_dir, "context_data.json")
  if not os.path.exists(ctx_file):
    return None
  try:
    with open(ctx_file, 'r', encoding='utf-8') as f:
      context = json.load(f)
    task_key = f"{task_id}_output"
    if task_key in context:
      return context[task_key].get("result")
  except Exception:
    pass
  return None
