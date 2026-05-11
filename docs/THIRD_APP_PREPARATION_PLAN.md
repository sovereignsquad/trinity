# Third App Preparation Plan

## Purpose

This document defines the implementation plan for preparing `{trinity}` to onboard a third downstream app after `{reply}` and `{spot}`.

The goal is to make the next adapter addition boring, explicit, and low-risk rather than another round of architecture cleanup during integration.

## Target Outcome

`{trinity}` should be able to accept one new downstream app through an explicit adapter seam without:

- moving product logic into `workflow.*`
- moving product logic into `memory.*`
- adding fresh Reply-shaped assumptions into generic runtime code
- requiring a new top-level runtime storage root
- inventing a new integration path outside the generic CLI and runtime facade

## Current Readiness

The repository is already partway prepared:

- adapter-scoped runtime storage exists
- generic `TrinityRuntime(adapter_name=...)` exists
- generic CLI `--adapter` routing exists
- Reply-specific mapping has already been extracted into `adapter.product.reply.*`
- Spot proves a second bounded adapter shape
- runtime-owned memory, trace, control-plane, and eval seams are generic enough for reuse

The main remaining gap is not architecture ownership. It is integration ergonomics and a cleaner third-adapter contract.

## Non-Negotiable Rules

1. Keep `workflow.*`, `memory.*`, `adapter.product.*`, and `ops.*` separate.
2. Keep the new app product-owned outside `{trinity}` except for normalized runtime contracts.
3. Use adapter-scoped runtime roots only:
   `.../trinity_runtime/adapters/<adapter>/`
4. Do not add adapter-specific CLI aliases before the generic `--adapter` path works.
5. Only generalize policy or artifact families when the third app proves real overlap.

## Required Preparation Work

### Phase 1. Harden Adapter Registration

Goal:
- make adapter addition a first-class repository operation instead of an ad hoc edit set

Required work:

- centralize supported adapter registration in `core/trinity_core/adapters/base.py`
- ensure adapter exports stay consistent across `core/trinity_core/adapters/__init__.py`
- make `core/trinity_core/runtime.py` dispatch easier to extend for one more adapter
- make `core/trinity_core/cli.py` adapter validation and help text reflect the new extension model

Definition of done:

- adding a new adapter name is one explicit change set, not several hidden string edits

### Phase 2. Normalize Third-Adapter Contract Shapes

Goal:
- make the minimum adapter contract explicit before the third app lands

Required work:

- document the minimum required adapter components:
  - request normalization
  - output normalization
  - outcome or review feedback normalization
  - memory-event mapping if the app needs runtime memory
  - document registration mapping if the app contributes retrieval artifacts
- define which of those are required for:
  - draft-generation adapters
  - bounded reasoning/review adapters
  - net-new product shapes

Definition of done:

- contributors can tell whether a new app is Reply-like, Spot-like, or net-new before writing runtime code

### Phase 3. Reduce Reply-Centric Generic CLI Assumptions

Goal:
- keep the generic CLI generic when a third adapter lands

Required work:

- identify which generic commands are truly shared today and which are still Reply-only in practice
- document and, where low-risk, tighten command gating so unsupported commands fail clearly per adapter
- keep third adapters from inheriting Reply draft semantics accidentally through command names or code paths

Definition of done:

- the generic CLI remains the main entrypoint, but unsupported flows fail explicitly rather than by accident

### Phase 4. Define Third-App Memory Participation Rules

Goal:
- avoid memory cross-contamination when the new app joins

Required work:

- define when a new adapter may write:
  - memory events
  - contact or item state
  - retrieval artifacts
  - human-resolution summaries
- define which scopes are expected for item-level state in the third app
- define whether the app uses:
  - thread-like state
  - row-like state
  - another item-family shape

Definition of done:

- the third app can use runtime memory without leaking its product ontology into core memory logic

### Phase 5. Prepare Optional Adapter-Specific Policy and Train Seams

Goal:
- avoid overbuilding policy infrastructure for a third app that may not need it yet

Required work:

- decide whether the third app needs:
  - no policy artifact family
  - adapter-local review policy only
  - training-bundle export only
  - both policy and Train proposal flows
- keep this decision adapter-specific instead of forcing Reply or Spot policy shapes onto the new app

Definition of done:

- the third adapter can start narrow without being blocked on policy generalization

### Phase 6. Add a Third-Adapter Acceptance Checklist

Goal:
- make onboarding auditable and resumable

Required work:

- create a reusable checklist covering:
  - adapter registration
  - schemas
  - payload mapping
  - runtime dispatch
  - CLI coverage
  - storage path verification
  - memory participation
  - trace coverage
  - docs
  - tests

Definition of done:

- any future app onboarding can be reviewed against one explicit checklist

## Files Likely To Change When The Third App Lands

Almost certainly:

- `core/trinity_core/adapters/base.py`
- `core/trinity_core/adapters/__init__.py`
- `core/trinity_core/runtime.py`
- `core/trinity_core/cli.py`
- `core/trinity_core/adapters/product/<newapp>/...`
- `tests/test_adapter_runtime.py`

Only if needed:

- `core/trinity_core/schemas/...`
- `core/trinity_core/ops/...policy_store.py`
- `core/trinity_core/ops/...policy_gate.py`
- `core/trinity_core/ops/train_client.py`
- `tests/test_integration_contracts.py`
- adapter-specific fixture or policy tests

Should not need broad changes just to connect:

- `core/trinity_core/workflow/*`
- `core/trinity_core/memory/storage.py`
- `core/trinity_core/memory/retrieval.py`
- `core/trinity_core/adapters/model/*`

## Recommended Implementation Order

1. tighten adapter registration and generic runtime dispatch
2. document minimum third-adapter contract shapes
3. make CLI adapter gating more explicit
4. define third-app memory participation rules
5. add the reusable onboarding checklist
6. only then start the concrete adapter for the new app

## Practical Starting Point

If the third app is known already, the first code tranche should be:

1. add the adapter name
2. add adapter-local schemas and payload mappers
3. add adapter runtime dispatch
4. expose one bounded CLI flow
5. prove one deterministic end-to-end test

Do not start with policy generalization, Train integration, or UI work unless the new app truly needs them in its first bounded slice.
