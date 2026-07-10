"""Public integration surface for NoteForge."""

from core.pipeline import PipelineError, run_job
from core.version import __version__

__all__ = ["PipelineError", "run_job", "__version__"]
