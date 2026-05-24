"""
文献检索任务模块

支持双模式运行：
- LLM增强模式：通过大语言模型生成模拟学术文献条目
- Mock回退模式：基于规则匹配返回预设的文献检索结果
"""


def run(keywords: list | str) -> str:
  """
  根据关键词进行模拟学术文献检索。

  优先使用LLM模式生成详细的文献条目，若LLM不可用，
  则回退到基于关键词匹配的Mock模式。

  参数:
    keywords: 关键词列表或关键词字符串

  返回:
    str: 文献检索结果文本
  """
  # 将关键词列表转换为字符串
  if isinstance(keywords, list):
    topic = " ".join(str(k) for k in keywords)
  else:
    topic = str(keywords)

  # --- LLM增强模式 ---
  try:
    from utils.llm_client import chat

    system_prompt = (
      "你是一个学术文献检索助手。请根据关键词生成3-5条模拟学术文献条目，"
      "每条包含标题、来源和简要摘要。如果涉及技术突破或创新案例，请在文献中体现。"
      "如果涉及政策法规、监管等内容，也请在文献中体现。"
    )
    prompt = f"请根据以下关键词进行学术文献检索：\n\n关键词：{topic}"

    result = chat(prompt, system_prompt=system_prompt, temperature=0.7)

    if result is not None:
      return result
  except ImportError:
    # llm_client模块不可用，回退到Mock模式
    pass

  # --- Mock回退模式 ---
  # 基于关键词规则匹配返回预设结果
  if "AI" in topic or "大模型" in topic:
    return "检索到多篇关于技术突破和创新案例的文献，同时涉及相关政策法规监管动态。"
  if "智能汽车" in topic:
    return "文献聚焦自动驾驶安全标准、数据隐私保护及国家政策法规更新。"
  return "文献不足"
