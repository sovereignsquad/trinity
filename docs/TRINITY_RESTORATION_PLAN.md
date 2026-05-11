# Trinity Restoration Plan

## Purpose

This document defines the concrete recovery plan for `{trinity}` as the proper core system:

- a continuous three-stage reasoning runtime
- active memory owner
- disagreement-aware system with explicit minority reports
- bounded looping with Human-in-the-Loop escalation
- reusable across multiple downstream projects

This plan must preserve the existing `{reply}` integration while creating a clean path for `{spot}` to consume `{trinity}` reasoning without inheriting Reply-specific semantics.

## Problem Statement

Current repository reality is narrower than the intended system.

What exists now:

- a reusable workflow core
- a live `{reply}` integration
- a bounded `{reply} <-> {trinity} <-> {train}` policy loop
- first runtime memory persistence seams

What is still missing from the intended core system:

- first-class active memory retrieval as a runtime dependency
- explicit disagreement handling and `minority_report` artifacts
- loop budgets and runtime rework control
- formal Human-in-the-Loop escalation contracts
- a second product integration proving the runtime shape without forcing Reply semantics onto another project

## North Star

The intended live runtime loop is:

```text
Evidence ingestion
  -> scoped memory retrieval
  -> Generator
  -> Refiner
  -> Evaluator
  -> consensus and minority-report synthesis
  -> confidence gate
  -> accept or rework loop
  -> Human-in-the-Loop escalation when loop budget is exhausted
  -> memory update
  -> bounded export for slower Train optimization
```

This means:

- `{trinity}` owns live reasoning and live memory
- `{train}` owns slower bounded optimization and proposal generation
- downstream products own intake, operator workflow, transport, and final product semantics

## Non-Negotiable Constraints

1. Do not break the current `{reply}` runtime contract while restoring the core system.
2. Do not let raw feedback mutate global runtime behavior without promotion or explicit runtime-memory rules.
3. Do not force `{spot}` into Reply-shaped draft semantics.
4. Do not collapse `workflow.*`, `memory.*`, `adapter.product.*`, and `ops.*` into one implementation layer.
5. Do not treat live memory updates and offline model optimization as the same mechanism.

## Product Positioning

### `{reply}`

`{reply}` remains the first production embedding and the quality anchor.

`{trinity}` should continue helping `{reply}` by:

- generating and refining reply candidates
- retrieving thread/contact/document memory
- preserving prepared drafts
- recording structured outcomes
- exporting bounded artifacts for later optimization

### `{spot}`

`{spot}` should use `{trinity}` for per-message reasoning, not for workbook ownership.

`{spot}` remains owner of:

- `.xlsx` intake/output
- closed taxonomy enforcement
- deterministic run orchestration
- audit artifacts
- review and signoff workflow

`{trinity}` should contribute:

- normalized reasoning over one message or one evidence cluster
- memory-informed interpretation
- disagreement-aware output
- confidence-aware escalation recommendation

## Restoration Phases

### Phase 0. Restore SSOT

Goal:
- make the active repository docs match the intended core system

Required outcomes:

- top-level docs no longer describe `{trinity}` primarily as a Reply policy runtime
- active docs explicitly define memory, minority report, looping, and HiTL as first-class runtime concerns
- `{reply}` is documented as the first embedding, not the whole identity
- `{spot}` is documented as a target consumer with different product semantics

Deliverables:

- update `README.md`
- update `docs/OPERATING_MODEL.md`
- update `docs/REPOSITORY_CONTRACT.md`
- update `docs/LIVE_BRAIN_RUNTIME_ARCHITECTURE.md`
- update `docs/STATUS.md`
- update `docs/HANDOVER.md`
- add dedicated contracts:
  - `docs/TRINITY_CORE_LOOP.md`
  - `docs/MEMORY_ARCHITECTURE.md`
  - `docs/MINORITY_REPORT_CONTRACT.md`
  - `docs/HITL_ESCALATION_CONTRACT.md`
  - `docs/CROSS_PROJECT_MEMORY_BOUNDARIES.md`

### Phase 1. Make Memory First-Class

Goal:
- turn the current runtime memory slice into an explicit subsystem

Required outcomes:

- stage execution depends on scoped memory retrieval
- memory is no longer conceptually Reply-owned
- memory can influence generation, refinement, evaluation, and ranking

Target module shape:

```text
core/trinity_core/memory/
  schemas.py
  storage.py
  retrieval.py
  lessons.py
  scoping.py
```

Required memory scopes:

- global
- adapter
- project
- company
- thread or item family
- topic
- stage
- human-resolution

Required memory families:

- evidence memory
- preference memory
- correction memory
- anti-pattern memory
- successful-pattern memory
- disagreement memory
- human-resolution memory

### Phase 2. Add Disagreement And Minority Report

Goal:
- make multi-stage disagreement operationally meaningful

Required outcomes:

- each runtime cycle can produce a majority interpretation and a dissenting interpretation
- disagreement is preserved in traces instead of being silently collapsed
- informative dissent can trigger rework or escalation

Required contracts:

- `StageOpinion`
- `ConsensusDecision`
- `MinorityReport`
- `ConfidenceBundle`
- `LoopDecision`

Important rule:

`minority_report` must be a first-class alternate interpretation or action path, not a cosmetic score delta.

### Phase 3. Add Loop Budgets And HiTL

Goal:
- formalize when `{trinity}` keeps reasoning and when it asks for human help

Required outcomes:

- runtime can rework a cycle a bounded number of times
- runtime can escalate unresolved or risky work to human review
- human feedback comes back as structured memory and bounded learning artifacts

Required controls:

- minimum combined confidence threshold
- disagreement severity threshold
- maximum rework count
- maximum runtime loop count
- escalation policy by risk level and adapter

HiTL payload must include:

- majority result
- minority report
- evidence anchors
- memory factors used
- unresolved questions
- recommended human decision target

### Phase 4. Preserve And Refactor `{reply}`

Goal:
- keep `{reply}` stable while moving generic runtime logic out of `ReplyRuntime`

Move into shared runtime ownership:

- loop controller
- confidence aggregation
- disagreement synthesis
- minority-report generation
- generic memory retrieval
- generic HiTL decisioning

Keep in Reply adapter ownership:

- thread snapshot normalization
- reply candidate rendering
- reply outcome mapping
- prepared-draft product semantics
- reply-specific policy artifacts

Success criteria:

- all current `reply-*` compatibility commands still work
- Reply shadow fixtures stay stable or improve
- runtime traces show generic loop and memory artifacts instead of Reply-only heuristics

### Phase 5. Define The `{spot}` Reasoning Contract

Goal:
- create the second bounded use case without forcing a full adapter prematurely

`{spot}` should send `{trinity}`:

- one message or evidence unit
- optional source metadata
- language
- run context
- tenant or corpus context
- relevant prior memory and review history

`{trinity}` should return:

- reasoning candidates
- classification rationale candidates
- confidence bundle
- minority report when present
- escalation recommendation
- traceable memory factors

`{spot}` should remain owner of:

- category enforcement
- workbook writes
- run review workflow
- legal and audit packaging

### Phase 6. Add The First Bounded `{spot}` Adapter Slice

Goal:
- prove the runtime abstraction through one real second consumer

The first slice should be deliberately small:

- one message in
- one reasoning result out
- no workbook writes from `{trinity}`
- no live policy mutation
- no attempt to absorb full `{spot}` orchestration into `{trinity}`

Suggested first artifact family:

- `spot_threat_reasoning_result`

### Phase 7. Re-ground `{train}`

Goal:
- keep Train valuable without turning it into the live brain

`{train}` should consume:

- bounded traces
- bounded training bundles
- disagreement and minority-report exports
- human-resolution artifacts
- holdout replay bundles

`{train}` should propose:

- threshold changes
- routing policies
- prompt and policy artifacts
- evaluator heuristics
- memory compaction or lesson rules

`{train}` must not:

- become the live memory owner
- mutate runtime directly
- continuously fine-tune on all touched knowledge without curation and promotion

## Recommended Delivery Order

1. restore SSOT and add missing contracts
2. extract first-class memory architecture
3. add minority-report and disagreement contracts
4. add loop-budget and HiTL contracts
5. refactor Reply runtime onto the new shared services
6. define the Spot reasoning contract
7. ship one bounded Spot adapter slice
8. update Train consumers and proposal types for the richer runtime exports

## Immediate Tranche

The next correct tranche is not a second adapter or a new provider.

The next correct tranche is:

1. restore top-level system identity
2. formalize memory architecture
3. define disagreement and minority-report contracts
4. define loop-budget and HiTL contracts
5. record the new active lane in status and handover docs

This tranche is the minimum serious step because the current repository cannot safely grow into a proper core system until the missing contracts are explicit.

## Acceptance Checks

This restoration program is succeeding when:

- `{reply}` remains fully supported and does not regress in fixture quality
- the active docs describe `{trinity}` as a continuous memory-and-reasoning system
- memory is actively consulted during runtime work
- disagreement produces explicit artifacts instead of being lost in stage collapse
- low-confidence or unresolved cases escalate through a bounded HiTL path
- `{spot}` can consume `{trinity}` reasoning without inheriting Reply-specific behavior
- `{train}` remains bounded and proposal-oriented instead of becoming the live runtime owner
