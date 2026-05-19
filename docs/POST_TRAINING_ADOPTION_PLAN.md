# Post-Training Adoption Plan

## Purpose

This document defines the bounded adoption plan for efficient teaching, annotation, and local fine-tuning around `{trinity}`.

It converts external post-training tooling research into a Trinity-native implementation sequence.

## Recommendation

Recommended operating direction:

- keep the active delivery plan backend-neutral until an Apple-Silicon-safe local training path is chosen
- keep `Ollama` as the likely local serving target for trained adapters
- treat `QLoRA` as a candidate method, not an active backend commitment
- do not make `Unsloth`, `LLaMA-Factory`, or `Axolotl` part of the active delivery lane on Apple Silicon-only machines

This is intentionally not a platform rewrite.

`{trinity}` remains:

- the governed runtime
- the source of truth for accepted artifacts and training bundles
- the owner of trace provenance, acceptance, and rollback

External post-training tools are only allowed to consume bounded Trinity-owned exports and produce bounded Trinity-reviewable outputs.

## Tool Assessment

### `QLoRA`

Best fit for the first method:

- efficient local adaptation
- lower memory footprint
- realistic for bounded experiments on curated Trinity exports

### `Unsloth`

Research-only for now:

- the active delivery plan should not depend on it for Apple Silicon-only work
- the official requirements docs still position `Apple/Silicon/MLX` support as in progress

### `Ollama + LoRA`

Useful as a serving target, not as the primary training system:

- good target for local adapter loading
- not sufficient by itself for annotation, curation, or governed training orchestration

### `LLaMA-Factory`

Not part of the active delivery plan:

- useful only as later research if a future backend decision changes the platform constraints

### `Axolotl`

Not part of the active delivery plan:

- useful only as later research if the hardware and platform assumptions change

## Non-Goals

This lane does not:

- move live learning into runtime
- let model mutation bypass policy acceptance
- make `{trinity}` depend on one training vendor
- turn annotation into an opaque external sidecar
- collapse product adapter semantics into generic post-training code

## Operating Constraints

All post-training work must preserve:

- local-first execution where feasible
- explicit dataset provenance
- company-safe isolation
- auditable acceptance and rollback
- clear separation between runtime, memory, adapters, ops, and apps

## Implementation Sequence

### Phase 1: Training Dataset Contract

Add a first-class Trinity contract for post-training datasets.

Deliver:

- explicit dataset/export schema for `sft`, `lora`, and `qlora` use cases
- provenance fields linking every example back to accepted artifacts, traces, and review context
- company-safe filtering and negative-sample handling
- deterministic export CLI and persisted bundle artifacts

Why first:

- Trinity must own the teachable corpus contract before any backend-specific training work starts

### Phase 2: Annotation and Curation Workflow

Add a bounded workflow for converting accepted runtime artifacts into teachable corpora.

Deliver:

- explicit annotation states
- curated example families such as positive, negative, corrected, and abstain
- operator review surface for promoting examples into post-training datasets
- rejection and exclusion reasons

Why second:

- none of the external tools is the right source of truth for annotation governance

### Phase 3: Apple-Silicon-Safe Local Fine-Tune Runner

Add the first end-to-end prototype lane behind explicit ops contracts.

Deliver:

- local training job contract
- backend-neutral launcher seam for an Apple-Silicon-safe runner
- small-model prototype path against Trinity-owned datasets
- persisted training run metadata, config, and output artifact references

Why third:

- Trinity still needs an explicit local fine-tune seam, but the backend choice must respect the Apple Silicon-only constraint

### Phase 4: Evaluation and Regression Gates

Add deterministic evaluation before any trained adapter can be treated as useful.

Deliver:

- baseline-versus-adapter comparison contract
- holdout eval datasets tied to Trinity exports
- regression checks against accepted policy behavior and quality gates
- explicit promotion recommendation artifact

Why fourth:

- training without replay and regression gating would bypass the existing Trinity governance model

### Phase 5: Local Adapter Import and Serving

Add a bounded serving seam for trained adapters.

Deliver:

- adapter import contract for locally trained artifacts
- local `Ollama` integration path for serving trained adapters when compatible
- explicit model registry metadata inside Trinity ops
- activation, rollback, and provenance checks

Why fifth:

- serving matters only after the prototype has already shown measurable value

### Phase 6: Deferred Backend Decision

Choose whether a durable backend decision is even needed after the Apple-Silicon-safe prototype lane proves value.

Decision criteria:

- reproducibility needs
- multi-run experiment management
- annotation-to-training workflow complexity
- operator usability requirements
- maintenance burden

Recommendation:

- do not choose this before the prototype and evaluation lane prove worth
- do not make `Unsloth`, `LLaMA-Factory`, or `Axolotl` part of the active delivery plan on the current hardware baseline

## Deliverable Issue Breakdown

1. Add a post-training dataset contract for Trinity-governed SFT and QLoRA exports.
2. Add bounded annotation and teachable-corpus curation workflows.
3. Add an Apple-Silicon-safe local fine-tune runner seam for Trinity-owned datasets.
4. Add baseline-versus-adapter evaluation and regression gates.
5. Add bounded local adapter import and `Ollama` serving support for trained artifacts.
6. Add a deferred backend-decision lane only if the Apple-Silicon-safe prototype proves worth expanding.

## Recommended Execution Order

1. dataset contract
2. annotation and curation
3. Apple-Silicon-safe local fine-tune runner
4. evaluation and regression gates
5. local adapter import and serving
6. durable backend decision

## Acceptance Criteria

This adoption lane is only successful if:

- Trinity remains the source of truth for training inputs
- all teachable examples are provenance-linked and reviewable
- training runs are persisted as explicit local artifacts
- trained adapters are evaluated against holdout datasets before promotion
- serving activation is reversible and auditable
- no runtime path silently mutates live model behavior without acceptance
