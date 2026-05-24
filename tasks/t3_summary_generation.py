"""
摘要生成任务模块

支持双模式运行：
- LLM增强模式：通过大语言模型生成综述摘要
- Mock回退模式：基于模板拼接生成简单摘要
"""


def run(literature_result: str) -> str:
  """
  根据文献检索结果生成综述摘要。

  优先使用LLM模式生成200-300字的综合摘要，若LLM不可用，
  则回退到基于模板的Mock模式。

  参数:
    literature_result: 文献检索结果文本

  返回:
    str: 生成的综述摘要
  """
  # --- LLM增强模式 ---
  try:
    from utils.llm_client import chat

    system_prompt = (
      "你是一个学术摘要生成专家。请根据以下文献检索结果，"
      "生成一段200-300字的综述摘要，概括核心发现和趋势。"
    )
    prompt = f"请根据以下文献检索结果生成综述摘要：\n\n{literature_result}"

    result = chat(prompt, system_prompt=system_prompt, temperature=0.7)

    if result is not None:
      return result
  except ImportError:
    # llm_client模块不可用，回退到Mock模式
    pass

  # --- Mock回退模式 ---
  # 根据文献结果长度决定摘要格式
  if len(literature_result) < 100:
    return f"基于文献检索结果的综合分析：{literature_result}"
  return f"基于文献检索结果的综合分析：{literature_result[:100]}..."
