# Paradigme technical guide

## Architecture

| Module | Responsibility |
| --- | --- |
| app.py | FastAPI routes, configuration, job scheduling, persistent history |
| analysis.py | Research and analysis pipelines; quality checks |
| llm_client.py | Provider requests, health checks, JSON parsing |
| prompts.py | English prompts with stable legacy schema keys |
| research.py | Public research, relevance filtering, excerpts |
| cleaning.py | Structural cleanup and fallback text |
| tree_builder.py | Decision trees and fallback conversion |
| pdf_report.py, txt_report.py | Reports |
| mailer.py | Optional SMTP delivery |
| static/ | Browser interface, visualizations, setup wizard |
| scripts/ | Publication and Git-object audits |

## Analysis lifecycle

POST /api/analyze assigns a job ID, retains an asyncio task, and returns immediately.
The client polls GET /api/job/{id}. Steps include LLM health, query generation,
research, analysis, trees, scenarios, synthesis, quality checks, and optional reports.
A bounded repair request asks for missing summary citations. Stages have timeouts;
insufficient final content becomes an error. Fallback structure is not success.

Completed jobs are written atomically to data/results/{id}.json. The newest 200
entries remain in data/history.json; reports live in data/reports/. Older entries
without full JSON results can still link to reports. In-flight jobs remain in
memory and do not resume after shutdown.

## Configuration

The app creates config.json from the credential-free example when absent.
API responses mask API keys and SMTP passwords. Debug output contains only
provider and credential-presence flags, never key prefixes.

| Environment variable | Default |
| --- | --- |
| PARADIGME_CONFIG | config.json next to the app |
| PARADIGME_DATA_DIR | data/ next to the app |
| PARADIGME_LOGS_DIR | logs/ next to the app |
| GROQ_API_KEY | Optional credential when Groq is enabled |

These overrides allow tests to avoid user settings and storage.

The configurable shared bridge exposes /status with model_loaded and optional
current_model; /chat accepts messages, temperature, max_tokens, and priority and
returns a response string. It reuses a separately running model without loading
another copy. No personal installation path is required.

OpenAI-compatible providers use chat completions. Ollama supports native chat;
Anthropic uses its messages protocol. A selected local provider must not silently
send requests to Groq merely because an environment credential exists.

## API overview

- GET /api/health, /api/debug-llm, /api/models: status and metadata.
- GET/POST /api/config: masked settings and updates.
- GET /api/setup/status, POST /api/setup/test, /api/setup/save: setup.
- POST /api/analyze, GET /api/job/{id}: analysis jobs.
- GET /api/history, /api/report/{id}, /api/report/{id}/txt: results.
- GET /api/logs, POST /api/logs/clear: diagnostics.
- POST /api/test-email, /api/test-research: real outbound operations.

There is no authentication or multi-user isolation. Keep the server on loopback.
Never use production credentials or real email recipients in tests.

## Compatibility and interpretation

Persisted keys such as synthese, secteurs, probabilite and IDs such as classique,
risque, optimiste remain stable. They are API identifiers, not a UI language setting.
Prompts request English prose. Existing reports and user content are not rewritten.

The displayed PSI averages three LLM-assigned scores. It is not a calibrated or
validated measure. Branch probabilities and scenario weights are illustrative.
Historical claims need verification. Citation/number checks are syntactic heuristics
and do not prove source quality, entailment, or factual accuracy.

## Release procedure

Run tests, inspect the UI and synthetic reports, audit publishable files, and audit
all Git objects and metadata with an external private reference list. The Git audit
includes unreachable objects. Exclude local state, credentials, logs, backups,
environments, and generated reports. Keep original history backups outside the
project. A neutral root commit can publish a snapshot without original Git objects.
