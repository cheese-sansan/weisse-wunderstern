"""
状态管理工具模块

实现对智能体管道中各个任务执行状态的持久化、读取和更新，支持故障中断后的断点续跑。
"""

import json
import os
from datetime import datetime

OUTPUT_DIR = "outputs"
STATE_FILE = os.path.join(OUTPUT_DIR, "task_state.json")


def ensure_output_dir():
  """
  确保输出目录存在，若不存在则创建。
  """
  os.makedirs(OUTPUT_DIR, exist_ok=True)


def now_str():
  """
  获取当前时间的格式化字符串。

  返回:
    str: 格式为 "%Y-%m-%d %H:%M:%S" 的时间字符串
  """
  return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_state():
  """
  初始化任务状态，并将初始状态持久化写入 JSON 文件。
  """
  ensure_output_dir()
  tasks = [
    {"task_id": "T1", "task_name": "关键词提取", "status": "未开始", "status_history": [{"status": "未开始", "timestamp": now_str()}]},
    {"task_id": "T2", "task_name": "文献检索", "status": "未开始", "status_history": [{"status": "未开始", "timestamp": now_str()}]},
    {"task_id": "T3", "task_name": "摘要生成", "status": "未开始", "status_history": [{"status": "未开始", "timestamp": now_str()}]},
    {"task_id": "T4", "task_name": "报告框架搭建", "status": "未开始", "status_history": [{"status": "未开始", "timestamp": now_str()}]}
  ]
  state = {"task_list": tasks}
  with open(STATE_FILE, 'w', encoding='utf-8') as f:
    json.dump(state, f, ensure_ascii=False, indent=2)


def load_state():
  """
  加载当前的任务状态。若状态文件不存在或损坏，将重新初始化。

  返回:
    dict: 任务状态字典
  """
  if not os.path.exists(STATE_FILE):
    init_state()
  with open(STATE_FILE, 'r', encoding='utf-8') as f:
    content = f.read().strip()
    if not content:
      init_state()
      with open(STATE_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
  try:
    return json.loads(content)
  except json.JSONDecodeError:
    init_state()
    with open(STATE_FILE, 'r', encoding='utf-8') as f:
      content = f.read()
    return json.loads(content)


def save_state(state):
  """
  将当前状态保存写入状态文件。

  参数:
    state: 需要被持久化的状态字典
  """
  with open(STATE_FILE, 'w', encoding='utf-8') as f:
    json.dump(state, f, ensure_ascii=False, indent=2)


def update_task_status(task_id, new_status):
  """
  更新指定任务的状态，并记录状态变更的历史时间戳。

  参数:
    task_id: 任务ID (例如 "T1")
    new_status: 目标状态 (例如 "进行中", "完成")
  """
  state = load_state()
  for task in state["task_list"]:
    if task["task_id"] == task_id:
      if task["status"] != new_status:
        task["status"] = new_status
        task["status_history"].append({"status": new_status, "timestamp": now_str()})
  save_state(state)
