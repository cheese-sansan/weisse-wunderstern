# Security Policy

Lite Agent Orchestrator is a lightweight local tool and standalone API service. It is not yet a hardened multi-tenant hosted platform.

## Supported Versions

Security fixes target the latest `main` branch until versioned releases begin.

## Reporting A Vulnerability

Please do not open a public issue for suspected credential exposure, path traversal, arbitrary file read/write, authentication bypass, or remote code execution.

Use GitHub private vulnerability reporting if it is enabled for the repository, or contact the maintainer directly.

## Operational Guidance

- Do not expose the API to untrusted networks without setting `API_TOKEN`.
- Treat uploaded documents as untrusted input.
- Keep `.env` local and never commit real credentials.
- Generated artifacts are stored under `outputs/jobs/{job_id}/` and should not be published by default.
- Simulated literature results must remain labeled as simulated.

## Pre-Publish Audit

Run before publishing:

```bash
python scripts/privacy_audit.py
python scripts/privacy_audit.py --history
python scripts/privacy_audit.py --include-outputs
```

The audit checks for high-confidence credentials, assigned secret-like values, private absolute paths, and phone-like numbers. Findings are redacted in command output.
