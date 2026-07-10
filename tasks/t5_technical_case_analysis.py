"""T5: structured technical case extraction with evidence references."""

from __future__ import annotations

import json


CASE_FIELDS = (
    "case_name", "use_scenario", "technical_route", "inputs", "outputs",
    "implementation_conditions", "limitations",
)


def run(topic: str, t2_output: dict, t3_output: dict | None = None,
        document: dict | None = None) -> dict:
    literature = t2_output.get("literature_results", []) if isinstance(t2_output, dict) else []
    provider = t2_output.get("provider", "unknown") if isinstance(t2_output, dict) else "unknown"

    if provider in ("mock", "llm-simulated"):
        cases = [_mock_case(item, index) for index, item in enumerate(literature[:3], 1)]
        return {
            "status": "ok" if cases else "insufficient_evidence",
            "warnings": [] if cases else ["没有可用于模拟技术案例的记录。"],
            "cases": cases,
        }

    evidence = _evidence_payload(literature, document)
    if not evidence:
        return _empty("未发现包含摘要或原始文档内容的技术案例证据。")

    try:
        from utils.llm_client import chat
        from utils.json_parser import extract_json

        prompt = (
            "请仅从给定证据中提取技术实施案例，只返回 JSON。"
            "不得根据常识补全；每个案例必须给出 evidence_ids。\n\n"
            f"主题：{topic}\n证据：{json.dumps(evidence, ensure_ascii=False)}\n\n"
            "格式：{\"cases\":[{\"case_name\":\"\",\"use_scenario\":\"\","
            "\"technical_route\":\"\",\"inputs\":[],\"outputs\":[],"
            "\"implementation_conditions\":[],\"limitations\":[],"
            "\"evidence_ids\":[\"L1\"]}]}"
        )
        raw = chat(
            prompt,
            system_prompt="你是严格的证据提取器。缺少证据时返回空 cases。",
            temperature=0.2,
        )
        if raw is not None:
            parsed, error = extract_json(raw)
            if error is None and isinstance(parsed, dict):
                cases = _normalize_cases(parsed.get("cases", []), evidence)
                if cases:
                    return {"status": "ok", "warnings": [], "cases": cases}
    except ImportError:
        pass

    return _empty("现有证据需要 LLM 提取；当前未获得可验证的结构化技术案例。")


def _empty(warning: str) -> dict:
    return {"status": "insufficient_evidence", "warnings": [warning], "cases": []}


def _evidence_payload(literature: list, document: dict | None) -> list[dict]:
    evidence = []
    for item in literature:
        if not isinstance(item, dict):
            continue
        abstract = str(item.get("abstract", "")).strip()
        findings = item.get("key_findings", [])
        text = abstract or "; ".join(str(value) for value in findings if value)
        if text:
            evidence.append({
                "source_id": item.get("source_id"),
                "title": item.get("title"),
                "text": text[:4000],
                "source_type": item.get("source_type", "unverified"),
            })
    if isinstance(document, dict):
        text = str(document.get("markdown_text") or document.get("raw_text") or "").strip()
        if text:
            evidence.append({
                "source_id": "D1",
                "title": document.get("metadata", {}).get("file_name", "source document"),
                "text": text[:6000],
                "source_type": "source_document",
            })
    return evidence


def _normalize_cases(raw_cases, evidence: list[dict]) -> list[dict]:
    if not isinstance(raw_cases, list):
        return []
    valid_ids = {str(item.get("source_id")) for item in evidence if item.get("source_id")}
    normalized = []
    for raw in raw_cases:
        if not isinstance(raw, dict):
            continue
        evidence_ids = [
            str(value) for value in raw.get("evidence_ids", [])
            if str(value) in valid_ids
        ] if isinstance(raw.get("evidence_ids"), list) else []
        case_name = str(raw.get("case_name", "")).strip()
        if not case_name or not evidence_ids:
            continue
        item = {field: _field_value(raw.get(field), field) for field in CASE_FIELDS}
        item.update({
            "evidence_ids": evidence_ids,
            "source_type": "llm_inference",
            "verification_status": "supported",
        })
        normalized.append(item)
    return normalized


def _field_value(value, field: str):
    if field in ("inputs", "outputs", "implementation_conditions", "limitations"):
        return [str(item) for item in value if str(item).strip()] if isinstance(value, list) else []
    return str(value or "").strip()


def _mock_case(item: dict, index: int) -> dict:
    title = str(item.get("title", f"Simulated case {index}"))
    method = str(item.get("core_method", "unknown"))
    return {
        "case_name": title,
        "use_scenario": f"Simulated scenario for {title}",
        "technical_route": method,
        "inputs": list(item.get("datasets", [])),
        "outputs": list(item.get("metrics", [])),
        "implementation_conditions": ["Simulation only; verify against a real source"],
        "limitations": list(item.get("limitations", [])) or ["Simulated evidence"],
        "evidence_ids": [item.get("source_id", f"L{index}")],
        "source_type": "simulated",
        "verification_status": "simulated",
    }
