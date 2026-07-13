"""Typed real and simulated literature providers."""

from __future__ import annotations

import abc
import html
import json
import os
import re
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from noteforge.models import (
    LiteratureQuery,
    LiteratureRecord,
    LiteratureSearchResult,
    ProviderName,
    ProviderStatus,
    SourceType,
)

DEFAULT_PROVIDER = ProviderName.CROSSREF.value
PROVIDER_NAMES = tuple(item.value for item in ProviderName)
CROSSREF_API_URL = "https://api.crossref.org/works"
EXCLUDED_CROSSREF_TYPES = {"component", "reference-entry", "journal-issue", "journal-volume"}


class LiteratureProvider(abc.ABC):
    """Stable public provider contract."""

    name = "unknown"

    @abc.abstractmethod
    def search(self, query: LiteratureQuery) -> LiteratureSearchResult:
        raise NotImplementedError


class MockLiteratureProvider(LiteratureProvider):
    name = ProviderName.MOCK.value

    def search(self, query: LiteratureQuery) -> LiteratureSearchResult:
        text = _query_text(query) or "research topic"
        retrieved_at = _now_iso()
        titles = (
            f"Recent Advances in {text.title()}",
            f"A Survey of {text.title()} Methodologies",
            f"Empirical Analysis of {text.title()}",
        )
        records = []
        for index, title in enumerate(titles, 1):
            records.append(LiteratureRecord(
                source_id=f"L{index}",
                title=title,
                authors=[f"Author {chr(64 + index)}", f"Author {chr(67 + index)}"],
                year=2025 - index,
                source_provider=self.name,
                source_type=SourceType.SIMULATED,
                retrieved_at=retrieved_at,
                core_method=query.methods[(index - 1) % len(query.methods)] if query.methods else "unknown",
                datasets=[],
                metrics=[],
                key_findings=[
                    f"Simulated finding 1 for {title}",
                    f"Simulated finding 2 for {title}",
                ],
                limitations=["Simulated record; not a real citation"],
            ))
        return _result(self.name, text, records, retrieved_at=retrieved_at)


class LLMSimulatedProvider(LiteratureProvider):
    name = ProviderName.LLM_SIMULATED.value

    def search(self, query: LiteratureQuery) -> LiteratureSearchResult:
        from noteforge.json_tools import extract_json
        from noteforge.llm import chat

        query_text = _query_text(query) or "research topic"
        prompt = (
            "请生成 3-5 条用于界面演示的模拟学术记录，只返回 JSON。"
            "这些记录不是真实检索结果。\n\n"
            f"主题：{query_text}\n"
            "格式：{\"literature_results\":[{\"title\":\"\",\"authors\":[],"
            "\"year\":2025,\"abstract\":\"\",\"core_method\":\"\","
            "\"datasets\":[],\"metrics\":[],\"key_findings\":[],\"limitations\":[]}]}"
        )
        response = chat(
            prompt,
            system_prompt="你生成的内容仅用于模拟演示，不得声称是真实文献。",
            temperature=0.5,
        )
        if response is not None:
            parsed, error = extract_json(response)
            if error is None and isinstance(parsed, dict):
                return _normalize_simulated(parsed, self.name, query_text)
        fallback = MockLiteratureProvider().search(query)
        fallback.provider = self.name
        fallback.warnings.append("LLM 模拟结果解析失败，已使用本地 Mock 数据。")
        for item in fallback.literature_results:
            item.source_provider = self.name
        return fallback


class CrossrefLiteratureProvider(LiteratureProvider):
    name = ProviderName.CROSSREF.value

    def __init__(self, *, max_results: int | None = None,
                 timeout: int | None = None, opener=None, sleeper=None):
        self.max_results = max_results or _env_int("LITERATURE_MAX_RESULTS", 10, 1, 100)
        self.timeout = timeout or _env_int("LITERATURE_TIMEOUT_SECONDS", 10, 1, 60)
        self._opener = opener or urlopen
        self._sleep = sleeper or time.sleep

    def search(self, query: LiteratureQuery) -> LiteratureSearchResult:
        query_text = _query_text(query)
        if not query_text:
            return _result(
                self.name, "", [], status=ProviderStatus.DEGRADED,
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
                usable = [
                    item for item in items if isinstance(item, dict)
                    and str(item.get("type", "")).casefold() not in EXCLUDED_CROSSREF_TYPES
                ]
                records = [
                    _normalize_crossref_item(item, index, retrieved_at)
                    for index, item in enumerate(usable[:self.max_results], 1)
                ]
                warnings = [] if records else ["Crossref 未返回匹配的文献记录。"]
                return _result(self.name, query_text, records, warnings=warnings, retrieved_at=retrieved_at)
            except HTTPError as error:
                if attempt == 0 and (error.code == 429 or 500 <= error.code < 600):
                    self._sleep(_retry_delay(error))
                    continue
                return self._degraded(query_text, f"Crossref HTTP {error.code}")
            except (URLError, TimeoutError) as error:
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
        return f"NoteForge/0.3.0 (https://github.com/cheese-sansan/NoteForge{contact})"

    def _degraded(self, query_text: str, warning: str) -> LiteratureSearchResult:
        return _result(
            self.name, query_text, [], status=ProviderStatus.DEGRADED, warnings=[warning],
        )


def search_literature(query: LiteratureQuery, provider: ProviderName | str | None = None) -> LiteratureSearchResult:
    return get_provider(provider).search(query)


def get_provider(provider: ProviderName | str | None = None) -> LiteratureProvider:
    raw = provider.value if isinstance(provider, ProviderName) else provider
    name = (raw or os.environ.get("LITERATURE_PROVIDER", DEFAULT_PROVIDER)).strip().lower().replace("_", "-")
    if name == ProviderName.CROSSREF.value:
        return CrossrefLiteratureProvider()
    if name == ProviderName.MOCK.value:
        return MockLiteratureProvider()
    if name in ("llm", ProviderName.LLM_SIMULATED.value):
        return LLMSimulatedProvider()
    raise ValueError(f"不支持的文献 Provider '{name}'；可选值: {', '.join(PROVIDER_NAMES)}")


def query_from_keyword_output(output: dict) -> LiteratureQuery:
    entities = output.get("academic_entities", {}) if isinstance(output, dict) else {}
    return LiteratureQuery(
        keywords=[str(item) for item in output.get("keywords", [])] if isinstance(output, dict) else [],
        methods=[str(item) for item in entities.get("methods", [])] if isinstance(entities, dict) else [],
        domains=[str(item) for item in entities.get("domains", [])] if isinstance(entities, dict) else [],
    )


def _result(provider: str, query: str, records: list[LiteratureRecord], *,
            status: ProviderStatus = ProviderStatus.OK, warnings: list[str] | None = None,
            retrieved_at: str | None = None) -> LiteratureSearchResult:
    return LiteratureSearchResult(
        provider=provider,
        query=query,
        status=status,
        retrieved_at=retrieved_at or _now_iso(),
        warnings=list(warnings or []),
        literature_results=records,
    )


def _normalize_simulated(data: dict, provider: str, query: str) -> LiteratureSearchResult:
    raw_records = data.get("literature_results", []) if isinstance(data, dict) else []
    retrieved_at = _now_iso()
    records = []
    for index, raw in enumerate(raw_records if isinstance(raw_records, list) else [], 1):
        if not isinstance(raw, dict):
            continue
        records.append(LiteratureRecord(
            source_id=f"L{index}",
            title=str(raw.get("title", "Unknown")),
            authors=raw.get("authors", []) if isinstance(raw.get("authors"), list) else [],
            year=raw.get("year") if isinstance(raw.get("year"), int) else None,
            doi=str(raw.get("doi", "")).strip() or None,
            url=str(raw.get("url", "")).strip() or None,
            abstract=str(raw.get("abstract", "")),
            source_provider=provider,
            source_type=SourceType.SIMULATED,
            retrieved_at=retrieved_at,
            core_method=str(raw.get("core_method", "")),
            datasets=_string_list(raw.get("datasets")),
            metrics=_string_list(raw.get("metrics")),
            key_findings=_string_list(raw.get("key_findings")),
            limitations=_string_list(raw.get("limitations")),
        ))
    return _result(provider, query, records, retrieved_at=retrieved_at)


def _normalize_crossref_item(item: dict, index: int, retrieved_at: str) -> LiteratureRecord:
    authors = []
    for author in item.get("author", []) if isinstance(item.get("author"), list) else []:
        if isinstance(author, dict):
            name = " ".join(part for part in (
                str(author.get("given", "")).strip(), str(author.get("family", "")).strip(),
            ) if part)
            if name:
                authors.append(name)
    doi = str(item.get("DOI", "")).strip() or None
    url = str(item.get("URL", "")).strip() or (f"https://doi.org/{doi}" if doi else None)
    return LiteratureRecord(
        source_id=f"L{index}",
        title=_clean_markup(_first_text(item.get("title"))) or "Unknown",
        authors=authors,
        year=_crossref_year(item),
        doi=doi,
        url=url,
        abstract=_clean_markup(item.get("abstract")),
        source_provider=ProviderName.CROSSREF.value,
        source_type=SourceType.EXTERNAL_API,
        retrieved_at=retrieved_at,
    )


def _query_text(query: LiteratureQuery) -> str:
    values: list[str] = []
    for item in query.keywords + query.methods + query.domains:
        text = str(item).strip()
        if text and text.casefold() not in {value.casefold() for value in values}:
            values.append(text)
        if len(values) >= 8:
            break
    return " ".join(values)


def _crossref_year(item: dict) -> int | None:
    for key in ("published-print", "published-online", "created"):
        parts = item.get(key, {}).get("date-parts", [])
        if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0]:
            try:
                return int(parts[0][0])
            except (TypeError, ValueError):
                pass
    return None


def _first_text(value) -> str:
    return str(value[0]).strip() if isinstance(value, list) and value else str(value or "").strip()


def _clean_markup(value) -> str:
    text = html.unescape(str(value or ""))
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()


def _string_list(value) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_error(error: Exception) -> str:
    return str(getattr(error, "reason", error))[:200]


def _retry_delay(error: HTTPError) -> float:
    try:
        value = float(error.headers.get("Retry-After", "0.5"))
    except (AttributeError, TypeError, ValueError):
        value = 0.5
    return max(0.0, min(value, 5.0))
