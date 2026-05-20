# Handover

## Purpose

This document captures the current resume point for `{trinity}`.

Snapshot date:

- `2026-05-20`

## Current Resume Point

The current tranche is a documentation and state-alignment sweep after the relation-hardening implementation.

What is true now:

- the relation-hardening code is already landed
- the public health commands are already live
- the repository docs were inconsistent with the actual command surface and current local machine state
- the current work updates the public docs, SSOT status docs, and relationship-health snapshot to match the shipped code and current environment
- the current work also includes a repo-wide code comment and docstring audit over the active Python runtime surface, with stale wording corrected where module ownership had expanded beyond the older description
- the `tests/` follow-on pass is also complete; it did not reveal broad prose drift, but a few test/helper names were tightened where they encoded an older explanation of the behavior

## Most Important Current Reality

### Runtime And Adapters

- `reply` is the first mature downstream embedding
- `spot` is still a bounded reasoning/review adapter
- adapter registration and generic CLI dispatch are already established

### Active Local Provider State

- Reply is currently configured to use `mistral-cli`
- Spot is currently configured as `deterministic`
- Reply passed a live generator `provider-smoke`
- Spot remains intentionally LLM-disabled in the active config

### External Seams

- Train CLI is healthy locally
- Train API is still down locally at `http://127.0.0.1:8000`
- Reply compatibility check against sibling `/Users/Shared/Projects/reply` is currently passing
- Gobii is still unconfigured because `GOBII_API_KEY` is absent

## Commands To Re-Run First

If you resume this repo later, start with:

```bash
cd /Users/Shared/Projects/trinity
set -a
source .env.local
set +a
PYTHONPATH=core uv run python -m trinity_core.cli runtime-status --adapter reply
PYTHONPATH=core uv run python -m trinity_core.cli runtime-status --adapter spot
PYTHONPATH=core uv run python -m trinity_core.cli train-status --transport both
PYTHONPATH=core uv run python -m trinity_core.cli check-reply-compatibility --reply-root-dir /Users/Shared/Projects/reply
PYTHONPATH=core uv run python -m trinity_core.cli gobii-status --adapter reply --check-live
```

If you need to confirm the live Reply provider path again:

```bash
cd /Users/Shared/Projects/trinity
set -a
source .env.local
set +a
PYTHONPATH=core uv run python -m trinity_core.cli provider-smoke --adapter reply --role generator
```

## Files That Matter Most

Primary SSOT:

- [README.md](/Users/Shared/Projects/trinity/README.md)
- [docs/CLI_REFERENCE.md](/Users/Shared/Projects/trinity/docs/CLI_REFERENCE.md)
- [docs/LOCAL_INSTALL.md](/Users/Shared/Projects/trinity/docs/LOCAL_INSTALL.md)
- [docs/STATUS.md](/Users/Shared/Projects/trinity/docs/STATUS.md)
- [docs/RELATIONSHIP_HEALTH.md](/Users/Shared/Projects/trinity/docs/RELATIONSHIP_HEALTH.md)

Implementation seams:

- [core/trinity_core/cli.py](/Users/Shared/Projects/trinity/core/trinity_core/cli.py)
- [core/trinity_core/ops/relation_health.py](/Users/Shared/Projects/trinity/core/trinity_core/ops/relation_health.py)
- [core/trinity_core/ops/train_client.py](/Users/Shared/Projects/trinity/core/trinity_core/ops/train_client.py)

## Open Operational Gaps

- Gobii still needs a real `GOBII_API_KEY` before live status can move beyond `not_configured`
- Train API still needs either a local server or an intentional decision to stay CLI-first
- `mistral-cli` is live locally now, but still remains a bounded `vibe`-path provider rather than a fully route-enforced backend

## Recommended Next Step

Do not start another architecture rewrite.

If the next task is operational:

1. decide whether Gobii should actually be turned on in this environment
2. if yes, create a Gobii platform API key and load it through `.env.local`
3. re-run `gobii-status --check-live`

If the next task is product/runtime:

1. keep the public docs aligned with the actual CLI and machine-readable status payloads
2. preserve the generic adapter boundary
3. avoid reintroducing Reply-specific assumptions into core workflow code
