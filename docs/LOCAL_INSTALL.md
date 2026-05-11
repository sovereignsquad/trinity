# Local Install

## Purpose

This document explains how to install `{trinity}` locally from a fresh repository checkout, including required tooling and optional provider dependencies.

## Supported Baseline

Current local development baseline:

- `macOS` for the native app shell
- `Python 3.12+`
- `uv`
- `Swift 6.1` toolchain or Xcode with Swift Package Manager support

You can use the runtime and CLI without building the native shell, but the repository currently assumes a macOS-first development environment.

## Dependency Summary

### Required To Work On The Python Runtime

- `git`
- `Python 3.12+`
- `uv`

### Required To Build The Native App Shell

- `Xcode` or Apple Swift toolchain with:
  - `swift`
  - Swift Package Manager support
- macOS capable of building the app target in [apps/macos/Package.swift](/Users/Shared/Projects/trinity/apps/macos/Package.swift), which currently targets `macOS 15`

### Optional Runtime Providers

- `ollama`
  Use if you want a local non-deterministic model provider.

- `mistral-cli`
  Use if you want the current bounded `mistral-cli` provider path.

### Optional External Ops Tooling

- Gobii credentials and reachable Gobii API
  Only needed for the bounded Gobii task, normalization, enrichment, or recurring-workflow lanes.

## 1. Clone The Repository

```bash
git clone <repo-url>
cd trinity
```

## 2. Install Python Tooling

Install `uv` if it is not already available:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Confirm the required tools are present:

```bash
python3 --version
uv --version
```

`{trinity}` requires `Python 3.12+`.

## 3. Sync Python Dependencies

From the repository root:

```bash
uv sync --dev
```

This installs the current Python development dependencies declared in [pyproject.toml](/Users/Shared/Projects/trinity/pyproject.toml).

## 4. Verify The Python Runtime

Run the standard checks:

```bash
uv run ruff check .
uv run pytest
```

If you only want a faster smoke path first:

```bash
PYTHONPATH=core uv run python -m trinity_core.cli runtime-status --adapter reply
```

## 5. Build The macOS Shell

If you want the native shell:

```bash
cd apps/macos
swift build
cd ../..
```

The current app package is defined in [apps/macos/Package.swift](/Users/Shared/Projects/trinity/apps/macos/Package.swift).

## 6. Optional Provider Setup

### Deterministic Provider

No extra installation is required.

This is the safest default for a fresh checkout because it does not depend on external model tooling.

### Ollama

Install and start `ollama` locally, then confirm it is reachable before configuring `{trinity}` to use it.

Example verification:

```bash
ollama --version
```

### Mistral CLI

Install `mistral-cli` only if you intend to use the current bounded provider path.

Example verification:

```bash
mistral --help
```

Important current limitation:

- the repository's current `mistral-cli` provider is the bounded `vibe`-path integration
- configured route model names remain explicit in Trinity config and traces, but are still advisory rather than CLI-enforced

## 7. Optional Runtime Configuration

Inspect the current adapter config:

```bash
PYTHONPATH=core uv run python -m trinity_core.cli show-config --adapter reply --include-path
```

Write or update config:

```bash
PYTHONPATH=core uv run python -m trinity_core.cli write-config --adapter reply
```

Check the resolved runtime status:

```bash
PYTHONPATH=core uv run python -m trinity_core.cli runtime-status --adapter reply
```

## 8. Optional Gobii Setup

You do not need Gobii to install or use the core local runtime.

Gobii is only needed for the bounded browser-agent ops lanes. If you want those flows later, configure Gobii only after the base runtime and CLI already work locally.

See:

- [docs/GOBII_RECURRING_WORKFLOW.md](/Users/Shared/Projects/trinity/docs/GOBII_RECURRING_WORKFLOW.md)
- [docs/GOBII_NORMALIZATION_CONTRACT.md](/Users/Shared/Projects/trinity/docs/GOBII_NORMALIZATION_CONTRACT.md)
- [docs/GOBII_PROFILE_ENRICHMENT_WORKFLOW.md](/Users/Shared/Projects/trinity/docs/GOBII_PROFILE_ENRICHMENT_WORKFLOW.md)

## First Working Baseline

After a successful install, this should work:

```bash
cd /Users/Shared/Projects/trinity
uv sync --dev
uv run ruff check .
uv run pytest
PYTHONPATH=core uv run python -m trinity_core.cli runtime-status --adapter reply
```

If you also want the native shell baseline:

```bash
cd /Users/Shared/Projects/trinity/apps/macos
swift build
```

## What Is Optional Versus Required

Required for normal repository development:

- `Python 3.12+`
- `uv`
- repository checkout

Required only for the macOS shell:

- Swift/Xcode toolchain

Required only for non-deterministic local model providers:

- `ollama` or `mistral-cli`

Required only for bounded external browser-agent flows:

- Gobii credentials and connectivity
