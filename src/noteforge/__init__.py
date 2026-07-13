"""Stable public SDK surface for NoteForge."""

from noteforge.errors import ErrorCode, ErrorRecord, NoteForgeError
from noteforge.models import (
    AnalysisRequest,
    JobResult,
    JobStatus,
    LiteratureQuery,
    LiteratureRecord,
    LiteratureSearchResult,
    PolicyRecord,
    ProviderName,
    SourceRecord,
    SourceType,
    TechnicalCase,
)
from noteforge.pipeline import run_job
from noteforge.providers import LiteratureProvider
from noteforge.version import __version__

__all__ = [
    "AnalysisRequest",
    "ErrorCode",
    "ErrorRecord",
    "JobResult",
    "JobStatus",
    "LiteratureQuery",
    "LiteratureProvider",
    "LiteratureRecord",
    "LiteratureSearchResult",
    "NoteForgeError",
    "PolicyRecord",
    "ProviderName",
    "SourceRecord",
    "SourceType",
    "TechnicalCase",
    "run_job",
    "__version__",
]
