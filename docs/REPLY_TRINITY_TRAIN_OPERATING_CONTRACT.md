# Reply <-> Trinity <-> Train Operating Contract

## Goal

Prove one narrow, replayable integration spine without collapsing repository ownership:

1. `reply` captures one real thread as a `ThreadSnapshot`.
2. `trinity` owns runtime interpretation and returns a `RankedDraftSet`.
3. `reply` captures deterministic operator outcomes as `DraftOutcomeEvent`.
4. `trinity` persists the cycle and exports a `RuntimeTraceExport`.
5. `train` consumes exported traces and optimizes declared Trinity artifacts only.

## Ownership

- `reply`
  - product shell
  - channel ingestion and send execution
  - thread snapshot construction
  - operator action capture
- `trinity`
  - runtime contracts
  - evidence adaptation
  - candidate generation, refinement, evaluation, frontier selection
  - cycle persistence and trace export
- `train`
  - trace ingestion
  - replay fixtures
  - bounded artifact optimization scaffolding

## Canonical Contracts

- `ThreadSnapshot`
  - product-owned facts only
  - no runtime scores
- `RankedDraftSet`
  - Trinity-owned ranked output
  - max top 3 in this spine
- `DraftOutcomeEvent`
  - deterministic operator/product outcome
  - captures `cycle_id`, `candidate_id`, `final_text`, `edit_distance`, and `send_result`
- `RuntimeTraceExport`
  - replayable Trinity export for Train
- `AcceptedArtifactVersion`
  - explicit runtime artifact provenance

## Guardrails

1. `reply` must preserve its legacy draft path as fallback.
2. `trinity` must not read Reply SQLite stores directly.
3. `train` must not optimize Reply product orchestration.
4. exported traces must include artifact version provenance.
5. every cross-repo payload must carry `contract_version`.

## Initial Deliverable Issues

### Trinity

1. Define `ThreadSnapshot`, `RankedDraftSet`, `CandidateDraft`, `DraftOutcomeEvent`, `RuntimeTraceExport`, `AcceptedArtifactVersion`.
2. Add one local callable runtime entrypoint for `reply suggest`, `record outcome`, and `export trace`.
3. Persist runtime cycles outside the repo worktree.
4. Export replayable traces for Train.

### Reply

1. Build `ThreadSnapshot` from one real conversation path.
2. Add `TrinityClient` with feature flag fallback.
3. Route `/api/suggest` through Trinity when enabled.
4. Render top 3 ranked drafts and preserve candidate selection metadata.
5. Emit deterministic `DraftOutcomeEvent` records for show/select/send/reject/rework/ignore/manual replacement.

### Train

1. Add Trinity trace ingestion schema and loader.
2. Add `trinity_reply_ranker` project scaffold.
3. Keep optimization scaffold-only until enough real traces exist.

## Compatibility Rules

1. `reply` sends UTC ISO timestamps only.
2. `trinity` persists versioned payloads only.
3. `train` rejects trace files with the wrong contract version.
4. artifact promotion is copy-forward, never shared-write across repos.
