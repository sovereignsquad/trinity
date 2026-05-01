trinity
formal production definition

## 1. purpose

the Trinity is a three-stage candidate processing subsystem that transforms noisy evidence into a small, ranked set of decision-ready artifacts.

the Trinity exists to solve four problems simultaneously:

1. high evidence volume
2. noisy and overlapping signals
3. limited human attention
4. the need for continuous machine learning from feedback

the Trinity is not a user interface pattern.
the Trinity is not a prompt chaining gimmick.
the Trinity is not a human review queue.

the Trinity is a bounded transformation system.

---

## 2. primary design law

the system MUST complete its own production work before requesting human attention.

human feedback is supervisory, not structural.

therefore the correct order of operations is:

```text
Evidence
  -> Generator
  -> Refiner
  -> Evaluator
  -> Eligible Candidate Pool
  -> Frontier Selector
  -> User Feedback
  -> Reprocessing and Memory Update
```

this is the only form that scales.

if human intervention is required to move normal items through the middle of the pipeline, the pipeline is defective.

---

## 3. terminology

the following names are the canonical system names.

### 3.1 processing stages
- `Generator`
- `Refiner`
- `Evaluator`

### 3.2 core artifacts
- `EvidenceUnit`
- `KnowledgeItem`
- `ActionItem`
- `FeedbackEvent`

### 3.3 derived collections
- `GeneratedCandidateSet`
- `RefinedCandidateSet`
- `EvaluatedCandidateSet`
- `EligibleCandidatePool`
- `Frontier`

### 3.4 lifecycle language
- `GENERATED`
- `REFINED`
- `EVALUATED`
- `REWORK`
- `SUPPRESSED`
- `ARCHIVED`
- `DELIVERED` for action items only

product/UI language such as “flashcard” and “taskcard” MAY still exist, but MUST be treated as presentation-layer terminology, not core system terminology.

---

## 4. formal system definition

let:

- `E` be the set of evidence units
- `G(E)` be the generated candidate set
- `R(G)` be the refined candidate set
- `V(R)` be the evaluated candidate set
- `P(V)` be the eligible candidate pool
- `F(P)` be the surfaced frontier

then the Trinity is defined as:

```text
G: E -> GeneratedCandidateSet
R: GeneratedCandidateSet -> RefinedCandidateSet
V: RefinedCandidateSet -> EvaluatedCandidateSet
P: EvaluatedCandidateSet -> EligibleCandidatePool
F: EligibleCandidatePool -> Frontier
```

with the user-facing constraint:

```text
|Frontier| = min(3, number of currently eligible items)
```

if any valid candidate exists in the system, the frontier SHOULD NOT be empty.

---

## 5. system objective

the objective of the Trinity is not to generate prose.
the objective is to maintain a small, high-utility, continuously refreshed operational frontier from a much larger internal candidate inventory.

the Trinity succeeds when:

1. useful candidate recall is high
2. redundancy is low
3. surfaced-item precision is high
4. user overwhelm is low
5. feedback improves future system behavior
6. the frontier remains meaningfully populated

---

## 6. input and output contract

## 6.1 inputs

the Trinity accepts:

- raw evidence units
- evidence clusters
- business context
- policy constraints
- memory constraints
- prior evaluated items
- prior feedback events
- freshness and time signals

## 6.2 outputs

the Trinity emits:

- evaluated knowledge candidates
- evaluated action candidates
- suppression decisions
- merge decisions
- rework instructions
- ranking-ready scores
- memory-learning signals

the Trinity does not emit “final truth”.
it emits scored and dispositioned candidates under explicit policy.

---

## 7. evidence model

## 7.1 EvidenceUnit definition

an `EvidenceUnit` is the canonical raw input object.

required properties:
- `companyId`
- `evidenceId`
- `sourceType`
- `sourceRef`
- `contentRaw`
- `contentCanonical`
- `contentHash`
- `metadata`
- `topicHints[]`
- `createdAt`
- `updatedAt`
- `freshnessWindow`
- `provenance`

## 7.2 evidence requirements

every evidence unit MUST be:
- tenant-bound
- canonicalized
- deduplicated at exact-hash level
- timestamped
- traceable to origin

the evidence layer MUST support both:
- single evidence processing
- grouped evidence processing

because many useful candidates are inferable only from evidence sets, not from isolated evidence units.

---

## 8. stage 1: Generator

## 8.1 role

the Generator is the recall-maximizing stage.

its job is to transform evidence into plausible candidate artifacts with sufficient breadth and structured first-pass scoring.

the Generator is allowed to be prolific.
it is not allowed to be careless.

## 8.2 optimization target

the Generator MUST optimize:

```text
maximize useful candidate recall
subject to bounded redundancy
```

the Generator MUST prefer coverage over polish.

## 8.3 permitted synthesis cardinalities

the Generator MUST support all of the following:

- `1 evidence -> 1 candidate`
- `1 evidence -> many candidates`
- `many evidence -> 1 candidate`
- `many evidence -> many candidates`

if the system does not support these shapes, it will miss important business structure.

## 8.4 Generator input contract

the Generator receives:
- one or more evidence units
- strategic context
- active knowledge inventory
- active action inventory
- memory constraints
- business topic anchors
- freshness context

## 8.5 Generator output contract

the Generator emits a candidate set.
each generated candidate MUST include:

- `candidateId`
- `candidateType` = `KNOWLEDGE` or `ACTION`
- `title`
- `body` or `description`
- `sourceRefs[]`
- `state = GENERATED`
- `impact`
- `confidence`
- `ease`
- `iceScore`
- `semanticTags[]`
- `versionFamilyId`
- `duplicateClusterHint`
- `createdAt`
- `updatedAt`

## 8.6 Generator responsibilities

the Generator MUST:
- extract nontrivial insights
- preserve provenance
- avoid trivial restatements where possible
- propose structured metrics
- attach semantic tags
- avoid obvious duplication against active top-level inventory
- decompose overloaded evidence into distinct candidates

## 8.7 Generator failure conditions

the Generator is failing if it:
- misses obvious high-value opportunities
- floods the system with trivial restatements
- fabricates unsupported claims as if certain
- emits candidates too vague for downstream evaluation
- creates pathological duplicate density

---

## 9. stage 2: Refiner

## 9.1 role

the Refiner is the entropy-reducing stage.

its job is to transform a noisy candidate set into a smaller, cleaner, more evaluable set.

this is the structural compression stage.

## 9.2 optimization target

the Refiner MUST optimize:

```text
minimize candidate-set entropy
subject to preserving decision-useful information
```

## 9.3 Refiner input contract

the Refiner receives:
- generated candidate sets
- duplicate neighborhoods
- candidate lineage
- evidence lineage
- current inventory state
- feedback memory
- strategic context
- ranking context

## 9.4 Refiner output contract

the Refiner emits a refined candidate set.
each refined candidate MUST be:

- more precise than the source candidate
- less redundant than the source candidate
- easier to compare against peers
- easier to evaluate under policy
- explicitly lineage-preserving

state MUST become:
- `REFINED`

## 9.5 permitted operations

the Refiner MUST be able to perform:
- rewrite
- enrich
- normalize
- merge
- split
- suppress
- version
- reframe

a Refiner that only paraphrases text is not a serious system component.

## 9.6 merge and split requirements

### merge
when several candidates represent the same operational idea, the Refiner MUST merge them into a stronger candidate unless preserving variants is explicitly necessary.

### split
when one candidate bundles multiple distinct decisions, the Refiner MUST split it into smaller, evaluable candidates.

## 9.7 enrichment requirements

the Refiner MAY enrich a candidate by:
- adding contextual explanation
- clarifying implications
- grounding assertions against nearby evidence
- strengthening actionability
- improving business specificity

## 9.8 suppression requirements

the Refiner MUST suppress candidates that are clearly dominated by stronger siblings in the same semantic region.

suppression before evaluation is mandatory to prevent downstream ranking pollution.

## 9.9 Refiner failure conditions

the Refiner is failing if it:
- preserves duplicate noise
- over-compresses and destroys meaningful distinctions
- rewrites away provenance
- produces polished but semantically weak artifacts
- leaves candidates incomparable for evaluation

---

## 10. stage 3: Evaluator

## 10.1 role

the Evaluator is the precision-maximizing stage.

its job is to determine which refined candidates are eligible for surfacing, which require rework, and which should be suppressed or archived.

the Evaluator is not an authoring stage.

## 10.2 optimization target

the Evaluator MUST optimize:

```text
maximize surfaced-item precision
subject to maintaining non-empty operational supply
```

an Evaluator that is too lenient creates junk.
an Evaluator that is too strict creates emptiness.
both are system failures.

## 10.3 Evaluator input contract

the Evaluator receives:
- refined candidate sets
- evidence lineage
- duplicate cluster information
- freshness signals
- strategic policy
- feedback memory
- active inventory state
- relative ranking context

## 10.4 Evaluator output contract

for each refined candidate, the Evaluator MUST emit:

- `disposition`
- `impact`
- `confidence`
- `ease`
- `iceScore`
- `qualityScore`
- `urgencyScore`
- `freshnessScore`
- `feedbackScore`
- `state`
- `evaluationReason`
- `reworkRoute` if applicable
- `evaluatedAt`

## 10.5 valid dispositions

the canonical dispositions are:

- `ELIGIBLE`
- `REVISE`
- `REGENERATE`
- `MERGE`
- `SUPPRESS`
- `ARCHIVE`

the canonical evaluated states are:

- `EVALUATED` for surfacing-eligible items
- `REWORK` for machine-return items
- `SUPPRESSED`
- `ARCHIVED`

## 10.6 Evaluator responsibilities

the Evaluator MUST assess:

- usefulness
- novelty
- relevance
- timeliness
- actionability
- duplication risk
- support strength
- opportunity cost versus alternatives

evaluation MUST be partly relative to the candidate pool, not only absolute.

a candidate can be “good” in isolation and still be ineligible because stronger candidates already occupy its decision space.

## 10.7 Evaluator failure conditions

the Evaluator is failing if it:
- approves polished low-value artifacts
- rejects high-value rough artifacts too early
- ignores relative dominance
- scores without considering supply conditions
- creates frontier starvation

---

## 11. eligible candidate pool

the `EligibleCandidatePool` is the evaluated inventory from which surfaced items are selected.

the pool MUST contain:
- evaluated knowledge items
- evaluated action items
- fallback refined items where necessary
- fallback generated items where necessary

the pool MUST exclude:
- archived items
- permanently suppressed items
- obsolete dominated duplicates
- delivered action items
- rotten items beyond tolerance

the pool is an internal ranked inventory.
it is not the user interface.

---

## 12. frontier

## 12.1 definition

the `Frontier` is the user-facing top layer of the eligible candidate pool.

the Frontier is a dynamic ranked projection.

it is not a queue.
it is not a backlog.
it is not a permanent inbox.

## 12.2 cardinality

the Frontier MUST contain at most 3 items.

recommended rule:

```text
FrontierSize = min(3, count(eligible items))
```

if any meaningful candidate exists, the system SHOULD surface at least 1 item.

## 12.3 frontier eligibility tiers

the frontier selector MUST prefer candidates in this order:

1. `EVALUATED`
2. `REFINED`
3. `GENERATED`

this permits lower-quality candidate visibility without making it the default operating mode.

## 12.4 frontier ranking factors

the frontier selector MUST consider:

- state weight
- `iceScore`
- `qualityScore`
- `urgencyScore`
- `freshnessScore`
- `feedbackScore`
- strategic priority
- duplicate dominance
- rework status
- rotten risk

## 12.5 canonical frontier score

a recommended ranking formula is:

```text
frontierScore
=
stateWeight
* qualityWeight
* urgencyWeight
* freshnessWeight
* priorityWeight
* feedbackWeight
```

with:
- `stateWeight(EVALUATED) > stateWeight(REFINED) > stateWeight(GENERATED)`

the selector MAY use additive or multiplicative normalization, but it MUST be explicit and testable.

## 12.6 frontier re-ranking triggers

the Frontier MUST be recomputed when:
- new candidates arrive
- candidate scores change
- feedback arrives
- items age materially
- duplicates merge
- a rework completes
- a task is delivered
- freshness or urgency shifts

items MAY disappear from the Frontier without user interaction if stronger items emerge.
this is correct behavior.

---

## 13. knowledge items and action items

## 13.1 KnowledgeItem

a `KnowledgeItem` is an evaluated knowledge artifact derived from evidence.

required properties:
- `knowledgeItemId`
- `companyId`
- `title`
- `body`
- `sourceRefs[]`
- `state`
- `impact`
- `confidence`
- `ease`
- `iceScore`
- `qualityScore`
- `urgencyScore`
- `freshnessScore`
- `feedbackScore`
- `versionFamilyId`
- `duplicateClusterId`
- `createdAt`
- `updatedAt`
- `lastPresentedAt`
- `lastFeedbackAt`
- `lastReworkedAt`
- `rottenAt`

## 13.2 ActionItem

an `ActionItem` is an evaluated execution artifact derived from one or more knowledge items.

required properties:
- `actionItemId`
- `companyId`
- `title`
- `description`
- `sourceKnowledgeItemIds[]`
- `state`
- `impact`
- `confidence`
- `ease`
- `iceScore`
- `qualityScore`
- `urgencyScore`
- `freshnessScore`
- `feedbackScore`
- `versionFamilyId`
- `duplicateClusterId`
- `createdAt`
- `updatedAt`
- `lastPresentedAt`
- `lastFeedbackAt`
- `lastDeliveredAt`
- `lastReworkedAt`
- `rottenAt`

---

## 14. knowledge-to-action generation

the system MUST support the transformation of knowledge items into action items under all valid cardinalities:

- `1 knowledge -> 1 action`
- `1 knowledge -> many actions`
- `many knowledge -> 1 action`
- `many knowledge -> many actions`

this is mandatory for realistic business synthesis.

## 14.1 generation rule

action generation MUST occur only from sufficiently eligible knowledge states by policy.
the default recommended policy is:
- prefer `EVALUATED` knowledge items
- allow `REFINED` knowledge items when evaluated supply is insufficient

## 14.2 action generation objective

action generation MUST optimize:
- operational usefulness
- leverage
- non-duplication
- execution clarity
- timeliness

## 14.3 lifecycle symmetry

action items MUST move through the same Trinity lifecycle:

```text
GENERATED -> REFINED -> EVALUATED
```

this symmetry is required for operational consistency.

---

## 15. scoring model

## 15.1 canonical dimensions

all knowledge items and action items MUST carry the following scoring dimensions:

- `impact`
- `confidence`
- `ease`

these three define:

```text
iceScore = impact * confidence * ease
```

## 15.2 additional derived scores

the system MUST maintain at least:
- `qualityScore`
- `urgencyScore`
- `freshnessScore`
- `feedbackScore`

`iceScore` alone is not sufficient for frontier ranking.

## 15.3 interpretation

### impact
expected business leverage if correct and acted upon

### confidence
estimated reliability and usefulness under current evidence

### ease
estimated implementation or operational tractability

### qualityScore
overall quality after refinement and evaluation

### urgencyScore
time sensitivity and opportunity cost of delay

### freshnessScore
decay-adjusted current relevance

### feedbackScore
net supervisory signal accumulated from user behavior and downstream outcomes

---

## 16. time model and rot

time is a first-class feature, not metadata decoration.

## 16.1 required timestamps

all candidates MUST track:
- `createdAt`
- `updatedAt`
- `lastPresentedAt`
- `lastFeedbackAt`
- `lastReworkedAt`

action items additionally MUST track:
- `lastDeliveredAt`

## 16.2 rotten concept

an item is `rotten` when it is materially degraded by time, changed context, or closed opportunity.

causes include:
- stale market context
- expired timing window
- superseded evidence
- already-resolved opportunity
- delayed action beyond usefulness horizon

## 16.3 rotten policy

rotten items MUST be:
- downranked
- reworked
- or archived

they MUST NOT continue to compete equally for Frontier slots.

---

## 17. duplicate and dominance handling

duplicate management is a mandatory continuous system function.

## 17.1 duplicate classes

the system MUST recognize:
- exact evidence duplicate
- exact semantic duplicate
- near duplicate
- fragmented sibling
- superseded version
- cluster overlap

## 17.2 dominance principle

when two candidates occupy effectively the same decision space, the system MUST determine whether:
- one dominates the other
- they should be merged
- they should coexist as distinct variants

## 17.3 duplicate processing algorithm

1. detect exact duplicates by canonical hash where applicable
2. detect semantic neighbors by similarity search
3. form duplicate clusters
4. select cluster champion or merge target
5. suppress, merge, or archive weaker siblings
6. preserve provenance from all members

the Frontier MUST never be populated by duplicate siblings unless explicitly intended for comparison mode.

---

## 18. rework model

## 18.1 role of rework

`REWORK` is the machine return path for candidates that are not currently eligible but still potentially valuable.

rework is not a human review synonym.

## 18.2 rework routes

valid rework routes are:
- `REVISE`
- `REGENERATE`
- `MERGE`
- `ENRICH`
- `DOWNRANK_ONLY`

## 18.3 rework triggers

a candidate enters rework when:
- it is promising but too vague
- it lacks enough support
- it is over-fragmented
- it is under-specified for actionability
- it is dominated but mergeable
- it was declined with informative feedback

---

## 19. human supervision model

## 19.1 placement

human interaction MUST happen after machine processing by default.

the normal supervision order is:

1. machine generates
2. machine refines
3. machine evaluates
4. machine ranks and surfaces
5. human reacts

## 19.2 permitted lower-state interaction

the user MAY inspect and act on lower-state candidates when:
- the frontier lacks higher-state supply
- advanced inspection mode is enabled
- troubleshooting or policy tuning is required

this is an exception path, not the primary operating model.

## 19.3 human action types

the canonical `FeedbackEvent` types are:

- `ACCEPT`
- `DECLINE`
- `COMMENT`
- `MODIFY_ACCEPT`
- `DELIVER`
- `POSTPONE`
- `PIN_EVIDENCE`
- `SUPPRESS`
- `REWORK_REQUEST`

## 19.4 semantic interpretation

### ACCEPT
positive quality or usefulness signal

### DECLINE
negative quality, relevance, or readiness signal

### COMMENT
nonterminal directional supervision

### MODIFY_ACCEPT
strong positive signal plus corrective signal

### DELIVER
confirmed real-world execution of an action item

### POSTPONE
not wrong, but not currently actionable

### PIN_EVIDENCE
strong support signal for evidence grounding

### SUPPRESS
remove from normal surfacing

### REWORK_REQUEST
explicit request for a new machine pass

---

## 20. decline handling

decline MUST NOT imply blind deletion.

## 20.1 decline classification

the system SHOULD classify declines into:
- `WRONG`
- `DUPLICATE`
- `TOO_VAGUE`
- `LOW_PRIORITY`
- `BAD_TIMING`
- `NOT_ACTIONABLE`
- `MISSING_CONTEXT`
- `IRRELEVANT`
- `ALREADY_DONE`
- `IGNORANT_OUTPUT`

## 20.2 decline algorithm

1. store immutable decline event
2. classify reason
3. update candidate feedback state
4. update memory
5. decide:
   - archive permanently
   - send to rework
   - request enrichment
   - merge with sibling
   - downrank only

declined items of sufficient potential SHOULD be reprocessed, not discarded automatically.

---

## 21. delivery handling

`DELIVER` is the strongest positive signal for action items.

it means the action crossed from suggestion into real execution.

## 21.1 delivery consequences

on `DELIVER`, the system SHOULD:
- reward the action pattern
- reward the source knowledge lineage
- reward the transformation path that produced the action
- store comments as positive operational memory
- improve future action generation for similar clusters

the system MUST distinguish:
- “good idea”
from
- “executed in reality”

these are not equivalent.

---

## 22. feedback memory

## 22.1 role

feedback memory is the persistent supervisory learning layer.

it exists to ensure that feedback changes future system behavior.

feedback that does not affect future generation, refinement, evaluation, or ranking is wasted.

## 22.2 memory inputs

feedback memory MUST absorb:
- accepts
- declines
- comments
- modify-accept events
- deliveries
- postponements
- suppressions
- pinned evidence
- merge confirmations
- rework requests

## 22.3 memory scopes

memory MUST support at least:
- `GLOBAL`
- `TOPIC`
- `ITEM_FAMILY`
- optionally `PIPELINE_STAGE`

## 22.4 memory outputs

memory MUST produce:
- hard constraints
- soft preferences
- terminology corrections
- preferred action patterns
- anti-patterns
- duplicate suppression hints
- ranking hints

memory MUST be consumable by:
- Generator
- Refiner
- Evaluator
- Frontier selector

---

## 23. maintenance obligations

the system MUST continuously maintain itself.

maintenance is not optional cleanup.
it is part of correctness.

## 23.1 required maintenance jobs

the system MUST periodically:
- deduplicate evidence
- deduplicate candidates
- merge overlapping candidate families
- revisit oldest modified candidates
- revisit declined high-potential candidates
- revisit stale refined candidates
- re-evaluate aging evaluated candidates
- update memory from feedback
- recompute frontier ranking
- archive hopelessly rotten items

## 23.2 oldest modified candidate policy

the system MUST explicitly inspect the oldest modified candidates because they are high-value signals for:
- unresolved policy mismatch
- system blind spots
- incomplete rework
- outdated interpretations

recommended maintenance priority:
1. oldest modified high-value candidates not re-evaluated
2. oldest declined candidates with strong potential
3. oldest refined candidates still unevaluated
4. oldest generated candidates with high predicted leverage
5. evaluated candidates with negative downstream outcomes

---

## 24. failure conditions

the Trinity is considered operationally defective if any of the following persist:

- the Frontier is often empty while valid candidates exist
- duplicate siblings frequently occupy Frontier space
- user feedback does not change future behavior
- rework backlog grows without meaningful resolution
- evaluated supply is too low because Evaluator is over-strict
- low-quality items dominate because Evaluator is too weak
- Refiner only improves prose but not decision quality
- Generator misses obvious opportunity clusters
- action generation produces non-executable recommendations
- delivery signals are ignored by future ranking or generation

---

## 25. canonical end-to-end loop

the full system loop is:

```text
EvidenceUnit ingestion
  -> canonicalization and exact deduplication
  -> Generator
  -> GeneratedCandidateSet
  -> Refiner
  -> RefinedCandidateSet
  -> Evaluator
  -> EvaluatedCandidateSet
  -> EligibleCandidatePool
  -> Frontier Selector
  -> Frontier (Top 3)
  -> Human Feedback
  -> Memory Update
  -> Rework / Re-evaluation / Re-ranking
  -> Continuous regeneration
```

for knowledge-to-action transformation, the loop extends:

```text
EvidenceUnit
  -> KnowledgeItem generation
  -> KnowledgeItem refinement
  -> KnowledgeItem evaluation
  -> ActionItem generation from eligible KnowledgeItems
  -> ActionItem refinement
  -> ActionItem evaluation
  -> EligibleCandidatePool
  -> Frontier
  -> Feedback
  -> Memory and business learning
```

---

## 26. final operational statement

the Trinity is a three-stage candidate processing system designed to convert high-volume noisy evidence into a small, continuously refreshed, high-utility operational frontier.

its stages are:

1. **Generator**
   produces high-recall candidate sets from evidence

2. **Refiner**
   reduces candidate-set entropy through rewrite, merge, split, enrichment, normalization, and suppression

3. **Evaluator**
   maximizes surfaced-item precision through scoring, disposition, and eligibility control

the Trinity outputs an eligible candidate pool.
a separate frontier selector surfaces the top 3 current items.
human feedback is supervisory and feeds memory, rework, and business learning.
the system remains autonomous even when lower-quality candidates are optionally exposed.
