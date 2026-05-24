"""
T0: 文档内容提取任务模块

从外部文件中提取文本内容，作为后续分析管道的输入源。
支持 LLM 增强模式（对长文档生成结构化摘要）和直接透传模式。
"""


def run(file_path: str) -> dict:
  """
  读取外部文件并提取结构化内容。

  参数:
    file_path: 文件路径

  返回:
    dict: {
      "raw_content": str,       # 原始文件内容
      "file_name": str,         # 文件名
      "file_type": str,         # 文件类型
      "content_length": int,    # 内容长度
      "structured_summary": str # 结构化摘要（LLM模式）或截取前段（Mock模式）
    }
  """
  from utils.file_reader import read_file

  result = read_file(file_path)

  if not result["success"]:
    return {
        "raw_content": "",
        "file_name": result["file_name"],
        "file_type": "",
        "content_length": 0,
        "structured_summary": f"[错误] 文件读取失败: {result['error']}",
    }

  raw_content = result["content"]
  file_name = result["file_name"]
  file_type = result["file_type"]
  content_length = len(raw_content)

  # --- LLM增强模式：对长文档生成结构化摘要 ---
  try:
    from utils.llm_client import chat

    system_prompt = (
        "你是一个专业的文档分析助手。请对以下文档内容进行结构化分析，"
        "提取：1) 文档主题 2) 核心观点（3-5条） 3) 关键数据/事实 4) 文档类型判断。"
        "以Markdown格式输出，每条以'- '开头。"
    )
    # 如果文档过长，截取前 8000 字符
    truncated = raw_content[:8000]
    prompt = f"请分析以下文档内容：\n\n{truncated}"

    llm_result = chat(prompt, system_prompt=system_prompt, temperature=0.5)

    if llm_result is not None:
      return {
          "raw_content": raw_content,
          "file_name": file_name,
          "file_type": file_type,
          "content_length": content_length,
          "structured_summary": llm_result,
      }
  except ImportError:
    pass

  # --- Mock回退模式 ---
  preview = raw_content[:500]
  if len(raw_content) > 500:
    preview += f"\n\n... (共 {content_length} 字符，已截断预览)"

  return {
      "raw_content": raw_content,
      "file_name": file_name,
      "file_type": file_type,
      "content_length": content_length,
      "structured_summary": f"[Mock模式] 文档分析预览：\n\n{preview}",
  }
