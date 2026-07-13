"""Structured NoteForge errors."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from noteforge.models import JsonModel


class ErrorCode(str, Enum):
    INPUT_INVALID = "INPUT_INVALID"
    PARSE_FAILED = "PARSE_FAILED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_RESPONSE_INVALID = "PROVIDER_RESPONSE_INVALID"
    ANALYSIS_FAILED = "ANALYSIS_FAILED"
    STORAGE_FAILED = "STORAGE_FAILED"
    MIGRATION_FAILED = "MIGRATION_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass(slots=True)
class ErrorRecord(JsonModel):
    code: ErrorCode
    message: str
    retryable: bool = False
    details: dict[str, Any] = field(default_factory=dict)


class NoteForgeError(Exception):
    def __init__(self, code: ErrorCode, message: str, *, retryable: bool = False,
                 details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = dict(details or {})
        self.record = ErrorRecord(code=code, message=message, retryable=retryable, details=self.details)

    def to_dict(self) -> dict[str, Any]:
        return self.record.to_dict()


class InvalidStateTransition(NoteForgeError):
    def __init__(self, current: str, target: str):
        super().__init__(
            ErrorCode.STORAGE_FAILED,
            f"invalid stage transition: {current} -> {target}",
            details={"current": current, "target": target},
        )


class LLMResponseError(NoteForgeError):
    def __init__(self, message: str, *, retryable: bool = True):
        super().__init__(ErrorCode.ANALYSIS_FAILED, message, retryable=retryable)
