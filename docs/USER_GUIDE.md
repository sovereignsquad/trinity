# User Guide

## Purpose

This document is the practical operator guide for using `{trinity}` after a local install.

## What Trinity Is

`{trinity}` is a local-first reasoning runtime.

It accepts normalized product evidence, applies adapter-aware runtime logic, and returns ranked outputs with traceable provenance.

It is not:

- the downstream product shell
- the offline optimizer
- a hosted control plane

## Primary Ways To Use It

You can use `{trinity}` through:

- the generic CLI
- the native macOS shell under `apps/macos`
- the programmatic runtime entrypoint `TrinityRuntime(adapter_name=...)`

## First Working Baseline

After install, these are the first commands worth running:

```bash
cd /Users/Shared/Projects/trinity
PYTHONPATH=core uv run python -m trinity_core.cli runtime-status --adapter reply
PYTHONPATH=core uv run python -m trinity_core.cli runtime-status --adapter spot
PYTHONPATH=core uv run python -m trinity_core.cli show-foundation-policy --include-path
```

If you want the native shell:

```bash
cd /Users/Shared/Projects/trinity/apps/macos
swift build
```

## Core Runtime Tasks

Most day-to-day runtime work falls into these categories:

- generate outputs with `suggest --adapter <adapter>`
- persist operator outcomes with `record-outcome --adapter <adapter>`
- inspect readiness with `runtime-status --adapter <adapter>`
- inspect release-preflight health with `foundation-check --adapter <adapter>`
- inspect or update machine-local config with `show-config`, `write-config`, `show-foundation-policy`, and `write-foundation-policy`

See the full command catalog in [docs/CLI_REFERENCE.md](/Users/Shared/Projects/trinity/docs/CLI_REFERENCE.md).

## Native Shell

The macOS shell is a native SwiftUI operator surface.

Current operator-facing surfaces include:

- overview
- timeline
- candidates
- feedback
- governance
- admin/settings

Current shell behavior to know:

- governance artifact loading runs off-main
- governance state distinguishes `loading`, `missing`, and `failed`
- settings save and reload run off-main
- the shell derives the visible adapter list from the shared adapter catalog

## Adapter Expectations

Current implemented adapters:

- `reply`
- `spot`

Current posture:

- `reply` is the first mature embedding
- `spot` is intentionally bounded
- new apps should add a new adapter instead of stretching Reply semantics

If you are integrating a new app, start with [docs/INTEGRATING_NEW_APP.md](/Users/Shared/Projects/trinity/docs/INTEGRATING_NEW_APP.md).

## Runtime Storage

Live runtime data does not belong in the repo working tree.

Default machine-local adapter storage for new installs:

```text
~/Library/Application Support/Trinity/trinity_runtime/adapters/<adapter>/
```

Reply compatibility note:

- if a machine already has `~/Library/Application Support/Trinity/reply_runtime/` and no namespaced Reply root exists yet, `{trinity}` can continue using the legacy Reply root for migration safety

## Common Operator Checks

Use these when something looks wrong:

```bash
cd /Users/Shared/Projects/trinity
PYTHONPATH=core uv run python -m trinity_core.cli runtime-status --adapter reply
PYTHONPATH=core uv run python -m trinity_core.cli foundation-check --adapter reply
PYTHONPATH=core uv run python -m trinity_core.cli provider-smoke --adapter reply --role generator
PYTHONPATH=core uv run python -m trinity_core.cli governance-status --adapter reply
```

If Gobii is relevant in your environment:

```bash
PYTHONPATH=core uv run python -m trinity_core.cli gobii-status --adapter reply --check-live
```

## Where To Go Next

- install and dependency setup: [docs/LOCAL_INSTALL.md](/Users/Shared/Projects/trinity/docs/LOCAL_INSTALL.md)
- settings and local policy/config: [docs/SETTINGS_GUIDE.md](/Users/Shared/Projects/trinity/docs/SETTINGS_GUIDE.md)
- public CLI and runtime API surface: [docs/API_SURFACE.md](/Users/Shared/Projects/trinity/docs/API_SURFACE.md)
- system overview: [docs/TRINITY_OVERVIEW.md](/Users/Shared/Projects/trinity/docs/TRINITY_OVERVIEW.md)
