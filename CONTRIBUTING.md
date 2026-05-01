# Contributing

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

## Documentation

If your change affects:

- architecture
- repository structure
- development workflow
- operator behavior
- handoff context

then update the relevant file under `docs/`.

