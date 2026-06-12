"""
结构化文献检索任务模块

接受 T1 产出的关键词与学术实体 dict，返回结构化文献候选列表。
提供 LiteratureProvider 接口，支持 Mock 和 LLM 两种 provider，
所有模拟文献必须标注 source_type: "simulated"。
"""

import abc
import json


# ═══════════════════════════════════════════════════════════════════
# LiteratureProvider 接口
# ═══════════════════════════════════════════════════════════════════

class LiteratureProvider(abc.ABC):
    """学术文献检索 provider 抽象接口。"""

    @abc.abstractmethod
    def search(self, query: dict) -> dict:
        """
        检索文献并返回结构化结果。

        参数:
            query: T1 产出的关键词与实体 dict

        返回:
            dict: {"literature_results": [...]}
        """
        ...


class MockLiteratureProvider(LiteratureProvider):
    """Mock provider：基于关键词规则返回固定模拟文献。"""

    def search(self, query: dict) -> dict:
        keywords = query.get("keywords", [])
        entities = query.get("academic_entities", {})
        topic_str = " ".join(str(k) for k in keywords)
        methods = entities.get("methods", [])
        datasets = entities.get("datasets", [])
        metrics = entities.get("metrics", [])

        # 生成 3 条模拟文献
        results = []
        titles = [
            f"Recent Advances in {topic_str.title()}",
            f"A Survey of {topic_str.title()} Methodologies",
            f"Empirical Analysis of {topic_str.title()}",
        ]

        for i, title in enumerate(titles[:3]):
            results.append({
                "title": title,
                "authors": [f"Author {chr(65+i)}", f"Author {chr(68+i)}"],
                "year": 2024 - i,
                "core_method": methods[i % len(methods)] if methods else "unknown",
                "datasets": [datasets[i % len(datasets)]] if datasets else [],
                "metrics": [metrics[i % len(metrics)]] if metrics else [],
                "key_findings": [
                    f"Finding 1 for {title}",
                    f"Finding 2 for {title}",
                ],
                "limitations": ["Limited sample size", "Single domain evaluation"],
                "source_type": "simulated",
                "url": None,
            })

        return {"literature_results": results}


class LLMSimulatedProvider(LiteratureProvider):
    """LLM provider：调用大语言模型生成模拟文献条目。"""

    def search(self, query: dict) -> dict:
        from utils.llm_client import chat
        from utils.json_parser import extract_json

        keywords = query.get("keywords", [])
        entities = query.get("academic_entities", {})
        topic_str = " ".join(str(k) for k in keywords)

        system_prompt = (
            "你是一个学术文献检索助手。请只返回 JSON，不要包含其他内容。"
        )
        prompt = (
            f"请根据以下信息生成 3-5 条模拟学术文献条目，以 JSON 格式返回。\n\n"
            f"主题关键词：{topic_str}\n"
            f"学术实体：{json.dumps(entities, ensure_ascii=False)}\n\n"
            "JSON schema：\n"
            '{\n'
            '  "literature_results": [\n'
            '    {\n'
            '      "title": "论文标题",\n'
            '      "authors": ["作者1", "作者2"],\n'
            '      "year": 2024,\n'
            '      "core_method": "核心方法",\n'
            '      "datasets": ["数据集"],\n'
            '      "metrics": ["指标"],\n'
            '      "key_findings": ["发现1", "发现2"],\n'
            '      "limitations": ["局限1"],\n'
            '      "source_type": "simulated",\n'
            '      "url": null\n'
            '    }\n'
            '  ]\n'
            "}\n\n"
            "注意：每条文献的 source_type 必须为 \"simulated\"。"
        )

        result = chat(prompt, system_prompt=system_prompt, temperature=0.5)

        if result is not None:
            parsed, err = extract_json(result)
            if err is None and isinstance(parsed, dict):
                return _normalize_results(parsed)

        # LLM 解析失败，回退到 Mock
        return MockLiteratureProvider().search(query)


def _normalize_results(data: dict) -> dict:
    """规范化文献结果，确保每条记录包含必要字段。"""
    results = data.get("literature_results", [])
    if not isinstance(results, list):
        results = []
    normalized = []
    for r in results:
        if not isinstance(r, dict):
            continue
        normalized.append({
            "title": str(r.get("title", "Unknown")),
            "authors": r.get("authors", []) if isinstance(r.get("authors"), list) else [],
            "year": r.get("year") if isinstance(r.get("year"), int) else None,
            "core_method": str(r.get("core_method", "")),
            "datasets": r.get("datasets", []) if isinstance(r.get("datasets"), list) else [],
            "metrics": r.get("metrics", []) if isinstance(r.get("metrics"), list) else [],
            "key_findings": r.get("key_findings", []) if isinstance(r.get("key_findings"), list) else [],
            "limitations": r.get("limitations", []) if isinstance(r.get("limitations"), list) else [],
            "source_type": "simulated",
            "url": r.get("url"),
        })
    return {"literature_results": normalized}


# ═══════════════════════════════════════════════════════════════════
# Provider 工厂
# ═══════════════════════════════════════════════════════════════════

def _get_provider() -> LiteratureProvider:
    """根据 API Key 是否配置，返回 LLM 或 Mock provider。"""
    import os
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if api_key:
        try:
            return LLMSimulatedProvider()
        except Exception:
            pass
    return MockLiteratureProvider()


# ═══════════════════════════════════════════════════════════════════
# 任务入口
# ═══════════════════════════════════════════════════════════════════

def run(t1_output: dict) -> dict:
    """
    根据 T1 产出的关键词与学术实体进行文献检索。

    参数:
        t1_output: T1 任务产出的 dict

    返回:
        dict: {
            "literature_results": [
                {title, authors, year, core_method, datasets, metrics,
                 key_findings, limitations, source_type, url}
            ]
        }
    """
    # 兼容旧调用（关键词列表）
    if isinstance(t1_output, (list, str)):
        t1_output = {"keywords": list(t1_output) if isinstance(t1_output, list) else [str(t1_output)],
                      "academic_entities": {}}

    provider = _get_provider()
    return provider.search(t1_output)
