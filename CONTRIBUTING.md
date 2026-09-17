# Contributing

Thanks for taking a look. Overscope is a small, deliberately dependency-light project,
so contributions that keep it fast, local, and honest are very welcome.

## Analyzer (Python CLI)

```bash
uv sync --extra dev
uv run pytest        # tests
uv run ruff check .  # lint + import order
uv run mypy          # strict types
```

The pipeline is a set of small modules under `src/overscope/`: git collection, session
adapters, intent extraction, attribution, scope, rules, reconciliation, and reporting.
The analysis model is independent of the terminal and JSON renderers.

### Adding an agent adapter

Implement `SessionAdapter` in `src/overscope/sessions/base.py` with bounded
`candidates()` discovery and a tolerant `parse()`, return the shared `Session` /
`ToolAction` / `SessionCandidate` models, register it in
`sessions.discovery.adapters_for()`, and add fixtures covering malformed records,
unknown events, discovery, messages, tools, and results. An adapter must not make
network calls or surface hidden model reasoning.

## Desktop app

```bash
cd web
npm install
npm run dev          # browser preview with sample data
npm run desktop:dev  # the Tauri app against your own repos
```

## Ground rules

- New rules and heuristics need tests, and should run on added/removed diff lines rather
  than scanning whole files.
- Prefer "unknown" over a fabricated conclusion. False positives are the thing most
  likely to make this tool useless.
- Keep it local: no telemetry, no network calls in the default path.
