"""Stable standard-library models for the NoteForge SDK and persistence layer."""

from __future__ import annotations

import json
import types
from dataclasses import dataclass, field, fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, TypeVar, Union, cast, get_args, get_origin, get_type_hints

SCHEMA_VERSION = 3
T = TypeVar("T", bound="JsonModel")


class SourceType(str, Enum):
    EXTERNAL_API = "external_api"
    SOURCE_DOCUMENT = "source_document"
    LLM_INFERENCE = "llm_inference"
    SIMULATED = "simulated"
    UNVERIFIED = "unverified"


class ProviderName(str, Enum):
    CROSSREF = "crossref"
    MOCK = "mock"
    LLM_SIMULATED = "llm-simulated"


class ProviderStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"


class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class StageStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


class JsonModel:
    """Uniform recursive JSON codec shared by every public dataclass model."""

    def to_dict(self) -> dict[str, Any]:
        return _encode(self)

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls: type[T], data: dict[str, Any]) -> T:
        if not isinstance(data, dict):
            raise TypeError(f"{cls.__name__} requires an object")
        if "schema_version" in data and data["schema_version"] != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {data['schema_version']}")
        hints = get_type_hints(cls)
        kwargs: dict[str, Any] = {}
        for item in fields(cast(Any, cls)):
            if item.name in data:
                kwargs[item.name] = _decode(hints.get(item.name, Any), data[item.name])
        return cls(**kwargs)

    @classmethod
    def from_json(cls: type[T], payload: str) -> T:
        data = json.loads(payload)
        return cls.from_dict(data)


def _encode(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return {item.name: _encode(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, dict):
        return {str(key): _encode(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_encode(item) for item in value]
    return value


def _decode(annotation: Any, value: Any) -> Any:
    if annotation is Any:
        return value
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin in (Union, types.UnionType):
        if value is None and type(None) in args:
            return None
        for candidate in args:
            if candidate is type(None):
                continue
            try:
                return _decode(candidate, value)
            except (TypeError, ValueError):
                continue
        return value
    if origin is list:
        item_type = args[0] if args else Any
        return [_decode(item_type, item) for item in value or []]
    if origin is dict:
        key_type, item_type = args if len(args) == 2 else (Any, Any)
        return {_decode(key_type, key): _decode(item_type, item) for key, item in (value or {}).items()}
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return annotation(value)
    if annotation is Path:
        return Path(value)
    if isinstance(annotation, type) and issubclass(annotation, JsonModel):
        return annotation.from_dict(value)
    return value


@dataclass(slots=True)
class AnalysisRequest(JsonModel):
    topic: str = ""
    file_path: Path | None = None
    provider: ProviderName | None = None
    job_id: str | None = None

    def __post_init__(self):
        self.topic = self.topic.strip()
        if isinstance(self.file_path, str):
            self.file_path = Path(self.file_path)
        if isinstance(self.provider, str):
            self.provider = ProviderName(self.provider)
        if not self.topic and self.file_path is None and not self.job_id:
            raise ValueError("topic, file_path, or resumable job_id is required")


@dataclass(slots=True)
class LiteratureQuery(JsonModel):
    keywords: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SourceRecord(JsonModel):
    source_id: str
    title: str
    source_provider: str
    source_type: SourceType
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    doi: str | None = None
    url: str | None = None
    retrieved_at: str | None = None


@dataclass(slots=True)
class LiteratureRecord(SourceRecord):
    abstract: str = ""
    core_method: str = ""
    datasets: list[str] = field(default_factory=list)
    metrics: list[str] = field(default_factory=list)
    key_findings: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)


@dataclass(slots=True)
class LiteratureSearchResult(JsonModel):
    provider: str
    query: str
    status: ProviderStatus
    retrieved_at: str
    warnings: list[str] = field(default_factory=list)
    literature_results: list[LiteratureRecord] = field(default_factory=list)


@dataclass(slots=True)
class ClaimRecord(JsonModel):
    text: str
    evidence_ids: list[str]
    source_type: SourceType
    verification_status: str


@dataclass(slots=True)
class TechnicalCase(JsonModel):
    case_name: str
    use_scenario: str = ""
    technical_route: str = ""
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    implementation_conditions: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    source_type: SourceType = SourceType.UNVERIFIED
    verification_status: str = "unverified"


@dataclass(slots=True)
class PolicyRecord(JsonModel):
    policy_name: str
    issuing_body: str = ""
    effective_date: str = ""
    scope: str = ""
    affected_parties: list[str] = field(default_factory=list)
    compliance_requirements: list[str] = field(default_factory=list)
    risk_level: str = "unknown"
    evidence_ids: list[str] = field(default_factory=list)
    source_type: SourceType = SourceType.UNVERIFIED
    verification_status: str = "unverified"


@dataclass(slots=True)
class ArtifactSet(JsonModel):
    report: str | None = None


@dataclass(slots=True)
class StageRecord(JsonModel):
    name: str
    status: StageStatus = StageStatus.PENDING
    started_at: str | None = None
    finished_at: str | None = None
    error: dict[str, Any] | None = None
    history: list[dict[str, str]] = field(default_factory=list)


@dataclass(slots=True)
class JobState(JsonModel):
    job_id: str
    status: JobStatus = JobStatus.PENDING
    current_stage: str | None = None
    created_at: str = ""
    updated_at: str = ""
    error: dict[str, Any] | None = None
    stages: dict[str, StageRecord] = field(default_factory=dict)
    artifacts: ArtifactSet = field(default_factory=ArtifactSet)
    schema_version: int = SCHEMA_VERSION


@dataclass(slots=True)
class JobResult(JsonModel):
    job_id: str
    status: JobStatus
    report_path: Path
    sources: list[SourceRecord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    tech_cases: list[TechnicalCase] = field(default_factory=list)
    policies: list[PolicyRecord] = field(default_factory=list)
