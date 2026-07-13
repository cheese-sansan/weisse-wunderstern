# Developer Integration

## Stable SDK

```python
from pathlib import Path

from noteforge import AnalysisRequest, JobResult, run_job

request = AnalysisRequest(
    topic="LLM benchmark evaluation",
    file_path=Path("examples/sample_paper_abstract.md"),
    provider="crossref",
    job_id="my-analysis-job",
)
result: JobResult = run_job(request, output_root=Path("outputs"))
```

`JobResult` contains `job_id`, `status`, `report_path`, `sources`, `warnings`, `tech_cases`, and `policies`. Dataclass models provide `to_dict`, `to_json`, `from_dict`, and `from_json`; incoming schema markers are validated against schema v3.

Resume with persisted input:

```python
result = run_job(AnalysisRequest(job_id="my-analysis-job"))
```

## Provider contract

```python
from noteforge import LiteratureProvider, LiteratureQuery, LiteratureSearchResult


class MyProvider(LiteratureProvider):
    name = "my-provider"

    def search(self, query: LiteratureQuery) -> LiteratureSearchResult:
        ...
```

Provider records must label `source_type` and `source_provider`. Simulated records must never be represented as retrieved evidence.

## Internal persistence access

Persistence classes are available for operational tools but are not part of the small top-level SDK surface:

```python
from noteforge.storage.context import ContextStore
from noteforge.storage.state import StateManager

state = StateManager("my-analysis-job").load_state()
context = ContextStore("my-analysis-job").load_all()
```

Do not import v0.2 paths such as `core.pipeline`, `tasks.t2_literature_search`, or `utils.state_manager`; they were removed in v0.3.
