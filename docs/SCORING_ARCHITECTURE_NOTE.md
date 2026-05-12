# Scoring Architecture Note

## Purpose

This note captures a Trinity-native assessment of a proposed scoring-architecture upgrade pattern taken from adjacent work.

It exists to answer one question:

- which ideas are worth borrowing into `{trinity}` without importing another product's semantics

## Current Runtime Reality

Today `{trinity}` already has:

- candidate-level `impact`, `confidence`, and `ease`
- derived evaluator scores such as `quality_score`, `urgency_score`, `freshness_score`, and `feedback_score`
- frontier ranking that blends those derived scores with normalized ICE
- runtime memory retrieval with explicit scope, tier, family, relevance score, and selection reason
- outcome ingestion that writes company-scoped `successful_pattern`, `correction`, `anti_pattern`, `disagreement`, and human-resolution summaries back into runtime memory

Current limitations:

- the score contract does not expose factor-level sub-signals behind `impact`, `confidence`, or `ease`
- memory ranking is explicit, but it is still generic relevance ranking rather than score-specific reasoning
- human outcome learning is present, but mostly through coarse summary retrieval and one Reply-only `feedback_score` delta
- there is no first-class similarity-to-success, similarity-to-failure, or novelty signal in scoring
- `ease` is still generic and not yet modeled as true delivery difficulty

## What Is Worth Borrowing

These ideas fit Trinity's architecture and should be considered:

### 1. Factorized score profiles

Keep the public top-line scores, but add explicit sub-signals behind them.

Trinity-native direction:

- keep `impact`, `confidence`, and `ease` as the canonical headline dimensions
- add a structured `score_profile` or equivalent factor object instead of hiding calibration inside one opaque number
- keep factor calculation in runtime-owned workflow and memory layers, not in adapter-local prompt text only

### 2. History as first-class scoring input

This matches the current memory architecture direction.

Useful inputs:

- accepted outputs
- edited outputs
- rejected outputs
- delivered outputs
- disagreement resolutions
- human corrections

Important rule:

- those inputs should become explicit memory-derived scoring features, not silent model mutation

### 3. Similarity-to-history features

This is one of the highest-value missing pieces.

Useful feature families:

- similarity to previously successful patterns
- similarity to corrected patterns
- similarity to anti-patterns
- novelty relative to accepted company memory
- disagreement recurrence against past human resolutions

These should be computed against runtime-owned memory artifacts and candidate lineage, not product-local hidden stores.

### 4. Separate score proposal from score audit

The article is right that one-shot scoring is brittle.

A Trinity-native pattern would be:

1. stage execution proposes candidate scores and rationales
2. memory/history calibration adjusts or annotates those scores
3. a deterministic auditor flags unsupported clustering, contradictions, or missing justification
4. persisted traces keep both proposed and calibrated views

This fits the existing consensus, loop, trace, and Train-export direction.

## What Should Not Be Borrowed Directly

### 1. Product semantics inside `workflow.*`

The article speaks in terms such as:

- business impact for this company
- accepted flashcards
- delivered taskcards
- planning drag/drop behavior

That is useful conceptually, but `{trinity}` cannot hardcode one product's object model into the core workflow.

Trinity translation is required:

- generic candidate and outcome contracts in `workflow.*` and `schemas.*`
- product-specific mappings at `adapter.product.*`

### 2. Hidden prompt-only scoring logic

Requiring the model to justify scores is useful.

Relying on prompt text alone is not sufficient.

The score contract must remain inspectable and auditable in stored runtime artifacts.

### 3. Weakly defined "ease"

If this is upgraded, it should be renamed or explicitly documented as delivery difficulty semantics rather than staying a vague convenience score.

## Recommended Trinity-Native Implementation Order

### 1. Add explicit factor storage behind the current score contract

Example target shape:

- `impact_factors`
- `confidence_factors`
- `delivery_difficulty_factors`
- factor provenance and evidence anchors

This is the lowest-risk next step because it improves inspectability without forcing an immediate model rewrite.

### 2. Build memory-derived similarity features

Start from already persisted runtime memory families:

- `successful_pattern`
- `correction`
- `anti_pattern`
- `disagreement`
- `human_resolution`

Then add deterministic similarity helpers that produce bounded signals instead of free-form text only.

### 3. Rework `ease` semantics

Preferred direction:

- preserve the external field name short-term for compatibility
- define internal semantics as delivery difficulty
- later decide whether the public field should be renamed or aliased

### 4. Require per-dimension rationale in stage outputs or audit payloads

The rationale should be separate for:

- impact
- confidence
- ease or delivery difficulty

This should persist in traces so future Train or replay work can judge support quality.

### 5. Add score-health auditing

Useful first checks:

- repeated unsupported tuples
- strong score claims with weak evidence anchors
- high confidence despite contradiction-heavy memory
- high impact with low company-specific support

## Immediate Practical Takeaway

The article is directionally right.

The best ideas to borrow are:

- factorized scoring
- history-aware confidence and impact calibration
- similarity-to-success and similarity-to-failure features
- explicit score auditing

The main thing to avoid is importing another product's business objects or prompt habits directly into Trinity core.
