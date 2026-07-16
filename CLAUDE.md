# solar-report

Generate human-readable reports from your solar PV system data. Connects to Home Assistant or CSV exports, aggregates production data, and uses an LLM to produce weekly/monthly reports in natural language.

## Project goal

Open source portfolio project (Apache 2.0). Purpose: demonstrate hands-on skills in Python, time-series data processing, and LLM integration in the renewable energy domain. Used as a magnet for inbound freelance opportunities, not as a SaaS product.

v0.1 success criterion: a stranger with a Home Assistant instance monitoring their PV system can run `docker compose up` (or `pip install solar-report`), point it at their HA instance, and receive a Markdown report of last week's production with a plain-language summary.

## v0.1 scope

IN:
- Data source connectors:
  - Home Assistant (via REST API + long-term statistics)
  - CSV import (documented column format for interoperability)
- Time-series aggregation: daily/weekly/monthly production, min/max/avg, day-over-day and week-over-week deltas
- Simple anomaly detection: production drops vs rolling baseline, worst/best day identification
- LLM-based report generation via Anthropic API:
  - Structured prompt with aggregated data + metadata (location, system size)
  - Configurable tone/length (short summary vs detailed)
  - Output in Markdown (default) and HTML
- CLI entry point: `solar-report generate --config config.yaml --period week`
- Docker Compose for zero-install trial
- Example configs and sample CSV for demo runs

OUT (do not implement, do not scaffold):
- Web UI, multi-user, authentication
- Other data sources (Solar-Log, SolarEdge, Enphase, Fronius): mention in roadmap only
- Real-time / streaming reports
- Forecasting, ML models
- Email/notification delivery
- Multi-language reports (English only for v0.1)

## Stack

- Python 3.11 (system: Ubuntu 22.04 LTS with python3.11 installed alongside default python3.10; use `python3.11 -m venv .venv` explicitly)
- `httpx` for Home Assistant API calls
- `pandas` for time-series aggregation
- `pydantic` v2 for config validation
- `anthropic` official SDK for LLM calls
- `jinja2` for report templating (Markdown/HTML)
- `PyYAML` for config
- `typer` for CLI
- Tests: `pytest` + `pytest-asyncio`, plus recorded HA API responses as fixtures
- Lint/format: `ruff`; type-check: `mypy` strict on `src/`
- Packaging: `pyproject.toml` (hatchling), publishable to PyPI

## Repository layout

```
solar-report/
├── CLAUDE.md
├── README.md
├── LICENSE                  # Apache 2.0
├── pyproject.toml
├── docker-compose.yml
├── Dockerfile
├── config.example.yaml
├── sample-data/
│   └── example-week.csv
├── src/solar_report/
│   ├── __init__.py
│   ├── cli.py
│   ├── config.py            # pydantic models, YAML loading
│   ├── sources/
│   │   ├── base.py          # DataSource protocol
│   │   ├── home_assistant.py
│   │   └── csv_source.py
│   ├── analysis/
│   │   ├── aggregations.py  # daily/weekly/monthly
│   │   ├── anomalies.py     # baseline comparison, worst/best day
│   │   └── models.py        # ProductionData, PeriodSummary
│   ├── report/
│   │   ├── generator.py     # orchestrates: source → analysis → LLM → render
│   │   ├── prompts.py       # Anthropic API prompt templates
│   │   └── templates/
│   │       ├── report.md.j2
│   │       └── report.html.j2
│   └── llm/
│       └── client.py        # thin wrapper around anthropic SDK
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/            # recorded HA responses, sample CSVs
└── docs/
    ├── quickstart.md
    ├── home-assistant-setup.md
    └── csv-format.md
```

## Config YAML shape

```yaml
system:
  name: "My rooftop PV"
  location: "Turin, Italy"
  installed_kwp: 6.0
  panels: 15
  tilt_deg: 30
  azimuth_deg: 180

source:
  kind: "home_assistant"     # home_assistant | csv
  home_assistant:
    url: "http://homeassistant.local:8123"
    token: "${HA_TOKEN}"
    entity_id: "sensor.solar_production_total"
  csv:
    path: "./data/production.csv"

report:
  period: "week"             # day | week | month
  tone: "friendly"           # friendly | technical | brief
  language: "en"
  output_format: "markdown"  # markdown | html
  output_path: "./reports/{period}-{date}.md"

llm:
  provider: "anthropic"
  model: "claude-sonnet-5"
  api_key: "${ANTHROPIC_API_KEY}"
  max_tokens: 1500
```

## Prompt design principles

- Never send raw time-series to the LLM: send pre-computed aggregations only
- Include system metadata (size, location, season) so the LLM can reason about expected performance
- Provide baseline comparisons (this week vs 4-week rolling average) so the LLM can call out deviations
- Structure prompt in sections: system info → period summary → notable events → tone/format instructions
- Keep prompts in `report/prompts.py` as versioned functions; snapshot-test them

## Conventions

- All code, comments, docs, commit messages in English
- Conventional Commits (`feat:`, `fix:`, `docs:`...)
- Every public function typed; mypy strict must pass
- Fixtures for HA API responses stored under `tests/fixtures/` — never call the live API in tests
- LLM calls in tests mocked at the client boundary
- No secrets in config files: env var interpolation only
- Reports must degrade gracefully if LLM is unreachable (fallback: template-only report from aggregations)

## README priorities (marketing surface)

The README is the portfolio piece. Structure:
1. One-line tagline + sample report screenshot (rendered Markdown with real numbers)
2. "Why": three lines on the problem (monitoring dashboards give data, not insight)
3. Quick start: 3-command Docker or pip
4. Live example: sample CSV → generated report shown in full
5. Supported data sources + roadmap (invite issues for requested integrations)
6. Config reference
7. Sober footer: "Building something on solar/energy data? → contact" (freelance channel)

## Critical constraints

- Original work only: no code, snippets or configs from any employer project
- Developed on personal hardware, personal GitHub account, personal git identity
- Domain deliberately distant from industrial CNC monitoring to avoid any perceived conflict of interest

## Timeline (6 weeks, ~15h/week)

- Week 1-2: config, CSV source, aggregations, models, tests
- Week 3: Home Assistant source + fixtures
- Week 4: LLM integration, prompt engineering, template rendering
- Week 5: Docker, docs, README, sample report generation
- Week 6: launch (r/homeassistant, r/solar, dev.to, LinkedIn) + issue triage
