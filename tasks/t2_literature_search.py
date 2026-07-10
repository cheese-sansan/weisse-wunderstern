"""T2: evidence-aware literature retrieval providers.

Crossref is the default real provider. Mock and LLM-generated records remain
available only when explicitly selected and are always labelled ``simulated``.
"""

from __future__ import annotations

import abc
import html
import json
import os
import re
import socket
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_PROVIDER = "crossref"
PROVIDER_NAMES = ("crossref", "mock", "llm-simulated")
CROSSREF_API_URL = "https://api.crossref.org/works"
EXCLUDED_CROSSREF_TYPES = {"component", "reference-entry", "journal-issue", "journal-volume"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _env_int(name: str, default: int, minimum: int = 1, maximum: int = 100) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


def _query_text(query: dict) -> str:
    """Build a stable, compact bibliographic query from T1 output."""
    values = []
    entities = query.get("academic_entities", {}) if isinstance(query, dict) else {}
    for group in (
        query.get("keywords", []) if isinstance(query, dict) else [],
        entities.get("methods", []) if isinstance(entities, dict) else [],
        entities.get("domains", []) if isinstance(entities, dict) else [],
    ):
        if not isinstance(group, list):
            continue
        for item in group:
            text = str(item).strip()
            if text and text.casefold() not in {v.casefold() for v in values}:
                values.append(text)
            if len(values) >= 8:
                return " ".join(values)
    return " ".join(values)


def _result_envelope(provider: str, query: str, results: list, *,
                     status: str = "ok", warnings: list[str] | None = None,
                     retrieved_at: str | None = None) -> dict:
    return {
        "provider": provider,
        "query": query,
        "status": status,
        "retrieved_at": retrieved_at or _now_iso(),
        "warnings": list(warnings or []),
        "literature_results": results,
    }


def _empty_record(*, title: str, authors: list | None = None,
                  year: int | None = None, doi: str | None = None,
                  url: str | None = None, abstract: str = "",
                  source_provider: str, source_type: str,
                  source_id: str, retrieved_at: str) -> dict:
    """Return the v0.2 record shape plus legacy analysis fields."""
    return {
        "source_id": source_id,
        "title": title or "Unknown",
        "authors": list(authors or []),
        "year": year,
        "doi": doi,
        "url": url,
        "abstract": abstract or "",
        "source_provider": source_provider,
        "source_type": source_type,
        "retrieved_at": retrieved_at,
        # Compatibility fields. Real providers do not fabricate these values.
        "core_method": "",
        "datasets": [],
        "metrics": [],
        "key_findings": [],
        "limitations": [],
    }


class LiteratureProvider(abc.ABC):
    """Stable extension point for literature retrieval backends."""

    name = "unknown"

    @abc.abstractmethod
    def search(self, query: dict) -> dict:
        """Return a v0.2 result envelope containing normalized records."""
        raise NotImplementedError


class MockLiteratureProvider(LiteratureProvider):
    """Deterministic offline provider for tests and demonstrations."""

    name = "mock"

    def search(self, query: dict) -> dict:
        text = _query_text(query) or "research topic"
        entities = query.get("academic_entities", {}) if isinstance(query, dict) else {}
        methods = entities.get("methods", []) if isinstance(entities, dict) else []
        datasets = entities.get("datasets", []) if isinstance(entities, dict) else []
        metrics = entities.get("metrics", []) if isinstance(entities, dict) else []
        retrieved_at = _now_iso()
        titles = [
            f"Recent Advances in {text.title()}",
            f"A Survey of {text.title()} Methodologies",
            f"Empirical Analysis of {text.title()}",
        ]
        results = []
        for index, title in enumerate(titles, 1):
            record = _empty_record(
                title=title,
                authors=[f"Author {chr(64 + index)}", f"Author {chr(67 + index)}"],
                year=2025 - index,
                source_provider=self.name,
                source_type="simulated",
                source_id=f"L{index}",
                retrieved_at=retrieved_at,
            )
            record.update({
                "core_method": methods[(index - 1) % len(methods)] if methods else "unknown",
                "datasets": [datasets[(index - 1) % len(datasets)]] if datasets else [],
                "metrics": [metrics[(index - 1) % len(metrics)]] if metrics else [],
                "key_findings": [
                    f"Simulated finding 1 for {title}",
                    f"Simulated finding 2 for {title}",
                ],
                "limitations": ["Simulated record; not a real citation"],
            })
            results.append(record)
        return _result_envelope(self.name, text, results, retrieved_at=retrieved_at)


class LLMSimulatedProvider(LiteratureProvider):
    """LLM-generated provider; its output is never treated as retrieval."""

    name = "llm-simulated"

    def search(self, query: dict) -> dict:
        from utils.llm_client import chat
        from utils.json_parser import extract_json

        query_text = _query_text(query) or "research topic"
        entities = query.get("academic_entities", {}) if isinstance(query, dict) else {}
        prompt = (
            "请生成 3-5 条用于界面演示的模拟学术记录，只返回 JSON。"
            "这些记录不是真实检索结果。\n\n"
            f"主题：{query_text}\n"
            f"实体：{json.dumps(entities, ensure_ascii=False)}\n\n"
            "格式：{\"literature_results\":[{\"title\":\"\",\"authors\":[],"
            "\"year\":2025,\"abstract\":\"\",\"core_method\":\"\","
            "\"datasets\":[],\"metrics\":[],\"key_findings\":[],"
            "\"limitations\":[]}]}"
        )
        result = chat(
            prompt,
            system_prompt="你生成的内容仅用于模拟演示，不得声称是真实文献。",
            temperature=0.5,
        )
        if result is not None:
            parsed, error = extract_json(result)
            if error is None and isinstance(parsed, dict):
                return _normalize_results(parsed, provider=self.name, query=query_text)
        fallback = MockLiteratureProvider().search(query)
        fallback["provider"] = self.name
        fallback["warnings"].append("LLM 模拟结果解析失败，已使用本地 Mock 数据。")
        for item in fallback["literature_results"]:
            item["source_provider"] = self.name
        return fallback


class CrossrefLiteratureProvider(LiteratureProvider):
    """Real Crossref REST API provider with bounded retry and timeout."""

    name = "crossref"

    def __init__(self, *, max_results: int | None = None,
                 timeout: int | None = None, opener=None, sleeper=None):
        self.max_results = max_results or _env_int("LITERATURE_MAX_RESULTS", 10, 1, 100)
        self.timeout = timeout or _env_int("LITERATURE_TIMEOUT_SECONDS", 10, 1, 60)
        self._opener = opener or urlopen
        self._sleep = sleeper or time.sleep

    def search(self, query: dict) -> dict:
        query_text = _query_text(query)
        if not query_text:
            return _result_envelope(
                self.name, "", [], status="degraded",
                warnings=["没有可用于文献检索的关键词。"],
            )

        params = urlencode({
            "query.bibliographic": query_text,
            "rows": min(self.max_results * 3, 100),
            "select": "DOI,title,author,published-print,published-online,created,URL,abstract,type",
        })
        request = Request(
            f"{CROSSREF_API_URL}?{params}",
            headers={"Accept": "application/json", "User-Agent": self._user_agent()},
        )

        for attempt in range(2):
            try:
                with self._opener(request, timeout=self.timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                items = payload.get("message", {}).get("items", [])
                if not isinstance(items, list):
                    raise ValueError("Crossref 响应中缺少 items 列表")
                retrieved_at = _now_iso()
                usable_items = [
                    item for item in items
                    if isinstance(item, dict)
                    and str(item.get("type", "")).casefold() not in EXCLUDED_CROSSREF_TYPES
                ]
                results = [
                    _normalize_crossref_item(item, index, retrieved_at)
                    for index, item in enumerate(usable_items[:self.max_results], 1)
                ]
                warnings = [] if results else ["Crossref 未返回匹配的文献记录。"]
                return _result_envelope(
                    self.name, query_text, results,
                    warnings=warnings, retrieved_at=retrieved_at,
                )
            except HTTPError as error:
                retryable = error.code == 429 or 500 <= error.code < 600
                if attempt == 0 and retryable:
                    self._sleep(_retry_delay(error))
                    continue
                return self._degraded(query_text, f"Crossref HTTP {error.code}")
            except (URLError, TimeoutError, socket.timeout) as error:
                if attempt == 0:
                    self._sleep(0.5)
                    continue
                return self._degraded(query_text, f"Crossref 网络错误：{_safe_error(error)}")
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
                return self._degraded(query_text, f"Crossref 响应无法解析：{_safe_error(error)}")

        return self._degraded(query_text, "Crossref 检索失败。")

    def _user_agent(self) -> str:
        mailto = os.environ.get("CROSSREF_MAILTO", "").strip()
        contact = f"; mailto:{mailto}" if mailto else ""
        return f"NoteForge/0.2.0 (https://github.com/cheese-sansan/noteforge{contact})"

    def _degraded(self, query_text: str, warning: str) -> dict:
        return _result_envelope(
            self.name, query_text, [], status="degraded", warnings=[warning],
        )


def _safe_error(error: Exception) -> str:
    reason = getattr(error, "reason", error)
    return str(reason)[:200]


def _retry_delay(error: HTTPError) -> float:
    try:
        value = float(error.headers.get("Retry-After", "0.5"))
    except (AttributeError, TypeError, ValueError):
        value = 0.5
    return max(0.0, min(value, 5.0))


def _first_text(value) -> str:
    if isinstance(value, list) and value:
        return str(value[0]).strip()
    return str(value or "").strip()


def _crossref_year(item: dict) -> int | None:
    for key in ("published-print", "published-online", "created"):
        parts = item.get(key, {}).get("date-parts", [])
        if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0]:
            try:
                return int(parts[0][0])
            except (TypeError, ValueError):
                continue
    return None


def _clean_abstract(value) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _normalize_crossref_item(item: dict, index: int, retrieved_at: str) -> dict:
    authors = []
    for author in item.get("author", []) if isinstance(item.get("author"), list) else []:
        if not isinstance(author, dict):
            continue
        name = " ".join(
            part for part in (str(author.get("given", "")).strip(),
                              str(author.get("family", "")).strip()) if part
        )
        if name:
            authors.append(name)
    doi = str(item.get("DOI", "")).strip() or None
    url = str(item.get("URL", "")).strip() or (f"https://doi.org/{doi}" if doi else None)
    return _empty_record(
        title=_clean_abstract(_first_text(item.get("title"))) or "Unknown",
        authors=authors,
        year=_crossref_year(item),
        doi=doi,
        url=url,
        abstract=_clean_abstract(item.get("abstract")),
        source_provider="crossref",
        source_type="external_api",
        source_id=f"L{index}",
        retrieved_at=retrieved_at,
    )


def _normalize_results(data: dict, *, provider: str = "llm-simulated",
                       query: str = "") -> dict:
    """Normalize simulated/legacy provider output into the v0.2 contract."""
    raw_results = data.get("literature_results", []) if isinstance(data, dict) else []
    if not isinstance(raw_results, list):
        raw_results = []
    retrieved_at = _now_iso()
    normalized = []
    for index, raw in enumerate(raw_results, 1):
        if not isinstance(raw, dict):
            continue
        record = _empty_record(
            title=str(raw.get("title", "Unknown")),
            authors=raw.get("authors", []) if isinstance(raw.get("authors"), list) else [],
            year=raw.get("year") if isinstance(raw.get("year"), int) else None,
            doi=str(raw.get("doi", "")).strip() or None,
            url=str(raw.get("url", "")).strip() or None,
            abstract=str(raw.get("abstract", "")),
            source_provider=provider,
            source_type="simulated",
            source_id=f"L{index}",
            retrieved_at=retrieved_at,
        )
        for key, default in (
            ("core_method", ""), ("datasets", []), ("metrics", []),
            ("key_findings", []), ("limitations", []),
        ):
            value = raw.get(key, default)
            if isinstance(default, list) and not isinstance(value, list):
                value = []
            record[key] = value
        normalized.append(record)
    return _result_envelope(provider, query, normalized, retrieved_at=retrieved_at)


def _get_provider(provider_name: str | None = None) -> LiteratureProvider:
    name = (provider_name or os.environ.get("LITERATURE_PROVIDER", DEFAULT_PROVIDER)).strip().lower()
    name = name.replace("_", "-")
    if name == "crossref":
        return CrossrefLiteratureProvider()
    if name == "mock":
        return MockLiteratureProvider()
    if name in ("llm", "llm-simulated"):
        return LLMSimulatedProvider()
    raise ValueError(
        f"不支持的文献 Provider '{name}'；可选值: {', '.join(PROVIDER_NAMES)}"
    )


def run(t1_output: dict, provider: str | None = None) -> dict:
    """Run literature retrieval with the selected explicit provider."""
    if isinstance(t1_output, (list, str)):
        t1_output = {
            "keywords": list(t1_output) if isinstance(t1_output, list) else [str(t1_output)],
            "academic_entities": {},
        }
    if not isinstance(t1_output, dict):
        t1_output = {"keywords": [], "academic_entities": {}}
    return _get_provider(provider).search(t1_output)
