"""Structured policy impact extraction with strict evidence gating."""

from __future__ import annotations

import json

POLICY_FIELDS = (
    "policy_name", "issuing_body", "effective_date", "scope",
    "affected_parties", "compliance_requirements", "risk_level",
)


def run(topic: str, t2_output: dict, document: dict | None = None) -> dict:
    literature = t2_output.get("literature_results", []) if isinstance(t2_output, dict) else []
    provider = t2_output.get("provider", "unknown") if isinstance(t2_output, dict) else "unknown"

    if provider in ("mock", "llm-simulated"):
        return {
            "status": "ok",
            "warnings": ["政策评估为显式 Mock 演示，不可作为合规依据。"],
            "policies": [_mock_policy(topic, literature)],
        }

    evidence = _policy_evidence(literature, document)
    if not evidence:
        return _empty("未找到可引用的政策原文或政策记录，请补充权威来源。")

    try:
        from noteforge.json_tools import extract_json
        from noteforge.llm import chat

        prompt = (
            "请仅从证据中提取明确出现的政策事实，只返回 JSON。"
            "政策名称、发布机构和 evidence_ids 缺一不可；不得根据常识补全日期或要求。\n\n"
            f"主题：{topic}\n证据：{json.dumps(evidence, ensure_ascii=False)}\n\n"
            "格式：{\"policies\":[{\"policy_name\":\"\",\"issuing_body\":\"\","
            "\"effective_date\":\"\",\"scope\":\"\",\"affected_parties\":[],"
            "\"compliance_requirements\":[],\"risk_level\":\"unknown\","
            "\"evidence_ids\":[\"D1\"]}]}"
        )
        raw = chat(
            prompt,
            system_prompt="你是合规证据提取器。证据不足时返回空 policies。",
            temperature=0.1,
        )
        if raw is not None:
            parsed, error = extract_json(raw)
            if error is None and isinstance(parsed, dict):
                policies = _normalize_policies(parsed.get("policies", []), evidence)
                if policies:
                    return {"status": "ok", "warnings": [], "policies": policies}
    except ImportError:
        pass

    return _empty("政策证据存在，但未能提取出同时包含名称、机构和引用的记录。")


def _empty(warning: str) -> dict:
    return {"status": "insufficient_evidence", "warnings": [warning], "policies": []}


def _policy_evidence(literature: list, document: dict | None) -> list[dict]:
    markers = ("policy", "regulation", "law", "standard", "政策", "法规", "条例", "标准")
    evidence = []
    for item in literature:
        if not isinstance(item, dict):
            continue
        text = f"{item.get('title', '')} {item.get('abstract', '')}".strip()
        if text and any(marker in text.casefold() for marker in markers):
            evidence.append({
                "source_id": item.get("source_id"),
                "title": item.get("title"),
                "text": text[:4000],
                "source_type": item.get("source_type", "unverified"),
            })
    if isinstance(document, dict):
        text = str(document.get("markdown_text") or document.get("raw_text") or "").strip()
        if text and any(marker in text.casefold() for marker in markers):
            evidence.append({
                "source_id": "D1",
                "title": document.get("metadata", {}).get("file_name", "source document"),
                "text": text[:8000],
                "source_type": "source_document",
            })
    return evidence


def _normalize_policies(raw_policies, evidence: list[dict]) -> list[dict]:
    if not isinstance(raw_policies, list):
        return []
    valid_ids = {str(item.get("source_id")) for item in evidence if item.get("source_id")}
    normalized = []
    for raw in raw_policies:
        if not isinstance(raw, dict):
            continue
        evidence_ids = [
            str(value) for value in raw.get("evidence_ids", [])
            if str(value) in valid_ids
        ] if isinstance(raw.get("evidence_ids"), list) else []
        policy_name = str(raw.get("policy_name", "")).strip()
        issuing_body = str(raw.get("issuing_body", "")).strip()
        if not policy_name or not issuing_body or not evidence_ids:
            continue
        item = {field: _field_value(raw.get(field), field) for field in POLICY_FIELDS}
        item["risk_level"] = item["risk_level"] if item["risk_level"] in {
            "low", "medium", "high", "unknown"
        } else "unknown"
        item.update({
            "evidence_ids": evidence_ids,
            "source_type": "llm_inference",
            "verification_status": "supported",
        })
        normalized.append(item)
    return normalized


def _field_value(value, field: str):
    if field in ("affected_parties", "compliance_requirements"):
        return [str(item) for item in value if str(item).strip()] if isinstance(value, list) else []
    return str(value or "").strip()


def _mock_policy(topic: str, literature: list) -> dict:
    source_id = "L1"
    if literature and isinstance(literature[0], dict):
        source_id = literature[0].get("source_id", source_id)
    return {
        "policy_name": f"Simulated policy for {topic}",
        "issuing_body": "Simulated authority",
        "effective_date": "unverified",
        "scope": topic,
        "affected_parties": ["Simulated stakeholders"],
        "compliance_requirements": ["Simulation only; obtain an authoritative policy source"],
        "risk_level": "unknown",
        "evidence_ids": [source_id],
        "source_type": "simulated",
        "verification_status": "simulated",
    }
