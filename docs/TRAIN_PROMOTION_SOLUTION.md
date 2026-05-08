# Train Promotion Solution

## Purpose

This document explains what made the `{trinity} <-> {train}` seam start working as an operationally safe runtime promotion path.

It is not the high-level contract.

It is the practical answer to:

- what was broken or incomplete before
- what changed
- why the current shape is safer

## The Problem

The original seam was too close to:

1. export bundles
2. ask `{train}` for a policy
3. accept it

That shape was insufficient for real runtime ownership.

The main risks were:

- proposal artifacts could be treated like runtime truth
- narrow corpora could imply overly broad policies
- accepted versions could lose important provenance
- rollback would exist, but without enough acceptance context to trust it
- the system would look autonomous while actually being under-reviewed

In blunt terms:

the seam could produce a valid JSON artifact without proving it was a safe runtime promotion.

## The Solution

The working solution was to turn the seam into a reviewed promotion workflow instead of a thin proposal handoff.

Current shape:

1. `{trinity}` exports bounded training bundles
2. `{trinity}` calls `{train}` by API or CLI
3. `{train}` returns a proposal artifact plus eval report
4. `{trinity}` reviews the proposal against runtime rules
5. `{trinity}` accepts explicitly only if the review passes
6. accepted runtime state is written with rollback-ready provenance

This keeps `{train}` as proposal generator and `{trinity}` as runtime owner.

## The Real Fixes

### 1. Proposal Review Became First-Class

The seam now has an explicit review phase before acceptance.

That matters because:

- a proposal can be inspected without mutating live runtime state
- holdout replay can be required or added before promotion
- skepticism can be recorded instead of discarded

This is implemented through:

- `policy-review`
- `policy-review-surface`
- `reply-policy-review`
- `reply-policy-review-surface`
- review logic in [`/Users/Shared/Projects/trinity/core/trinity_core/ops/reply_policy_gate.py`](/Users/Shared/Projects/trinity/core/trinity_core/ops/reply_policy_gate.py)

### 2. Scope Discipline Became Enforced Runtime Policy

The most important behavioral fix was scope rejection.

`{trinity}` now rejects suspiciously broad policies from narrow corpora.

Examples:

- one-company corpus must not become channel-wide
- one-channel corpus must not become global
- mixed-channel corpus must not become narrower than global

Why this matters:

without this, `{train}` could silently undo the multi-company isolation work by proposing a broader policy than the evidence justifies.

### 3. Provenance Became Promotion-Grade

Accepted artifact state now preserves more than:

- artifact key
- version

It can now carry:

- contract version
- scope kind
- scope value
- Train project key
- Train run id
- acceptance mode
- holdout bundle count
- skeptical acceptance notes

Why this matters:

later rollback, audit, and monitoring depend on knowing not just what version was accepted, but why and under what scope assumptions.

### 4. Holdout Replay Became The Default Acceptance Path

Acceptance no longer has to rely only on the proposal corpus, and the CLI now defaults to requiring holdout replay for serious review and acceptance paths.

`{trinity}` can now:

- review on proposal bundles
- compare on optional holdout bundles
- reject when holdout performance regresses
- require explicit `--allow-no-holdout` override for local/dev acceptance without a second replay surface

That is a major difference between:

- “artifact accepted because it looked fine”
- and
- “artifact accepted because it survived a second replay surface”

### 5. Skepticism Became Storable

The seam now supports skeptical notes on acceptance.

That sounds minor, but it matters operationally.

It lets the runtime keep memory such as:

- accepted without holdout replay
- monitor first 20 sends
- proposal came from narrow corpus

This prevents false certainty from being baked into the accepted-artifact registry.

## Why It Works Now

The seam works now because it has the right ownership split:

- `{train}` proposes
- `{trinity}` judges runtime adoption

And because promotion now requires more than syntactic validity:

- review
- scope fit
- replay evidence
- provenance
- rollback readiness

That is the real difference.

The system did not become safer because it learned more.

It became safer because it became stricter about what counts as a valid runtime promotion.

## What Is Still Not Done

The seam is better, but not finished.

Still open:

- promotion review does not yet have a richer operator-facing UI surface
- company-plus-channel composite scope is still not a runtime contract
- auto-accept should still not be considered the normal production mode

## Practical Rule

If asked what the production-safe default is, the answer is:

1. export bundles
2. call `{train}`
3. review proposal
4. replay against incumbent
5. check scope
6. accept explicitly
7. keep rollback ready

Not:

1. call `{train}`
2. trust the proposal

## Related Docs

- [`/Users/Shared/Projects/trinity/docs/REPLY_TRINITY_TRAIN_OPERATING_CONTRACT.md`](/Users/Shared/Projects/trinity/docs/REPLY_TRINITY_TRAIN_OPERATING_CONTRACT.md)
- [`/Users/Shared/Projects/trinity/docs/CLI_REFERENCE.md`](/Users/Shared/Projects/trinity/docs/CLI_REFERENCE.md)
- [`/Users/Shared/Projects/trinity/docs/STATUS.md`](/Users/Shared/Projects/trinity/docs/STATUS.md)
- [`/Users/Shared/Projects/trinity/docs/HANDOVER.md`](/Users/Shared/Projects/trinity/docs/HANDOVER.md)
