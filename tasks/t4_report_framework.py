"""
报告框架生成任务模块

支持双模式运行：
- LLM增强模式：通过大语言模型生成完整的Markdown研究报告框架
- Mock回退模式：基于预设模板生成标准报告结构
"""


def run(topic: str, summary: str) -> str:
  """
  根据主题和摘要生成Markdown格式的研究报告框架。

  优先使用LLM模式生成包含多个章节的完整报告框架，若LLM不可用，
  则回退到基于模板的Mock模式。

  参数:
    topic: 研究主题
    summary: 综述摘要

  返回:
    str: Markdown格式的研究报告框架
  """
  # --- LLM增强模式 ---
  try:
    from utils.llm_client import chat

    system_prompt = (
      "你是一个专业的研究报告撰写助手。请根据主题和摘要，"
      "生成一个完整的Markdown格式研究报告框架，包含标题、摘要、"
      "至少4个主要章节（每个章节包含2-3个子节），以及结论和参考文献章节。"
    )
    prompt = (
      f"请根据以下信息生成研究报告框架：\n\n"
      f"研究主题：{topic}\n\n"
      f"综述摘要：{summary}"
    )

    result = chat(prompt, system_prompt=system_prompt, temperature=0.7)

    if result is not None:
      return result
  except ImportError:
    # llm_client模块不可用，回退到Mock模式
    pass

  # --- Mock回退模式 ---
  # 使用预设模板生成标准报告框架
  lines = [
    f"# {topic} 研究报告",
    "",
    "## 摘要",
    summary,
    "",
    "## 1. 研究背景与意义",
    "### 1.1 研究背景",
    "### 1.2 研究意义",
    "",
    "## 2. 核心技术进展",
    "### 2.1 关键技术分析",
    "### 2.2 技术趋势展望",
    "",
    "## 3. 应用场景分析",
    "### 3.1 典型应用案例",
    "### 3.2 行业影响评估",
    "",
    "## 4. 市场与竞争格局",
    "### 4.1 市场规模分析",
    "### 4.2 主要参与者对比",
    "",
    "## 5. 结论与展望",
    "",
    "## 参考文献",
    "",
  ]
  return "\n".join(lines)
