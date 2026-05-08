# {trinity}

`{trinity}` is a local-first candidate runtime with product adapters.

It is the runtime layer that turns normalized evidence into ranked, decision-ready candidates. It is not the product shell, and it is not the offline optimizer.

Current system split:

- `{trinity}` owns runtime workflow, ranking, trace export, training-bundle export, and accepted-artifact application
- product repositories own ingestion, operator workflow, transport rules, approval semantics, and send execution
- `{train}` owns offline bounded optimization of exported `{trinity}` artifacts

## Current State

This repository now exposes a generic runtime seam with adapter-aware storage and CLI routing.

Implemented today:

- reusable workflow core under [core/trinity_core/workflow](/Users/Shared/Projects/trinity/core/trinity_core/workflow)
- adapter helpers under [core/trinity_core/adapters](/Users/Shared/Projects/trinity/core/trinity_core/adapters)
- generic runtime facade in [core/trinity_core/runtime.py](/Users/Shared/Projects/trinity/core/trinity_core/runtime.py)
- adapter-scoped storage helpers in [core/trinity_core/ops/runtime_storage.py](/Users/Shared/Projects/trinity/core/trinity_core/ops/runtime_storage.py)
- generic CLI surface in [core/trinity_core/cli.py](/Users/Shared/Projects/trinity/core/trinity_core/cli.py)
- first production adapter contract for `{reply}`

Implemented adapter support:

- `reply`

Compatibility guarantee:

- the generic CLI is the preferred contract
- legacy `reply-*` commands remain supported as compatibility aliases
- the Reply adapter can still read legacy `reply_runtime` storage when a machine already has that layout

## Repository Layout

```text
trinity/
  core/
    trinity_core/
      adapters/
      ops/
      runtime.py
      schemas/
      workflow/
  docs/
  tests/
```

Primary responsibility split:

- `workflow/`: reusable stage execution and frontier logic
- `schemas/`: canonical runtime contracts
- `adapters/`: product-specific adapter declarations and future adapter packages
- `ops/`: local storage, policy lifecycle, trace export, and fixture tooling

## CLI

Preferred generic commands:

- `suggest --adapter reply`
- `record-outcome --adapter reply`
- `export-trace --adapter reply`
- `export-training-bundle --adapter reply`
- `train-propose-policy --adapter reply`
- `policy-review-surface --adapter reply`
- `run-shadow-fixtures --adapter reply`
- `policy-accept --adapter reply`
- `policy-promote --adapter reply`
- `policy-rollback --adapter reply`
- `policy-status --adapter reply`
- `runtime-status --adapter reply`
- `show-config --adapter reply`
- `write-config --adapter reply`

Compatibility aliases:

- `reply-suggest`
- `reply-record-outcome`
- `reply-export-trace`
- `reply-export-training-bundle`
- `reply-train-propose-policy`
- `reply-policy-review-surface`
- `reply-run-shadow-fixtures`
- `reply-policy-accept`
- `reply-policy-promote`
- `reply-policy-rollback`
- `reply-policy-status`
- `reply-runtime-status`
- `reply-show-config`
- `reply-write-config`

Examples:

```bash
cd /Users/Shared/Projects/trinity
PYTHONPATH=core uv run python -m trinity_core.cli runtime-status --adapter reply
PYTHONPATH=core uv run python -m trinity_core.cli run-shadow-fixtures --adapter reply
```

Policy acceptance note:

- serious policy review and acceptance flows now default to holdout replay
- no-holdout acceptance is restricted to explicit local/dev override with `--allow-no-holdout`
- exported training bundles now preserve negative samples and policy-resolution context so `{train}` can learn from bounded runtime artifacts without silently reinterpreting the whole trace
- the current runtime, policy, Train handoff, and shadow-fixture lanes are intentionally centered on the `{reply} <-> {trinity} <-> {train}` workflow

## Runtime Storage

Runtime data must live outside the repository working tree.

Default adapter-scoped layout for new installs:

```text
~/Library/Application Support/Trinity/trinity_runtime/adapters/<adapter>/
```

Reply compatibility behavior:

- if a machine already has `~/Library/Application Support/Trinity/reply_runtime/` and no new namespaced Reply root exists yet, `{trinity}` continues using the legacy root
- new adapter integrations use adapter-scoped paths directly

## Development

Bootstrap:

```bash
cd /Users/Shared/Projects/trinity
uv sync --dev
```

Validation:

```bash
uv run ruff check .
uv run pytest
```

## Adapter Guidance

When adding a new product adapter:

1. keep reusable workflow logic in `core/trinity_core/workflow`
2. keep product contract types and mapping logic at the adapter boundary
3. namespace storage, fixtures, and accepted artifacts by adapter
4. expose the adapter through the generic CLI before adding product-specific aliases
5. prove the abstraction with deterministic tests and fixture replay

Do not:

- move transport or approval semantics into runtime core
- broaden core schemas with product-only fields unless at least two adapters need them
- use repository-local runtime data as the default storage path

## Read First

- [docs/STATUS.md](/Users/Shared/Projects/trinity/docs/STATUS.md)
- [docs/REPOSITORY_CONTRACT.md](/Users/Shared/Projects/trinity/docs/REPOSITORY_CONTRACT.md)
- [docs/TRINITY_OVERVIEW.md](/Users/Shared/Projects/trinity/docs/TRINITY_OVERVIEW.md)
- [docs/CLI_REFERENCE.md](/Users/Shared/Projects/trinity/docs/CLI_REFERENCE.md)
- [docs/ADAPTER_AUTHORING_GUIDE.md](/Users/Shared/Projects/trinity/docs/ADAPTER_AUTHORING_GUIDE.md)
- [docs/REPLY_PRODUCT_ADAPTER_CONTRACT.md](/Users/Shared/Projects/trinity/docs/REPLY_PRODUCT_ADAPTER_CONTRACT.md)
- [docs/REPLY_TRINITY_TRAIN_OPERATING_CONTRACT.md](/Users/Shared/Projects/trinity/docs/REPLY_TRINITY_TRAIN_OPERATING_CONTRACT.md)
- [docs/POLICY_LOOP_REPO_BREAKDOWN.md](/Users/Shared/Projects/trinity/docs/POLICY_LOOP_REPO_BREAKDOWN.md)

## License

This repository is licensed under `Apache-2.0`.
