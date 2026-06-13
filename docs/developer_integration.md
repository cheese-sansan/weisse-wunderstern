# Developer Integration

Lite Agent Orchestrator can be embedded as a small Python library.

## Run A Job

```python
from core import run_job

run_job(
    job_id="my_analysis_job",
    topic="LLM benchmark evaluation",
    file_path="./examples/sample_paper_abstract.md",
)
```

Artifacts are written to:

```text
outputs/jobs/my_analysis_job/
├── task_state.json
├── context_data.json
├── resume_log.txt
└── report_framework.md
```

## Read State And Context

```python
from utils.state_manager import StateManager
from utils.context_manager import ContextStore

state = StateManager("my_analysis_job").load_state()
context = ContextStore("my_analysis_job").load_all()
```

`StateManager` and `ContextStore` validate `job_id`, isolate each job, and write JSON atomically.

## Parse A File

```python
from utils.file_reader import read_file

result = read_file("./examples/sample_paper_abstract.md")
print(result["content"])
```

Optional parsers for PDF, DOCX, spreadsheets, presentations, EPUB, and OCR-related formats are listed in `requirements-extras.txt`.

## Custom Literature Provider

`tasks.t2_literature_search.LiteratureProvider` is the extension point for real retrieval integrations.

```python
from tasks.t2_literature_search import LiteratureProvider


class MyProvider(LiteratureProvider):
    def search(self, query: dict) -> dict:
        return {
            "literature_results": [
                {
                    "title": "Example",
                    "authors": ["A. Author"],
                    "year": 2026,
                    "core_method": "custom method",
                    "datasets": [],
                    "metrics": [],
                    "key_findings": ["..."],
                    "limitations": ["..."],
                    "source_type": "external_api",
                    "source_provider": "my-provider",
                    "url": "https://example.com",
                }
            ]
        }
```

Keep `source_type` explicit. Simulated results must not be presented as verified external citations.

## Stable Imports

Recommended public imports:

```python
from core import run_job, PipelineError
from utils.state_manager import StateManager
from utils.context_manager import ContextStore
from utils.file_reader import read_file
from tasks.t2_literature_search import LiteratureProvider
```

Internal task implementation details may change between releases.
