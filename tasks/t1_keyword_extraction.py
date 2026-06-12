"""
关键词与学术实体抽取任务模块

从主题文本中提取关键词和学术实体（methods, datasets, metrics, tasks, domains, relations）。
LLM 和 Mock 模式均返回同构 dict schema。
"""

import json


def run(topic: str) -> dict:
    """
    从给定主题中提取关键词与学术实体。

    返回:
        dict: {
            "keywords": list[str],
            "academic_entities": {
                "methods": list[str],
                "datasets": list[str],
                "metrics": list[str],
                "tasks": list[str],
                "domains": list[str],
                "relations": list[dict],
            }
        }
    """
    # ── LLM 增强模式 ──
    try:
        from utils.llm_client import chat
        from utils.json_parser import extract_json

        system_prompt = (
            "你是一个学术实体抽取助手。请只返回 JSON，不要包含其他内容。"
        )
        prompt = (
            f"请从以下主题中提取关键词和学术实体，以 JSON 格式返回。\n\n"
            f"主题：{topic}\n\n"
            "JSON schema：\n"
            "{\n"
            '  "keywords": ["关键词1", "关键词2", ...],\n'
            '  "academic_entities": {\n'
            '    "methods": ["方法1", ...],\n'
            '    "datasets": ["数据集1", ...],\n'
            '    "metrics": ["指标1", ...],\n'
            '    "tasks": ["任务1", ...],\n'
            '    "domains": ["领域1", ...],\n'
            '    "relations": [\n'
            '      {"source": "实体A", "relation": "关系", "target": "实体B"}\n'
            '    ]\n'
            '  }\n'
            "}\n\n"
            "注意：如果无法从主题中提取某个字段，返回空数组 []。"
        )

        result = chat(prompt, system_prompt=system_prompt, temperature=0.3)

        if result is not None:
            parsed, err = extract_json(result)
            if err is None and isinstance(parsed, dict):
                return _normalize(parsed)
    except ImportError:
        pass

    # ── Mock 回退模式 ──
    return _mock_extract(topic)


def _normalize(data: dict) -> dict:
    """规范化并补全字段。"""
    result = {
        "keywords": data.get("keywords", []),
        "academic_entities": {},
    }
    entities = data.get("academic_entities", {})
    if not isinstance(entities, dict):
        entities = {}
    for field in ("methods", "datasets", "metrics", "tasks", "domains"):
        val = entities.get(field, [])
        if isinstance(val, list):
            val = [str(v) for v in val]
        else:
            val = []
        result["academic_entities"][field] = val
    relations = entities.get("relations", [])
    if isinstance(relations, list):
        result["academic_entities"]["relations"] = [
            r for r in relations if isinstance(r, dict)
        ]
    else:
        result["academic_entities"]["relations"] = []
    return result


def _mock_extract(topic: str) -> dict:
    """Mock 模式：基于简单规则提取关键词和实体。"""
    words = [w for w in topic.split() if len(w) >= 2][:5]
    if not words:
        words = [topic]

    # 常见学术术语快速检测
    method_keywords = {
        "transformer", "cnn", "rnn", "lstm", "bert", "gpt", "diffusion",
        "reinforcement learning", "gan", "vae", "attention", "fine-tuning",
        "pretrain", "pretraining", "pre-train", "pre-training",
    }
    dataset_keywords = {
        "imagenet", "coco", "mnist", "cifar", "squad", "mmlu",
        "glue", "superglue", "wikitext", "openwebtext",
    }
    metric_keywords = {
        "accuracy", "f1", "bleu", "rouge", "perplexity", "auc",
        "recall", "precision", "mae", "mse", "rmse",
    }
    task_keywords = {
        "classification", "detection", "segmentation", "translation",
        "summarization", "generation", "qa", "ner", "sentiment",
    }
    domain_keywords = {
        "nlp", "cv", "computer vision", "speech", "robotics",
        "medical", "finance", "legal", "biology",
    }

    topic_lower = topic.lower()
    methods = [k for k in method_keywords if k in topic_lower]
    datasets = [k for k in dataset_keywords if k in topic_lower]
    metrics = [k for k in metric_keywords if k in topic_lower]
    tasks = [k for k in task_keywords if k in topic_lower]
    domains = [k for k in domain_keywords if k in topic_lower]

    return {
        "keywords": words,
        "academic_entities": {
            "methods": methods,
            "datasets": datasets,
            "metrics": metrics,
            "tasks": tasks,
            "domains": domains,
            "relations": [],
        },
    }
