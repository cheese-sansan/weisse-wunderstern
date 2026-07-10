# Mock And Real Provider Behavior

Provider selection controls where literature records come from. It is separate from the optional LLM used to analyze those records.

| Mode | Data origin | Network | Valid citation source | Failure behavior |
| --- | --- | --- | --- | --- |
| `crossref` | Crossref REST API metadata | Required | Metadata only; verify through DOI | Empty results plus warning |
| `mock` | Deterministic local generator | No | No | Always labelled `simulated` |
| `llm-simulated` | LLM-generated demonstration data | LLM endpoint | No | Falls back to labelled local Mock data |

Crossref is the default. It may return records without abstracts; NoteForge keeps the abstract empty and does not fabricate methods, findings, metrics, or limitations. Table, figure, reference-entry, issue, and volume components are filtered before the result limit is applied.

Mock modes must be selected explicitly:

```bash
python main.py --topic "AI evaluation" --provider mock
```

Reports show the active data mode at the top. A real Provider outage never triggers an automatic Mock fallback, because mixing simulated records into a real retrieval run would weaken provenance.
