"""T4: assemble the final evidence-aware Markdown report."""

from __future__ import annotations


def run(topic: str, t3_output, t5_output: dict | None = None,
        t6_output: dict | None = None, sources: list[dict] | None = None,
        warnings: list[str] | None = None) -> str:
    if isinstance(t3_output, str):
        t3_output = {"final_report": t3_output}
    t3_output = t3_output if isinstance(t3_output, dict) else {}
    t5_output = t5_output if isinstance(t5_output, dict) else {}
    t6_output = t6_output if isinstance(t6_output, dict) else {}
    sources = list(sources or [])
    warnings = _deduplicate(list(warnings or []))

    lines = [f"# {topic} 研究报告", "", _mode_banner(sources), ""]
    lines.extend(["## 学术提炼", ""])
    summary = str(t3_output.get("final_report", "")).strip()
    lines.append(summary or "证据不足，无法形成可验证的学术提炼结论。")
    lines.extend(["", "## 技术案例", ""])
    lines.extend(_render_cases(t5_output.get("cases", [])))
    lines.extend(["", "## 政策影响", ""])
    lines.extend(_render_policies(t6_output.get("policies", [])))
    lines.extend(["", "## 数据来源", ""])
    lines.extend(_render_sources(sources))

    all_warnings = _deduplicate(
        warnings
        + list(t3_output.get("warnings", []))
        + list(t5_output.get("warnings", []))
        + list(t6_output.get("warnings", []))
    )
    if all_warnings:
        lines.extend(["", "## 告警与边界", ""])
        lines.extend(f"- {warning}" for warning in all_warnings)
    lines.extend([
        "",
        "> 本报告由自动化流水线生成。LLM 推断、模拟数据及未验证信息均已单独标记；重要结论必须回查原始来源。",
        "",
    ])
    return "\n".join(lines)


def _mode_banner(sources: list[dict]) -> str:
    types = {str(item.get("source_type", "unverified")) for item in sources}
    if "simulated" in types and "external_api" in types:
        mode = "混合来源（真实检索 + 模拟数据）"
    elif "simulated" in types and "source_document" in types:
        mode = "混合来源（原始文档 + 模拟数据）"
    elif "simulated" in types:
        mode = "显式模拟模式"
    elif "external_api" in types:
        mode = "真实外部检索"
    elif "source_document" in types:
        mode = "原始文档分析"
    else:
        mode = "证据不足"
    return f"> 数据模式：**{mode}**"


def _render_cases(cases) -> list[str]:
    if not isinstance(cases, list) or not cases:
        return ["未提取到具有可追溯证据的技术案例。"]
    lines = []
    for index, case in enumerate(cases, 1):
        refs = ", ".join(f"[{item}]" for item in case.get("evidence_ids", [])) or "无"
        lines.extend([
            f"### {index}. {case.get('case_name', '未命名案例')}", "",
            f"- 使用场景：{case.get('use_scenario') or '未提供'}",
            f"- 技术路线：{case.get('technical_route') or '未提供'}",
            f"- 输入：{_join(case.get('inputs'))}",
            f"- 输出：{_join(case.get('outputs'))}",
            f"- 实施条件：{_join(case.get('implementation_conditions'))}",
            f"- 限制：{_join(case.get('limitations'))}",
            f"- 证据：{refs}；状态：{case.get('verification_status', 'unverified')}", "",
        ])
    return lines[:-1]


def _render_policies(policies) -> list[str]:
    if not isinstance(policies, list) or not policies:
        return ["未发现可引用的权威政策记录；本报告不生成事实性政策结论。"]
    lines = []
    for index, policy in enumerate(policies, 1):
        refs = ", ".join(f"[{item}]" for item in policy.get("evidence_ids", [])) or "无"
        lines.extend([
            f"### {index}. {policy.get('policy_name', '未命名政策')}", "",
            f"- 发布机构：{policy.get('issuing_body') or '未提供'}",
            f"- 生效时间：{policy.get('effective_date') or '未提供'}",
            f"- 适用范围：{policy.get('scope') or '未提供'}",
            f"- 影响对象：{_join(policy.get('affected_parties'))}",
            f"- 合规要求：{_join(policy.get('compliance_requirements'))}",
            f"- 风险等级：{policy.get('risk_level', 'unknown')}",
            f"- 证据：{refs}；状态：{policy.get('verification_status', 'unverified')}", "",
        ])
    return lines[:-1]


def _render_sources(sources: list[dict]) -> list[str]:
    if not sources:
        return ["- 无可用来源。"]
    lines = []
    for source in sources:
        source_id = source.get("source_id", "?")
        title = source.get("title", "Unknown")
        provider = source.get("source_provider", "unknown")
        source_type = source.get("source_type", "unverified")
        doi = source.get("doi")
        url = source.get("url")
        suffix = f" DOI: {doi}." if doi else ""
        if url:
            suffix += f" {url}"
        lines.append(f"- [{source_id}] {title} — {provider}/{source_type}.{suffix}".rstrip())
    return lines


def _join(value) -> str:
    if isinstance(value, list):
        return "；".join(str(item) for item in value if str(item).strip()) or "未提供"
    return str(value or "未提供")


def _deduplicate(values: list) -> list[str]:
    result = []
    for value in values:
        text = str(value).strip()
        if text and text not in result:
            result.append(text)
    return result
