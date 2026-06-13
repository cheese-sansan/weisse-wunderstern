# CLI, TUI, And API Usage

## CLI

Analyze a topic:

```bash
python main.py --topic "transformer model evaluation" --output demo_topic
```

Analyze a file:

```bash
python main.py --file ./examples/sample_paper_abstract.md --output demo_file
```

Start the TUI from the CLI:

```bash
python main.py --tui
```

## TUI

Interactive mode:

```bash
python main_tui.py
```

One-shot commands:

```bash
python main_tui.py --topic "AI safety" --job-id tui_ai_safety
python main_tui.py --file ./examples/sample_paper_abstract.md --job-id tui_file_demo
python main_tui.py --list
python main_tui.py --report tui_ai_safety
```

## API

Install API dependencies:

```bash
pip install -r requirements-api.txt
```

Start:

```bash
python main_api.py
```

Health:

```bash
curl http://localhost:8000/health
```

Submit:

```bash
curl -X POST http://localhost:8000/api/v1/jobs/submit -F "topic=AI safety"
```

Status:

```bash
curl http://localhost:8000/api/v1/jobs/status/{job_id}
```

Result:

```bash
curl http://localhost:8000/api/v1/jobs/result/{job_id}
```

## API Authentication

Set `API_TOKEN` to require bearer-token authentication:

```bash
API_TOKEN=change-me python main_api.py
```

Then call:

```bash
curl -H "Authorization: Bearer change-me" http://localhost:8000/api/v1/jobs/status/{job_id}
```

Use a real secret only through environment variables or a local `.env` file. Never commit credentials.
