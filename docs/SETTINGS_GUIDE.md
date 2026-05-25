# Settings Guide

## Purpose

This document explains how `{trinity}` stores and edits machine-local settings.

## Two Setting Layers

`{trinity}` currently has two main machine-local setting layers:

1. foundation policy
2. adapter model config

They serve different purposes.

## Foundation Policy

The foundation policy controls machine-local release and seam defaults such as:

- Train default transport
- supported providers per adapter
- preferred live provider per adapter
- release-gate smoke roles per adapter
- whether Gobii is required for release checks

CLI commands:

```bash
PYTHONPATH=core uv run python -m trinity_core.cli show-foundation-policy --include-path
PYTHONPATH=core uv run python -m trinity_core.cli write-foundation-policy --adapter reply
```

Current contract note:

- the shipped foundation-policy schema currently models `reply` and `spot`
- the macOS shell can detect additional adapters, but dedicated editable policy panels are only present for the adapters represented in that contract today

## Adapter Model Config

The adapter model config controls runtime execution wiring such as:

- active provider
- per-role model names
- per-role model IDs where used
- provider endpoints
- provider executable path
- provider timeout

CLI commands:

```bash
PYTHONPATH=core uv run python -m trinity_core.cli show-config --adapter reply --include-path
PYTHONPATH=core uv run python -m trinity_core.cli write-config --adapter reply
```

## Native Shell Settings

The macOS shell writes the same machine-local JSON as the CLI.

It does not use a second hidden settings path.

Current shell settings behavior:

- reload and save run off-main
- in-flight operations are visible in the UI
- failures are surfaced explicitly
- adapters are discovered through the shared adapter catalog
- unsupported/discovered adapters are shown instead of silently disappearing from the shell

## Current Local Paths

New installs use adapter-scoped paths:

```text
~/Library/Application Support/Trinity/trinity_runtime/adapters/<adapter>/model_config.json
~/Library/Application Support/Trinity/trinity_runtime/foundation_policy.json
```

Reply compatibility path:

- if `~/Library/Application Support/Trinity/reply_runtime/model_config.json` already exists and the new namespaced Reply root does not, `{trinity}` may keep using that legacy Reply config path

## Recommended Workflow

For normal operator use:

1. inspect `runtime-status --adapter <adapter>`
2. inspect `show-config --adapter <adapter> --include-path`
3. inspect `show-foundation-policy --include-path`
4. change settings through the native shell or CLI
5. re-run `foundation-check --adapter <adapter>`

## Safe Defaults

Current baseline described by the docs and local examples:

- Train default transport: `cli`
- Reply preferred live provider: `mistral-cli`
- Spot supported provider: `deterministic`
- Gobii required for release: `false`

## Related Docs

- [docs/LOCAL_INSTALL.md](/Users/Shared/Projects/trinity/docs/LOCAL_INSTALL.md)
- [docs/API_SURFACE.md](/Users/Shared/Projects/trinity/docs/API_SURFACE.md)
- [docs/CLI_REFERENCE.md](/Users/Shared/Projects/trinity/docs/CLI_REFERENCE.md)
- [docs/MACOS_DEVELOPMENT.md](/Users/Shared/Projects/trinity/docs/MACOS_DEVELOPMENT.md)
