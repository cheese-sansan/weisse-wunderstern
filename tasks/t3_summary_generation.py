"""
摘要生成任务模块

根据文献检索结果生成综述摘要。
支持结构化 dict 输入（T2 新 schema）和旧版 str 输入。
"""

import json


def run(literature_result) -> str:
    """
    根据文献检索结果生成综述摘要。

    参数:
        literature_result: T2 产出的 dict（含 literature_results）或旧版 str

    返回:
        str: 生成的综述摘要
    """
    # 统一转换为字符串格式，兼容新旧输入
    if isinstance(literature_result, dict):
        lit_results = literature_result.get("literature_results", [])
        if not lit_results:
            return "文献不足"
        # 将结构化结果转为文本供 LLM 处理
        context = _format_for_prompt(lit_results)
    else:
        context = str(literature_result)

    # ── LLM 增强模式 ──
    try:
        from utils.llm_client import chat

        system_prompt = (
            "你是一个学术摘要生成专家。请根据以下文献检索结果，"
            "生成一段200-300字的综述摘要，概括核心发现和趋势。"
        )
        prompt = f"请根据以下文献检索结果生成综述摘要：\n\n{context}"

        result = chat(prompt, system_prompt=system_prompt, temperature=0.7)
        if result is not None:
            return result
    except ImportError:
        pass

    # ── Mock 回退模式 ──
    if len(context) < 100:
        return f"基于文献检索结果的综合分析：{context}"
    return f"基于文献检索结果的综合分析：{context[:100]}..."


def _format_for_prompt(lit_results: list) -> str:
    """将结构化文献结果格式化为 LLM prompt 文本。"""
    parts = []
    for i, lr in enumerate(lit_results, 1):
        parts.append(
            f"[{i}] {lr.get('title', 'Unknown')} "
            f"({', '.join(lr.get('authors', []))}, {lr.get('year', 'N/A')})\n"
            f"  方法: {lr.get('core_method', 'N/A')}\n"
            f"  数据集: {', '.join(lr.get('datasets', [])) or 'N/A'}\n"
            f"  指标: {', '.join(lr.get('metrics', [])) or 'N/A'}\n"
            f"  发现: {'; '.join(lr.get('key_findings', []))}\n"
            f"  局限: {'; '.join(lr.get('limitations', []))}\n"
            f"  来源类型: {lr.get('source_type', 'unknown')}"
        )
    return "\n\n".join(parts)
