# Contributing

Current release line:

- `0.1.4`

## Principles

- Keep the workflow contract explicit.
- Keep local-first operation as the default path.
- Keep product adapters out of core runtime code.
- Update SSOT docs when behavior or architecture changes.

## Before Opening A PR

Run:

```bash
uv run ruff check .
uv run pytest
cd apps/macos && swift build
```

If your change touches adapter, CLI, or policy/governance contracts, also verify the downstream runtime seams still resolve:

```bash
PYTHONPATH=core uv run python -m trinity_core.cli runtime-status --adapter reply
PYTHONPATH=core uv run python -m trinity_core.cli runtime-status --adapter spot
```

## Documentation

If your change affects:

- architecture
- repository structure
- development workflow
- operator behavior
- handoff context

then update the relevant file under `docs/`.
