# Trinity Relationship Health

## Purpose

This document records the current dependency and integration map around `{trinity}`, plus one concrete health snapshot.

Snapshot date:

- `2026-05-20`

Follow-on implementation plan:

- [docs/RELATIONSHIP_HARDENING_PLAN.md](/Users/Shared/Projects/trinity/docs/RELATIONSHIP_HARDENING_PLAN.md)

## Verification Used

This snapshot was refreshed with:

- `set -a && source .env.local && set +a && PYTHONPATH=core uv run python -m trinity_core.cli runtime-status --adapter reply`
- `set -a && source .env.local && set +a && PYTHONPATH=core uv run python -m trinity_core.cli runtime-status --adapter spot`
- `set -a && source .env.local && set +a && PYTHONPATH=core uv run python -m trinity_core.cli show-foundation-policy --include-path`
- `set -a && source .env.local && set +a && PYTHONPATH=core uv run python -m trinity_core.cli train-status --transport both`
- `set -a && source .env.local && set +a && PYTHONPATH=core uv run python -m trinity_core.cli foundation-check --adapter reply`
- `set -a && source .env.local && set +a && PYTHONPATH=core uv run python -m trinity_core.cli provider-smoke --adapter reply --role generator`
- `set -a && source .env.local && set +a && PYTHONPATH=core uv run python -m trinity_core.cli check-reply-compatibility --reply-root-dir /Users/Shared/Projects/reply`
- `set -a && source .env.local && set +a && PYTHONPATH=core uv run python -m trinity_core.cli gobii-status --adapter reply --check-live`
- `PYTHONPATH=core uv run pytest tests/test_relation_health.py tests/test_foundation_policy.py tests/test_train_client.py tests/test_adapter_runtime.py tests/test_public_contracts.py -q`
- `PYTHONPATH=core uv run ruff check core/trinity_core/ops/foundation_policy.py core/trinity_core/ops/relation_health.py core/trinity_core/ops/train_client.py core/trinity_core/ops/__init__.py core/trinity_core/cli.py tests/test_relation_health.py tests/test_foundation_policy.py tests/test_train_client.py tests/test_adapter_runtime.py tests/test_public_contracts.py`

## Relation Inventory

| Relation | Type | Direction | Current state | Required | Health |
| --- | --- | --- | --- | --- | --- |
| `{reply}` | downstream product adapter | bidirectional | implemented and primary | yes for the current full workflow anchor | high |
| `{spot}` | downstream product adapter | bidirectional | implemented and bounded | no for base runtime | medium |
| `{train}` | offline optimizer | bidirectional | implemented and bounded | no for base runtime | medium |
| `ollama` | local provider service | outgoing | implemented and optional | no | medium |
| `mistral-cli` | local provider executable | outgoing | implemented and optional | no | medium |
| `Gobii` | external ops/control-plane service | outgoing | implemented and optional | no | low |
| `/Users/Shared/Models` inventory seam | local shared model seam | outgoing | implemented and active | no | medium |
| runtime storage and SQLite memory | local storage seam | internal | implemented | yes | high |
| macOS native shell | shipped operator surface | consumer | implemented | no for CLI/runtime | high |
| Python and `uv` toolchain | host/runtime dependency | host dependency | implemented | yes | high |

## Current Local Health

### `{reply}`

- `runtime-status --adapter reply` now reports `provider=mistral-cli`
- `readiness.ready=true`
- `readiness.can_suggest=true`
- `foundation-check --adapter reply --reply-root-dir /Users/Shared/Projects/reply` returned `ready=true`
- `provider-smoke --adapter reply --role generator` passed live
- `check-reply-compatibility` returned `ready=true`

Assessment:

- the Reply seam is currently the healthiest live downstream relation on this machine
- the code contract, sibling repo presence, and bounded live provider path all line up

Primary caution:

- Reply still carries the largest backward-compatibility burden because of legacy `reply-*` aliases and legacy Reply runtime-root compatibility

### `{spot}`

- `runtime-status --adapter spot` reports `provider=deterministic`
- `llm_enabled=false`
- `readiness.state=disabled`
- `foundation-check --adapter spot` returned `ready=true`

Assessment:

- Spot is healthy for what it currently claims to be
- it is still a bounded second-adapter proof, not a full product workflow on parity with Reply

### `{train}`

- `train-status --transport both` reports:
  - API `connection_refused`
  - CLI `online`
  - `recommended_transport=cli`

Assessment:

- the Train seam is implemented and still usable locally
- the reliable path right now is CLI, not API
- the machine-local foundation policy now makes that CLI-first baseline explicit

Primary caution:

- API-based Train flows still depend on a separately running Train server

### `ollama`

- the provider seam is implemented
- this snapshot did not re-run a fresh `ollama` smoke, but earlier hardening validation already proved the bounded smoke path
- Ollama is not the active Reply provider on this machine right now

Assessment:

- operationally credible, but not the current active provider path

### `mistral-cli`

- the provider seam is implemented
- the active Reply config now uses `mistral-cli`
- live generator smoke passed with `.env.local` loaded
- the current mode is still the bounded `vibe` path

Assessment:

- materially healthier than the earlier snapshot
- still intentionally constrained in scope

### `Gobii`

- `gobii-status --adapter reply --check-live` reports:
  - `state=not_configured`
  - `reason=missing_api_key`

Assessment:

- Gobii code and status supervision exist
- Gobii is still not operationally configured on this machine

Primary caution:

- Trinity expects a Gobii platform API key for `GOBII_API_KEY`, not a provider key such as `MISTRAL_API_KEY`

### Shared Model Inventory

- `runtime-status` now reports `shared_model_inventory.enabled=true`
- `runtime-status` now also reports `foundation_policy.provider_alignment`
- `entry_count=7`
- generator inventory mapping resolves to a real path under `/Users/Shared/Models`

Assessment:

- the inventory seam is active and visible
- it is useful for provenance and readiness, but it is not yet the authoritative execution controller for every role

## Referenced But Not Active Dependencies

These are referenced in-repo but are not current live runtime dependencies:

- `{compare}` as an example future adapter shape
- `OpenMythos` as a design mirror
- `QLoRA`, `Unsloth`, `LLaMA-Factory`, and `Axolotl` as post-training research references

## Honest Audit

Current honest view:

- the architectural boundary model is good
- the public health supervision is now much better than before
- the main remaining weakness is not hidden architecture debt
- the main remaining weakness is operational readiness for optional seams

Most hardened now:

1. `{reply}`
2. `mistral-cli`
3. `{train}` through CLI

Still weakest now:

1. `Gobii`
2. `{train}` API transport
3. the remaining gap between shared model inventory and full provider execution semantics

## Recommendation

Do these relations still need hardening:

- yes, but narrowly

Do they need a redesign:

- no

Recommended next hardening order now:

1. decide whether Train API should be restored locally or whether CLI should remain the explicit normal path
2. configure Gobii only if the bounded browser-agent workflows are actually needed
3. keep the docs and CLI contract in lockstep whenever the command surface changes
