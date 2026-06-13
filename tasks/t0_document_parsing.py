"""
T0: 文档内容提取任务模块

从外部文件中提取文本内容，作为后续分析管道的输入源。
输出包含 raw_text、markdown_text、metadata 和 warnings。
支持 LLM 增强模式（对长文档生成结构化摘要）和 Mock 回退模式。
"""


def run(file_path: str) -> dict:
    """
    读取外部文件并返回结构化提取结果。

    返回:
        dict: {
            "raw_text": str,
            "markdown_text": str,
            "metadata": {
                "file_name": str,
                "file_type": str,
                "file_size": int,
                "parser": str,
            },
            "warnings": list[str],
            "contains_latex": bool,
            "structured_summary": str,
        }
    """
    from utils.file_reader import read_file

    result = read_file(file_path)

    if not result["success"]:
        return {
            "raw_text": "",
            "markdown_text": "",
            "metadata": {
                "file_name": result["file_name"],
                "file_type": "",
                "file_size": 0,
                "parser": "none",
            },
            "warnings": [f"文件读取失败: {result['error']}"],
            "contains_latex": False,
            "structured_summary": f"[错误] {result['error']}",
        }

    raw_text = result["content"]
    markdown_text = result["markdown_text"]
    contains_latex = result.get("contains_latex", False)
    warnings = list(result.get("warnings", []))
    file_name = result["file_name"]
    file_type = result["file_type"]
    file_size = result["file_size"]

    # ── LLM 增强模式：对长文档生成结构化摘要 ──
    structured_summary = ""
    try:
        from utils.llm_client import chat

        system_prompt = (
            "你是一个专业的文档分析助手。请对以下文档内容进行结构化分析，"
            "提取：1) 文档主题 2) 核心观点（3-5条） 3) 关键数据/事实 4) 文档类型判断。"
            "以Markdown格式输出，每条以'- '开头。"
        )
        truncated = (markdown_text or raw_text)[:8000]
        prompt = f"请分析以下文档内容：\n\n{truncated}"

        llm_result = chat(prompt, system_prompt=system_prompt, temperature=0.5)
        if llm_result is not None:
            structured_summary = llm_result
    except ImportError:
        pass

    # ── Mock 回退模式 ──
    if not structured_summary:
        preview = (markdown_text or raw_text)[:500]
        if len(raw_text) > 500:
            preview += f"\n\n... (共 {len(raw_text)} 字符，已截断预览)"
        structured_summary = f"[Mock模式] 文档分析预览：\n\n{preview}"

    if markdown_text != raw_text:
        warnings.append("文档包含表格/公式，已提取 Markdown 富文本")

    return {
        "raw_text": raw_text,
        "markdown_text": markdown_text,
        "metadata": {
            "file_name": file_name,
            "file_type": file_type,
            "file_size": file_size,
            "parser": file_type.lstrip(".") if file_type else "text",
        },
        "warnings": warnings,
        "contains_latex": contains_latex,
        "structured_summary": structured_summary,
    }
