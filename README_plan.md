# NoteForge Public Roadmap

NoteForge is a lightweight, verifiable topic and document distillation pipeline. The project prioritizes data authenticity, provenance, and report trustworthiness over feature count.

## v0.2: Evidence-Aware Retrieval

Implemented in the current release:

- Real Crossref literature retrieval with explicit provider selection.
- Source records for external APIs, local documents, LLM inference, simulated data, and unverified content.
- Evidence-aware T3 claims and structured T5 technical cases.
- Strict T6 policy evidence gating; no factual policy output without a cited source.
- Final `report.md` with sources, warnings, and compatibility output for v0.1 clients.
- Real topic/document examples and an explicit Mock-versus-real behavior guide.

## v0.3: Python Engineering (implemented)

- Adopt `pyproject.toml` and a `src/noteforge/` package layout.
- Add an installed `noteforge` command and stable SDK models.
- Replace task-ID-centric context contracts with semantic models while retaining a migration reader.
- Formalize the Job state machine and structured error codes.
- Add Ruff, Pyright, coverage thresholds, and OpenAPI contract checks.

## v0.4: Report Quality

- Citation numbering, DOI/URL deduplication, and citation completeness checks.
- Evidence grades and conflict/obsolescence detection.
- Report presets for technical research, literature review, industry analysis, policy analysis, and product comparison.
- JSON and HTML exports before DOCX and PDF.

## v1.0 Release Conditions

- Installable Python package with stable CLI, API, and SDK interfaces.
- At least one production-ready real Provider and complete provenance on all outputs.
- T5/T6 validated against real source material.
- Citation traceability, representative examples, passing CI, and documented capability boundaries.

## Deferred Until After v1.0

GraphRAG, heavy vector databases, large knowledge graphs, multi-tenant authorization, complex frontends, cloud SaaS, and open-ended multi-agent loops remain out of scope.
