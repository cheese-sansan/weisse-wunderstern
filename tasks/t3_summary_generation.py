"""
T3: Extractor-Critic-Synthesizer 审稿反思环路

三智能体角色协同完成学术提炼：
- Extractor：从文献和文档中提取证据片段、方法、指标
- Critic：审稿质疑，指出证据不足、结论冲突、潜在幻觉
- Synthesizer：综合前两者输出，生成包含证据标注的最终 Markdown 报告

每个角色均有独立的 LLM prompt 和 Mock fallback。
"""

import json


def run(t2_output, t0_output=None) -> dict:
    """
    运行三角色审稿反思环路。

    参数:
        t2_output: T2 文献检索结果 dict（含 literature_results）
        t0_output: 可选的 T0 文档解析结果 dict

    返回:
        dict: {
            "extractor_draft": dict,
            "critic_review": dict,
            "final_report": str,  # Markdown
        }
    """
    if isinstance(t2_output, str):
        t2_output = {"literature_results": []}
    if not isinstance(t2_output, dict):
        t2_output = {"literature_results": []}

    lit_results = t2_output.get("literature_results", [])
    if not lit_results:
        empty = _empty_result()
        empty["final_report"] = (
            "# 学术提炼报告\n\n"
            "## 摘要\n\n文献不足，无法进行学术提炼分析。建议补充检索。\n\n"
            "> 声明：未检索到有效文献，本报告仅为占位内容。"
        )
        return empty

    extractor = _extract_evidence(lit_results, t0_output)
    critic = _critic_review(extractor, lit_results)
    report = _synthesize_report(extractor, critic, lit_results, t0_output)

    return {
        "extractor_draft": extractor,
        "critic_review": critic,
        "final_report": report,
    }


def _empty_result() -> dict:
    return {
        "extractor_draft": {"claims": [], "metrics": [], "methods": [], "evidence_snippets": []},
        "critic_review": {
            "critiques": [{"point": "文献不足", "severity": "high", "suggestion": "补充检索"}],
            "overall_confidence": "low",
        },
        "final_report": "",
    }


# ═══════════════════════════════════════════════════════════════════
# Extractor Agent
# ═══════════════════════════════════════════════════════════════════

def _extract_evidence(lit_results: list, t0_output=None) -> dict:
    """从文献和文档中提取证据片段。"""

    # ── LLM 模式 ──
    try:
        from utils.llm_client import chat
        from utils.json_parser import extract_json

        context = _format_literature_for_prompt(lit_results)
        doc_text = ""
        if t0_output and isinstance(t0_output, dict):
            doc_text = (t0_output.get("markdown_text", "") or t0_output.get("raw_text", ""))[:4000]

        system_prompt = (
            "你是一个学术证据提取专家。请从文献和文档中精确提取技术信息，"
            "只返回 JSON，不要包含其他内容。不要编造未在输入中出现的数据。"
        )
        prompt = (
            "请从以下内容中提取学术证据：\n\n"
            f"## 文献\n{context}\n\n"
        )
        if doc_text:
            prompt += f"## 原始文档\n{doc_text}\n\n"
        prompt += (
            "以 JSON 格式返回：\n"
            "{\n"
            '  "claims": ["核心主张1", ...],\n'
            '  "metrics": [{"name": "指标名", "value": "数值", "source": "来源文献"}, ...],\n'
            '  "methods": ["方法1", ...],\n'
            '  "evidence_snippets": [{"text": "原文证据", "source": "来源"}, ...]\n'
            "}\n\n"
            "重要：metrics 只提取输入中明确出现的数值，没有则返回空数组。"
        )

        result = chat(prompt, system_prompt=system_prompt, temperature=0.3)
        if result is not None:
            parsed, err = extract_json(result)
            if err is None and isinstance(parsed, dict):
                return _normalize_extractor(parsed)
    except ImportError:
        pass

    # ── Mock 模式 ──
    return _mock_extract(lit_results)


def _normalize_extractor(data: dict) -> dict:
    return {
        "claims": data.get("claims", []) if isinstance(data.get("claims"), list) else [],
        "metrics": _safe_list(data.get("metrics", [])),
        "methods": data.get("methods", []) if isinstance(data.get("methods"), list) else [],
        "evidence_snippets": _safe_list(data.get("evidence_snippets", [])),
    }


def _mock_extract(lit_results: list) -> dict:
    claims = []
    metrics = []
    methods = []
    snippets = []

    for lr in lit_results:
        if not isinstance(lr, dict):
            continue
        for f in lr.get("key_findings", []):
            if f:
                claims.append(str(f))
        for m in lr.get("metrics", []):
            if m:
                metrics.append({"name": m, "value": "见原文", "source": lr.get("title", "unknown")})
        cm = lr.get("core_method", "")
        if cm:
            methods.append(str(cm))
        title = lr.get("title", "")
        for f in lr.get("key_findings", []):
            snippets.append({"text": str(f), "source": title})

    return {
        "claims": claims[:10],
        "metrics": metrics[:10],
        "methods": list(set(methods)),
        "evidence_snippets": snippets[:10],
    }


# ═══════════════════════════════════════════════════════════════════
# Critic Agent
# ═══════════════════════════════════════════════════════════════════

def _critic_review(extractor_output: dict, lit_results: list) -> dict:
    """审稿质疑 Extractor 的提取结果。"""

    # ── LLM 模式 ──
    try:
        from utils.llm_client import chat
        from utils.json_parser import extract_json

        claims = extractor_output.get("claims", [])
        methods = extractor_output.get("methods", [])
        metrics = extractor_output.get("metrics", [])
        lit_count = len(lit_results)

        system_prompt = (
            "你是一个严格的学术审稿人。请对提取的学术证据进行批判性审查，"
            "只返回 JSON，不要包含其他内容。"
        )
        prompt = (
            "请审核以下提取结果，指出潜在问题：\n\n"
            f"文献数量：{lit_count}\n"
            f"提取的主张：{json.dumps(claims, ensure_ascii=False)}\n"
            f"提取的方法：{json.dumps(methods, ensure_ascii=False)}\n"
            f"提取的指标：{json.dumps(metrics, ensure_ascii=False)}\n\n"
            "以 JSON 格式返回：\n"
            "{\n"
            '  "critiques": [\n'
            '    {"point": "具体问题", "severity": "high|medium|low", "suggestion": "改进建议"}\n'
            '  ],\n'
            '  "overall_confidence": "high|medium|low"\n'
            "}\n\n"
            "要求：至少 2 条有效质疑。如果输入证据不足，"
            "应说明'输入证据不足，无法提出有效质疑'并解释原因。"
        )

        result = chat(prompt, system_prompt=system_prompt, temperature=0.4)
        if result is not None:
            parsed, err = extract_json(result)
            if err is None and isinstance(parsed, dict):
                critiques = parsed.get("critiques", [])
                if isinstance(critiques, list) and len(critiques) >= 2:
                    return {
                        "critiques": critiques,
                        "overall_confidence": parsed.get("overall_confidence", "medium"),
                    }
    except ImportError:
        pass

    # ── Mock 模式 ──
    return _mock_critic(extractor_output, lit_results)


def _mock_critic(extractor_output: dict, lit_results: list) -> dict:
    critiques = []
    claims = extractor_output.get("claims", [])
    methods = extractor_output.get("methods", [])
    metrics = extractor_output.get("metrics", [])

    if len(lit_results) < 3:
        critiques.append({
            "point": "文献样本量不足（<3 篇），结论的统计显著性存疑",
            "severity": "high",
            "suggestion": "扩大检索范围，纳入更多同行评审文献",
        })
    else:
        critiques.append({
            "point": "文献数量有限，可能存在发表偏倚",
            "severity": "medium",
            "suggestion": "建议包含负面结果和灰色文献以平衡视角",
        })

    if not metrics:
        critiques.append({
            "point": "缺少可验证的定量指标，无法评估结论的效应量",
            "severity": "high",
            "suggestion": "要求每项主要主张附带具体的数值证据",
        })
    else:
        critiques.append({
            "point": "定量指标缺乏误差范围和显著性水平报告",
            "severity": "medium",
            "suggestion": "补充置信区间或 p 值以增强可信度",
        })

    # 方法相关批评
    if len(set(methods)) <= 1 and methods:
        critiques.append({
            "point": f"仅使用 {methods[0]} 单一方法，缺乏多方法交叉验证",
            "severity": "medium",
            "suggestion": "建议结合实验、调查或元分析等多种方法",
        })

    return {
        "critiques": critiques,
        "overall_confidence": "medium" if len(lit_results) >= 3 else "low",
    }


# ═══════════════════════════════════════════════════════════════════
# Synthesizer Agent
# ═══════════════════════════════════════════════════════════════════

def _synthesize_report(extractor_output: dict, critic_output: dict,
                       lit_results: list, t0_output=None) -> str:
    """综合 Extractor 和 Critic 输出，生成最终 Markdown 报告。"""

    # ── LLM 模式 ──
    try:
        from utils.llm_client import chat

        system_prompt = (
            "你是一个学术综述撰写专家。请根据提取的证据和审稿意见，"
            "生成一份完整的 Markdown 学术提炼报告。"
            "不要编造任何未在输入中出现的数据。"
            "所有来自文献的定量指标必须标注来源。"
            "必须区分三类证据：文档中明确出现、由多文献支持、模型推断/待验证。"
        )
        prompt = (
            "请基于以下信息生成学术提炼报告：\n\n"
            f"## 提取的证据\n{json.dumps(extractor_output, ensure_ascii=False, indent=2)}\n\n"
            f"## 审稿意见\n{json.dumps(critic_output, ensure_ascii=False, indent=2)}\n\n"
            f"## 文献元信息\n共 {len(lit_results)} 篇文献（均为模拟生成，不可作为真实引用）\n\n"
            "报告必须包含以下 5 个章节（Markdown 格式）：\n"
            "## 核心共识\n（多文献共同确认的结论，标注支持文献数）\n\n"
            "## 学术冲突\n（文献之间的矛盾或争议点）\n\n"
            "## 方法局限\n（研究方法层面的限制，结合审稿意见）\n\n"
            "## 高价值定量指标\n（关键数据点，每个指标标注来源）\n\n"
            "## 证据与不确定性\n（明确标注每项陈述的证据等级：\n"
            "- 📄 文档中明确出现\n"
            "- 📚 由多文献支持\n"
            "- ⚠️ 模型推断/待验证）\n\n"
            "最后添加声明："
            "> ⚠️ 本文献均为模拟生成（source_type: simulated），不可作为真实学术引用。"
        )

        result = chat(prompt, system_prompt=system_prompt, temperature=0.6)
        if result is not None:
            return result
    except ImportError:
        pass

    # ── Mock 模式 ──
    return _mock_synthesize(extractor_output, critic_output, lit_results)


def _mock_synthesize(extractor_output: dict, critic_output: dict,
                     lit_results: list) -> str:
    claims = extractor_output.get("claims", [])
    methods = extractor_output.get("methods", [])
    metrics = extractor_output.get("metrics", [])
    critiques = critic_output.get("critiques", [])
    confidence = critic_output.get("overall_confidence", "medium")

    lines = ["# 学术提炼报告", ""]

    # 核心共识
    lines.append("## 核心共识")
    lines.append("")
    if claims:
        for c in claims[:5]:
            lines.append(f"- {c}")
        lines.append(f"")
        lines.append(f"> 以上共识由 {len(lit_results)} 篇文献支持（📚 由多文献支持）")
    else:
        lines.append("- 文献数量不足，无法形成核心共识")
    lines.append("")

    # 学术冲突
    lines.append("## 学术冲突")
    lines.append("")
    if len(lit_results) >= 2:
        titles = [lr.get("title", "") for lr in lit_results[:2] if isinstance(lr, dict)]
        if len(titles) >= 2:
            lines.append(f"- 不同文献在方法选择上可能存在分歧：如 {titles[0]} 与 {titles[1]} 采用不同技术路线")
        else:
            lines.append("- 文献间方法差异尚不明确，需要更多比较研究")
    else:
        lines.append("- 文献数量不足以识别学术冲突")
    lines.append("")

    # 方法局限
    lines.append("## 方法局限")
    lines.append("")
    if methods:
        for m in list(set(methods))[:3]:
            lines.append(f"- **{m}**：样本量和泛化性未经验证")
    for cq in critiques[:3]:
        lines.append(f"- {cq.get('point', '')}（严重程度：{cq.get('severity', 'N/A')}）")
    lines.append("")

    # 高价值定量指标
    lines.append("## 高价值定量指标")
    lines.append("")
    if metrics:
        lines.append("| 指标 | 数值 | 来源 |")
        lines.append("| --- | --- | --- |")
        for m in metrics[:10]:
            if isinstance(m, dict):
                lines.append(f"| {m.get('name', 'N/A')} | {m.get('value', 'N/A')} | {m.get('source', 'N/A')} |")
        lines.append("")
        lines.append("> 📄 以上指标提取自输入文献，未做修改")
    else:
        lines.append("- 未在输入中发现可验证的定量指标（⚠️ 模型推断/待验证）")
    lines.append("")

    # 证据与不确定性
    lines.append("## 证据与不确定性")
    lines.append("")
    lines.append("| 证据陈述 | 证据等级 |")
    lines.append("| --- | --- |")
    for c in claims[:3]:
        lines.append(f"| {c} | 📚 由多文献支持 |")
    if methods:
        lines.append(f"| 采用 {methods[0]} 等方法 | 📄 文档中明确出现 |")
    if not metrics:
        lines.append("| 定量指标缺失 | ⚠️ 模型推断/待验证 |")
    lines.append(f"| 综合可信度评估 | {confidence.upper()} |")
    lines.append("")

    # 声明
    lines.append("> ⚠️ 本报告中的文献均为模拟生成（source_type: simulated），不可作为真实学术引用。")
    lines.append("> 所有定量指标应回查原文验证，审稿意见为自动生成，供研究辅助参考。")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════════

def _format_literature_for_prompt(lit_results: list) -> str:
    parts = []
    for i, lr in enumerate(lit_results, 1):
        if not isinstance(lr, dict):
            continue
        parts.append(
            f"[{i}] {lr.get('title', 'Unknown')} "
            f"({', '.join(lr.get('authors', []))}, {lr.get('year', 'N/A')})\n"
            f"  方法: {lr.get('core_method', 'N/A')}\n"
            f"  数据集: {', '.join(lr.get('datasets', [])) or 'N/A'}\n"
            f"  指标: {', '.join(lr.get('metrics', [])) or 'N/A'}\n"
            f"  发现: {'; '.join(lr.get('key_findings', []))}\n"
            f"  局限: {'; '.join(lr.get('limitations', []))}"
        )
    return "\n\n".join(parts)


def _safe_list(val) -> list:
    if isinstance(val, list):
        return val
    return []
