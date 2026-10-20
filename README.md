# Paradigme

Paradigme is a local web application for researching a subject and exploring its
possible consequences with an LLM: public-source research, sector analysis,
decision trees, conditional scenarios, and PDF/text reports.

## Getting started

Requirements: Python 3.10 or newer, a browser, and a supported LLM server or cloud
API. Download or clone this repository and open a terminal in its folder.

On Windows, run `INSTALLER.bat`, then `start.bat`.
On Linux or macOS, run `bash install.sh`, then `bash start.sh`.
The scripts create a project-local environment and copy `config.example.json` to
`config.json` when absent. Existing configuration is preserved.

Open **http://127.0.0.1:8765** and use the setup wizard. Choose a provider and check
its URL, model name, and credentials. Example model names are editable starting
points, not availability guarantees. Start local LLM servers separately.

Manual installation is also possible:

```sh
python -m venv paradigme_venv
# Activate the environment using the command appropriate to your shell.
python -m pip install -r requirements.txt
python app.py
```

Change `server.port` in your private configuration if necessary. Stop with Ctrl+C.

## Using the application

1. Enter a specific subject and optional context.
2. Choose Classic sector analysis or the Turchin-inspired exploratory model.
3. Select perspectives and research sources. Full-page excerpts are optional.
4. Start the analysis and optionally request PDF/text output.
5. Review citations and evidence gaps. Completed results persist across restarts.

Classic is the default. Turchin adds cycle phases, stress scores, predator/prey
metaphors, and timelines. These are LLM-generated interpretations, not a validated
scientific forecasting model. Scores, probabilities, dates, and long-term scenarios
are **uncalibrated exploratory outputs**. The predator/prey curve is illustrative,
not a fitted simulation. Verify historical claims independently.

The quality gate checks length, actions, sources, citations, and unsupported
numbers. Passing this gate does not establish that an analysis is true.

## Connections and data

Providers include Groq, OpenAI-compatible endpoints, Anthropic, Ollama, llama.cpp,
and a configurable shared local bridge. No model server is bundled.

Research uses DuckDuckGo, Wikipedia, Google News, YouTube, and Internet Archive.
Queries leave your computer. Subject/context and source excerpts go to the selected
LLM, which may be a cloud provider. The browser loads D3 from `d3js.org`.
Using a local LLM does not make enabled web research offline.

Email is optional and disabled in the example configuration. Reports are sent when
requested; **Send test email** also sends a real email.

`config.json`, `data/`, `logs/`, environments, backups, archives, and `.local/` are
excluded from Git. They may contain credentials, personal subjects, reports, and
diagnostics. Do not include them in public archives. The app has no authentication;
keep it on loopback. See [Privacy](docs/PRIVACY.md).

Documentation and new generated prose default to English. Existing saved reports
remain unchanged. Legacy JSON keys and enum IDs stay stable for compatibility.

## Development and publication

```sh
python -m unittest discover -s tests -v
python scripts/audit_public.py
python scripts/audit_git_history.py
python zipper_drive.py
```

Pass `--private-denylist` with an external private JSON array of known identifiers
for stronger checks. Never commit it. Audits report locations/categories without
matching values; they are heuristics, not proof of anonymity. The ZIP exporter
audits first, includes publishable source only, and refuses to overwrite archives.
Git history is audited separately.

See [Technical guide](CAHIER_TECHNIQUE.md) and [Validation](docs/VALIDATION.md).

## License

MIT. See [LICENSE](LICENSE).
