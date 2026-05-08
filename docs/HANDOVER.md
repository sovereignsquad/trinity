# Handover

## Purpose

This document captures the current resume point for `{trinity}`.

## Current Resume Point

Most recent meaningful tranche:

- `{trinity}` moved from an implicitly Reply-shaped runtime shell to an explicit adapter-aware runtime surface
- `{trinity}` Reply runtime was hardened for parallel multi-company execution under one adapter root
- `{trinity}` now has a callable autonomous handoff into `{train}` for bounded Reply policy proposal generation
- `{trinity}` now has a second real downstream adapter through the bounded Impact recommendation surface

Implemented in that tranche:

- generic adapter helpers in `core/trinity_core/adapters`
- generic `TrinityRuntime` facade in `core/trinity_core/runtime.py`
- generic CLI commands with `--adapter` in `core/trinity_core/cli.py`
- adapter-scoped runtime storage for new installs
- Reply compatibility aliases for CLI and legacy storage
- documentation rewrite for repository, adapter, and CLI contracts
- tenant-aware cycle, export, and bundle persistence under adapter runtime `companies/<company_id>/...`
- company-scoped Reply behavior policy resolution ahead of channel and global fallback
- atomic JSON persistence for cycle state, accepted policies, and accepted artifact registry pointers
- deterministic tests proving two companies on the same adapter and channel do not share accepted policy resolution
- Train handoff client supporting both API and CLI transports
- CLI command `train-propose-policy` that exports bundles, invokes Train, and can immediately run the existing acceptance gate
- explicit Reply-side follow-through checklist in `docs/REPLY_TRINITY_INTEGRATION_CHECKLIST.md`
- policy review surface with optional holdout replay before acceptance
- stronger registry provenance carrying scope metadata, Train project/run ids, and skeptical acceptance notes
- stricter scope rejection for broad proposals coming from narrow corpora
- explicit explanation of the solution in `docs/TRAIN_PROMOTION_SOLUTION.md`
- holdout-by-default CLI behavior for policy review, policy acceptance, and `train-propose-policy --accept`
- promotion review surface that makes acceptance mode, holdout use, and Train provenance obvious in one JSON payload
- training bundles now include surfaced losers, filtered candidates, stage evidence anchors, model routes, and policy-resolution summaries
- policy review decisions are now persisted as standalone review artifacts and accepted pointers can link back to the review decision id
- Impact adapter contracts in `core/trinity_core/schemas/impact_integration.py`
- Impact adapter runtime in `core/trinity_core/impact_runtime.py`
- adapter dispatch for both `reply` and `impact` through the generic CLI
- explicit reply-only gating for Train, policy, and shadow-fixture commands

## What Was Preserved

- `ReplyRuntime` remains the concrete implementation for the Reply adapter
- `ImpactRuntime` is now the concrete implementation for the Impact adapter
- existing `reply-*` CLI commands still work
- existing Reply runtime state can still resolve through the legacy `reply_runtime` root when present
- existing Reply tests remain the primary contract coverage baseline
- legacy flat cycle/export paths remain readable for compatibility when discovered by id

## What Was Verified

- `uv run pytest`
- `uv run ruff check .`
- generic CLI config path works for `--adapter reply`
- generic runtime rejects unsupported adapter names explicitly
- generic runtime now accepts `reply` and `impact`
- adapter runtime paths are namespaced for new installs and can fall back to legacy Reply roots when needed
- accepted Reply policies now resolve by precedence `company -> channel -> global`
- sibling Train repo now exposes `/v1/trinity/reply/policies/propose` and `python -m train_core.cli propose-reply-policy`
- `policy-review` and `reply-policy-review` now exist for proposal inspection before acceptance
- `policy-review-surface` and `reply-policy-review-surface` now expose promotion-ready review output with acceptance mode and Train provenance
- runtime policy resolution can now be explained via deterministic resolution paths instead of silent scope fallback

## Practical Meaning

The repository is now safer to extend for other projects because:

- the generic runtime surface exists
- adapter naming is explicit
- storage layout is no longer hard-wired to Reply for new work
- the CLI contract is no longer product-specific by default
- the abstraction is now proven by a second real adapter instead of only by documentation
- one adapter root no longer implies one flat tenant namespace for runtime traces and bundles
- accepted behavior policy application can differ by company without forking the runtime
- the manual “export bundle, run Train by hand, carry proposal back” step is no longer required for the first Reply policy slice
- proposal review and acceptance now preserve more operational skepticism and provenance instead of collapsing everything into a bare version pointer
- serious acceptance flows now fail closed without holdout replay unless an explicit local/dev override is used
- `{train}` can now consume more hermetic bundles without needing to re-open the full trace just to recover losing candidates or policy-resolution context

## Watch Carefully

- do not move product transport or approval semantics into core runtime modules
- do not expand generic schemas only because Reply currently uses a field
- do not remove Reply compatibility aliases until a second adapter is live and the generic CLI has proven stable
- the second adapter is now live, but Reply compatibility aliases should still remain until downstream callers stop depending on them
- do not reintroduce fresh hard-coded `reply_runtime` paths in new code
- do not over-generalize policy scope precedence yet; company-plus-channel composite scope is still a future decision, not a current contract
- do not let Train proposal transport become implicit runtime mutation; the acceptance gate remains mandatory
- do not accept broad policies from narrow corpora just because Train produced a syntactically valid artifact
- do not normalize `--allow-no-holdout` into regular promotion practice; it exists only for local/dev exception paths
- do not broaden scope precedence or bundle schema further unless `{train}` actually needs the additional contract surface
- do not pretend the Reply policy and Train workflow is adapter-generic yet; Impact currently exercises the runtime seam, not the policy seam
