# OpenMythos Design Mirror For `{trinity}`

## Purpose

This document captures the highest-value ideas visible in `/Users/Shared/Projects/OpenMythos`.

`OpenMythos` is a design mirror, not a dependency.

`{trinity}` must not import its code, adopt its model architecture wholesale, or blur runtime workflow concerns with neural architecture research.

Use this document to borrow methods and engineering habits, not implementation layers.

## Why It Matters

`OpenMythos` is useful because it turns a central hypothesis into:

- explicit configuration
- explicit invariants
- explicit tests
- explicit adaptive-compute mechanics

That pattern is directly relevant to `{trinity}` even though the problem domain is different.

## Top 10 Useful Ideas

### 1. Make The Core Hypothesis Explicit

`OpenMythos` states its central thesis in the README and then carries it into code and tests.

Use in `{trinity}`:
- define the runtime learning thesis explicitly:
  feedback should improve ranking policy, routing policy, and surfaced candidate diversity over time
- keep the thesis visible in docs and artifact contracts

Do not copy:
- speculative product mythology
- unsupported capability claims

### 2. Treat Adaptive Compute As A First-Class Design Tool

`OpenMythos` uses recurrent depth and ACT halting to spend more compute on harder cases.

Use in `{trinity}`:
- add adaptive workflow depth
- run extra generator, refiner, or evaluator passes only when confidence is low, ambiguity is high, or candidate diversity collapses

Do not copy:
- neural recurrence mechanics

### 3. Re-Inject Canonical Input Every Iteration

`OpenMythos` keeps the encoded input alive across recurrent passes to prevent drift.

Use in `{trinity}`:
- every refinement or reevaluation pass should re-anchor on canonical evidence units and thread snapshots
- never let later passes mutate candidates based only on prior model output

Do not copy:
- latent-state update equations

### 4. Encode Invariants In Code, Not Just In Prose

`OpenMythos` protects important behavior with direct invariants such as stable spectral-radius constraints and halting behavior tests.

Use in `{trinity}`:
- add invariants for ranking determinism, evidence anchoring, candidate diversity, replay stability, and feedback-application legality
- treat these as contract behavior, not optional QA

Do not copy:
- architecture-specific math tests that do not map to workflow behavior

### 5. Test Mechanisms, Not Only End Results

The strongest parts of `OpenMythos` are tests that target mechanisms like RoPE correctness, cache behavior, and recurrent stability.

Use in `{trinity}`:
- test that extra passes change output only when thresholds justify it
- test that duplicate evidence does not create frontier spam
- test that repeated feedback does not silently collapse candidate variety

Do not copy:
- oversized benchmark culture that outruns product needs

### 6. Separate Shared Computation From Specialist Paths

`OpenMythos` uses a shared backbone plus sparse specialist experts.

Use in `{trinity}`:
- keep shared workflow contracts in core
- add strategy-specialist routes for direct response, clarification, escalation, scheduling, and risk-management
- surface which specialist contributed to each candidate

Do not copy:
- MoE implementation details

### 7. Make Fallback Behavior A Planned Part Of The System

`OpenMythos` documents optional acceleration paths and still keeps fallbacks.

Use in `{trinity}`:
- keep deterministic baseline runners as the canonical safety floor
- allow local model routes to improve output but never become the only operational path
- preserve replayability when model providers fail or drift

Do not copy:
- dependency-heavy optional paths unless they preserve local-first usability

### 8. Build Artifact-Level Traceability

`OpenMythos` is unusually good at connecting theory, config, and module boundaries.

Use in `{trinity}`:
- persist accepted ranking-policy versions, model routes, cycle traces, and downstream outcomes as first-class artifacts
- make it possible to answer:
  which policy version ranked this draft set
  which evidence created it
  which feedback changed its future treatment

Do not copy:
- research-style verbosity where simpler runtime artifacts are enough

### 9. Document The Failure Modes Up Front

`OpenMythos` talks openly about instability, halting, cache correctness, and scaling tradeoffs.

Use in `{trinity}`:
- document known failure modes explicitly:
  evidence drift
  overconfident evaluator scoring
  candidate duplication
  feedback poisoning
  strategy collapse into one safe draft shape

Do not copy:
- confidence theater that implies a solved learning loop before it exists

### 10. Keep Design Ambition, But Be Honest About What Is Actually Proven

`OpenMythos` is ambitious, but it is still a theoretical reconstruction.

Use in `{trinity}`:
- keep ambitious design ideas, especially around adaptive depth and learning loops
- mark what is experimental versus what is contractually reliable
- let tests and replay artifacts, not prose, decide what has graduated into runtime truth

Do not copy:
- claims that are not backed by local evidence

## Direct Recommendations For `{trinity}`

The most useful next implementations inspired by this mirror are:

1. Add adaptive workflow depth to `ReplyRuntime` based on evaluator uncertainty and diversity shortfall.
2. Introduce strategy-specialist routing while keeping core workflow contracts unchanged.
3. Create accepted learning-policy artifacts that convert outcomes into durable ranking and routing updates.
4. Add invariant tests for replay stability, evidence reinjection, and frontier diversity preservation.
5. Build shadow-mode fixtures comparing legacy `{reply}` drafts to `{trinity}` outputs on shared thread snapshots.

## Anti-Patterns To Avoid

- Do not import `OpenMythos` into `{trinity}`.
- Do not merge model-architecture experimentation into workflow core.
- Do not let product prompts masquerade as learning policy.
- Do not mistake feedback score deltas for genuine learning.
- Do not replace deterministic contracts with opaque adaptive behavior.
