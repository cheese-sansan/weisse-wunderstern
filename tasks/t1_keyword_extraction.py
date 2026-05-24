"""
关键词提取任务模块

支持双模式运行：
- LLM增强模式：通过大语言模型从主题中提取核心关键词
- Mock回退模式：基于简单的字符串分割逻辑提取关键词
"""

import json


def run(topic: str) -> list:
  """
  从给定主题中提取3-5个核心关键词。

  优先使用LLM模式进行智能关键词提取，若LLM不可用或解析失败，
  则回退到基于规则的Mock模式。

  参数:
    topic: 研究主题字符串

  返回:
    list: 包含3-5个关键词的列表
  """
  # --- LLM增强模式 ---
  try:
    from utils.llm_client import chat

    system_prompt = "你是一个专业的学术研究助手。请只返回JSON数组格式的关键词，不要包含其他内容。"
    prompt = f"请从以下主题中提取3-5个核心关键词，以JSON数组格式返回：\n\n{topic}"

    result = chat(prompt, system_prompt=system_prompt, temperature=0.7)

    if result is not None:
      # 尝试解析LLM返回的JSON数组
      try:
        keywords = json.loads(result)
        if isinstance(keywords, list) and len(keywords) > 0:
          return keywords
      except (json.JSONDecodeError, TypeError):
        # JSON解析失败，回退到Mock模式
        pass
  except ImportError:
    # llm_client模块不可用，回退到Mock模式
    pass

  # --- Mock回退模式 ---
  # 按空格分割主题，过滤长度小于2的字符串，最多返回5个
  words = [w for w in topic.split() if len(w) >= 2]
  if not words:
    return [topic]
  return words[:5]
