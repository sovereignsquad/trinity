# Status

## Purpose

This document records the current implementation state of `{trinity}`.

## Current Phase

Current phase:

- reusable runtime core is established
- Reply adapter integration remains the only full downstream workflow, and Spot now exists as a bounded reasoning adapter slice
- generic adapter seam and generic CLI surface are now implemented
- provider-neutral model seam is now implemented for current local routing, with Ollama extracted behind `adapter.model.*`
- `mistral-cli` is now implemented as the second real local provider path through the same seam
- compatibility aliases remain in place for downstream Reply integration safety
- GitHub planning artifacts were refreshed against external leader-platform research, and the Trinity board now uses the same 8-state status taxonomy as org project `#3`
- the ideabank now has 25 structured feature issues seeded from current platform patterns across memory, orchestration, evaluation, browser ops, guardrails, and release governance
- a concrete third-app preparation plan now exists so the next downstream adapter can land through the current seam without another round of architecture cleanup
- local install documentation now explicitly covers required versus optional dependencies so a fresh checkout can install the runtime, CLI, and macOS shell without prior repository context

Primary active lane:

- restore `{trinity}` as the proper core system: active memory owner, disagreement-aware reasoning runtime, bounded loop controller, and HiTL escalation surface
- preserve the existing `{reply}` workflow as the quality anchor while extracting generic runtime behavior out of Reply-specific implementation
- define a clean reasoning contract for `{spot}` so it can consume `{trinity}` without inheriting Reply draft semantics
- keep `{train}` bounded as the offline optimizer and proposal system rather than the live runtime owner
- treat provider additions and external-ops seams as secondary to the core-system restoration lane until the missing runtime contracts are explicit

## Current Reality

The repository currently has:

- deterministic workflow core
- adapter helper layer
- provider-neutral model adapter layer under `core/trinity_core/adapters/model`
- generic `TrinityRuntime` facade
- adapter-scoped runtime storage for new installs
- legacy Reply storage fallback for migration safety
- generic CLI commands with `--adapter`
- compatibility `reply-*` aliases
- bounded Reply policy artifacts and acceptance workflow
- accepted-artifact promotion and rollback workflows
- training-bundle export
- shadow fixture replay
- company-scoped Reply behavior policy resolution
- tenant-aware runtime cycle, export, and training-bundle storage beneath the adapter runtime root
- atomic JSON writes for cycle, export, bundle, and accepted-artifact persistence
- Train API/CLI handoff client for autonomous bounded policy proposal generation
- concrete `{reply}` integration checklist for company identity, cycle tracking, outcomes, provenance, and Train triggering
- proposal review surface with holdout replay support, skeptical notes, and stronger scope rejection rules
- holdout-by-default policy review and acceptance flows, with explicit no-holdout override mode for local/dev use
- richer promotion review surface carrying acceptance mode and Train provenance in inspectable output
- training bundles now preserve surfaced and filtered negative candidates, stage evidence anchors, model routes, and policy-resolution summaries for hermetic offline learning
- policy resolution is now explainable through explicit resolution-path payloads instead of implicit scope fallback only
- policy review decisions can now be persisted as lineage-bearing review artifacts and linked from accepted artifact pointers
- focused design note documenting why the Train promotion seam now works
- deterministic coverage across workflow, policy, storage, and adapter behavior
- repo-resident live-brain runtime architecture spec in `docs/LIVE_BRAIN_RUNTIME_ARCHITECTURE.md`
- first-class runtime memory schemas for events, contacts, thread state, documents, retrieval chunks, and prepared drafts
- SQLite-backed Reply runtime memory store under `core/trinity_core/memory/storage.py`
- adapter-owned Reply payload mappers under `core/trinity_core/adapters/product/reply`
- provider-neutral `TrinityModelConfig` contract with concrete `deterministic` and `ollama` provider paths
- provider-neutral `TrinityModelConfig` contract now also carries explicit `mistral-cli` executable, arg, mode, and model-binding assumptions
- Reply runtime model execution now routes through `model_provider` instead of constructing Ollama directly
- concrete `mistral-cli` provider under `core/trinity_core/adapters/model/mistral_cli.py` for the initial `vibe` programmatic CLI path
- CLI/runtime-status now exposes `mistral-cli` config and can distinguish configured, unsupported, and offline/misconfigured provider states for that lane
- first bounded provider comparison harness under `core/trinity_core/ops/provider_comparison.py`, with machine-readable report artifacts and a generic `compare-providers` CLI command
- first bounded production-trace eval-dataset seam under `core/trinity_core/ops/eval_datasets.py`, with explicit curation from persisted traces and replayable dataset reports
- first bounded control-plane seam under `core/trinity_core/ops/control_plane.py`, with persisted job/run artifacts and explicit recurring benchmark/refresh execution paths
- first bounded Gobii recurring-workflow proof under `core/trinity_core/ops/gobii_workflows.py` and `core/trinity_core/ops/gobii_client.py`, with Gobii-ready workflow bundles and narrow agent registration support
- first bounded Gobii task lifecycle surface under `core/trinity_core/ops/gobii_tasks.py`, with create/list/result/cancel support and persisted task records
- Gobii agent and task clients now fail through explicit config/auth/timeout/invalid-response error paths instead of only coarse HTTP/URL exceptions
- first bounded Gobii normalization surface under `core/trinity_core/ops/gobii_normalization.py`, with explicit tenant-bound ingestion into runtime-owned document, retrieval, memory-event, and evidence artifacts
- first bounded Gobii sourcing/enrichment proof under `core/trinity_core/ops/gobii_enrichment.py`, with persisted tracked-entity enrichment bundles, required task `output_schema`, explicit task-record persistence, and normalization into Trinity-owned runtime artifacts
- runtime and CLI commands for memory-event ingestion, document registration, prepared-draft lookup, and prepared-draft refresh
- prepared-draft persistence on normal suggest cycles, explicit refresh overwrite rules, and bounded active-thread refresh planning plus control-plane job materialization for dirty/stale threads
- normalized runtime architecture and CLI docs so current implemented contract is clearly separated from target expansion
- first generic runtime memory retrieval service under `core/trinity_core/memory/retrieval.py`
- explicit hierarchical memory tiers for core, working, and archival runtime state, with deterministic tier placement and tier-attributed retrieval traces
- first shared runtime memory profile service under `core/trinity_core/memory/profile.py`
- retrieval records now carry deterministic relevance scores and selection reasons, and Reply/Spot can consume tier-aware memory summaries instead of only flat family hint lists
- runtime traces now also expose the top ranked memory records with score/reason metadata, and Reply/Spot now consume compact ranked-memory lines alongside the tier summaries
- first generic runtime consensus and loop scaffolding under `core/trinity_core/workflow/decision_loop.py`
- first generic runtime decision schemas for confidence bundles, minority reports, consensus, and loop decisions
- Reply runtime now records retrieved memory context and bounded loop/consensus artifacts in trace payloads without changing current surfaced draft behavior
- Reply and Spot runtimes now both shape retrieved memory into explicit preference, correction, anti-pattern, success, disagreement, and evidence hints for shared reasoning surfaces
- bounded live loop control is now implemented in code: Reply uses runtime confidence/minority signals to gate delivery eligibility and emit structured HiTL escalation payloads, while Spot performs one bounded rework pass before escalating
- Reply feedback now closes part of the memory loop: human outcomes persist explicit successful-pattern, correction, anti-pattern, disagreement, and human-resolution summaries, and bounded training bundles now carry loop/escalation labels for later `{train}` use
- generic runtime trace payload helpers under `core/trinity_core/ops/runtime_trace.py`
- upgraded issue bodies for legacy runtime-memory issues `#24` to `#28`, aligned to the same issue quality standard used in `sovereignsquad/train#17`
- new ideabank feature issue tranche `#40` to `#64`, covering research-driven future capabilities for tiered memory, durable execution, trace/eval governance, browser observability, adaptive guardrails, and environment-scoped workflow releases
- first bounded `{spot}` reasoning contracts under `core/trinity_core/schemas/spot_integration.py`
- first Spot payload adapter parsing under `core/trinity_core/adapters/product/spot`
- first minimal `{spot}` runtime slice under `core/trinity_core/adapters/product/spot/runtime.py`
- `TrinityRuntime(adapter_name="spot")` now supports bounded per-message Spot reasoning through `reason_spot()`
- Spot runtime policy is now explicit in code: high-confidence benign outcomes may auto-approve, positive or risky outcomes remain review-required, and deeper analysis plus human override stay available for every row
- Spot now has a bounded human-review ingestion path in Trinity: reviewer outcomes persist correction, successful-pattern, disagreement, and human-resolution memory summaries through the Spot runtime
- Spot now has a first bounded Train seam: Trinity can export `spot-review-policy-learning` bundles for offline consumption, but Spot proposal/eval breadth is still much narrower than Reply
- Spot now has a bounded policy adoption seam inside Trinity: Train can propose `spot_review_policy`, Trinity can review and accept it, accepted policy versions persist in a Spot policy store, and the Spot runtime now resolves that accepted threshold instead of using only the hardcoded default
- Spot policy isolation is now materially stronger: accepted Spot review policies resolve by `company -> global` instead of one adapter-global pointer, so parallel Spot tenants no longer need to share the same negative auto-approve threshold
- Spot runtime high-risk gating is now tighter: violent-threat phrasing can no longer fall through the benign auto-approve path just because it lacks the earlier narrower hostile-term anchors
- third-app onboarding preparation is now documented in `docs/THIRD_APP_PREPARATION_PLAN.md`, including adapter registration, CLI gating, memory participation, and optional policy/train seams
- local installation and dependency setup are now documented in `docs/LOCAL_INSTALL.md`, with explicit separation between required base tooling and optional provider or Gobii dependencies

## Verified Working

Verified locally in the current tranche:

- `uv run pytest`
- `uv run pytest tests/test_runtime_memory.py`
- `PYTHONPATH=core uv run python -m trinity_core.cli show-config --adapter reply --include-path`
- `PYTHONPATH=core uv run python -m trinity_core.cli runtime-status --adapter reply`
- `PYTHONPATH=core uv run python -m trinity_core.cli run-shadow-fixtures --adapter reply`
- `uv run pytest tests/test_model_config.py tests/test_adapter_runtime.py tests/test_integration_contracts.py`
- `uv run ruff check core/trinity_core/adapters/model core/trinity_core/cli.py core/trinity_core/model_config.py core/trinity_core/ollama_client.py core/trinity_core/reply_runtime.py core/trinity_core/runtime.py tests/test_adapter_runtime.py tests/test_model_config.py tests/test_integration_contracts.py`
- `uv run ruff check .`
- `uv run pytest tests/test_runtime_memory.py tests/test_integration_contracts.py`
- `uv run pytest tests/test_spot_contracts.py tests/test_runtime_memory.py tests/test_integration_contracts.py`
- `uv run pytest tests/test_adapter_runtime.py tests/test_spot_contracts.py tests/test_runtime_memory.py tests/test_integration_contracts.py tests/test_memory_profile.py`
- `uv run ruff check core/trinity_core/memory core/trinity_core/schemas core/trinity_core/workflow core/trinity_core/reply_runtime.py tests/test_runtime_memory.py tests/test_integration_contracts.py`
- `uv run pytest`
- `uv run ruff check .`
- `uv run pytest tests/test_model_config.py tests/test_mistral_cli_provider.py tests/test_adapter_runtime.py`
- `uv run pytest tests/test_provider_comparison.py`
- `uv run pytest tests/test_control_plane.py`
- `uv run pytest tests/test_gobii_client.py tests/test_gobii_workflows.py`
- `uv run pytest tests/test_gobii_tasks.py`
- `uv run pytest tests/test_gobii_client.py tests/test_gobii_tasks.py`
- `uv run pytest tests/test_gobii_tasks.py tests/test_gobii_normalization.py`
- `uv run pytest tests/test_adapter_runtime.py tests/test_spot_contracts.py tests/test_integration_contracts.py tests/test_runtime_memory.py tests/test_memory_profile.py tests/test_reply_policy_gate.py tests/test_reply_policy_store.py tests/test_reply_shadow_fixtures.py tests/test_spot_policy_gate.py tests/test_spot_policy_store.py tests/test_train_client.py`
- `uv run pytest`
- `uv run ruff check .`
- `uv run ruff check core/trinity_core/reply_runtime.py core/trinity_core/adapters/product/spot/runtime.py core/trinity_core/memory core/trinity_core/schemas/integration.py tests/test_adapter_runtime.py tests/test_spot_contracts.py tests/test_runtime_memory.py tests/test_integration_contracts.py tests/test_memory_profile.py`
- `uv run pytest`
- `uv run ruff check .`
- targeted Train proposal seam verified against sibling `/Users/Shared/Projects/train`
- policy review and acceptance gates verified with stricter company/channel/global scope rules
- bundle export now preserves negative samples and policy-resolution context for Replay training bundles
- production traces can now be promoted deliberately into replayable eval datasets instead of relying only on hand-built shadow fixtures

## Known Constraints

- only the Reply adapter currently has the provider comparison harness and shadow-fixture corpus lane
- the first eval-dataset replay lane is also Reply-only and still depends on explicit curation rather than broad automatic capture
- the Train handoff, shadow fixtures, and policy artifact lifecycle are intentionally scoped to the Reply workflow today
- Reply policy artifacts remain Reply-specific by design and have not yet been generalized into multiple artifact families
- policy resolution is now company-aware, but it is still not a full company-plus-channel matrix; channel scope remains the shared fallback below company scope
- API transport to `{train}` still assumes the Train server is already running; CLI transport avoids that dependency
- no-holdout acceptance remains possible only through explicit CLI override and should stay out of normal production promotion flows
- policy scope precedence is still company -> channel -> global only; thread-level or composite scope remains intentionally out of contract
- retrieval ranking is now explicit in both traces and prompt context, and tier-aware summaries now exist, but summarization is still lightweight and it is still not a full autonomous background brain
- sibling or historical docs may still mention older product-local suggest paths; current runtime SSOT is this repo's normalized runtime and CLI contract docs
- Reply still uses a conservative loop budget of zero text-changing rework passes; it gates low-confidence output to human review instead of silently rewriting reply content
- `{spot}` now has a bounded runtime slice, but it is still not a full product adapter: workbook ownership, taxonomy enforcement, and review workflow remain in `{spot}`
- Spot still lacks a first-class human-resolution ingestion path of its own; the current closed-loop memory learning is implemented only for Reply outcomes today
- Spot review policy is now explicit, but Spot reviewer outcomes still are not persisted back into Trinity memory through a first-class ingestion contract
- Spot reviewer outcomes now persist back into Trinity memory and Spot now has a first Train-side proposal/eval loop, but it is still limited to the review-policy slice only
- Spot review policy is now runtime-resolved from accepted artifacts with `company -> global` lookup, but richer Spot artifact families and composite scopes still do not exist
- `mistral-cli` currently targets the `vibe` programmatic CLI path only; route model names are preserved for config/trace provenance but remain advisory rather than CLI-enforced in this first tranche
- the first provider comparison harness is intentionally Reply-only and uses bounded shadow fixtures rather than broader live corpora
- the first control-plane seam is launch-and-inspect only; it does not yet include a resident scheduler, retry policy, or Gobii-backed orchestration substrate
- the first Gobii proof is intentionally narrow: only `reply_provider_comparison` jobs can be packaged for Gobii recurrence, and local equivalent trigger replay remains the repo-owned execution proof
- Gobii transport is now clearer about auth/config/timeout/invalid-response failures, but broader retry policy and richer backoff behavior still remain intentionally out of scope for the first bounded seam
- the first Gobii normalization slice is intentionally narrow: it requires explicit file-driven envelopes, completed bound task records, and persists only document-registration style artifacts rather than broad workflow mutations
- the first Gobii enrichment proof is intentionally narrow: it only supports tracked-entity profile enrichment against a known profile URL and persists only document-style runtime artifacts
- Reply remains the most mature downstream path and passes the focused runtime/policy/export validation suite, but shadow-fixture output quality is still governed by the existing deterministic/runtime constraints rather than parity with older product-local wording

## Immediate Priorities

1. continue extracting shared runtime behavior out of `ReplyRuntime` now that memory retrieval, tiering, and decision-loop scaffolding exist, while keeping current `{reply}` outputs stable
2. prepare the repository for a third downstream app by hardening adapter registration, clarifying generic CLI gating, and making the minimum third-adapter contract explicit
3. continue deepening active memory usage beyond traceability: retrieved memory now has explicit ranking metadata in traces and prompt context plus tier-aware summaries, so the next step is richer summarization quality and stronger downstream use of those summaries
4. deepen the now-live loop/minority/HiTL controls carefully: Reply should only gain text-changing rework with stronger regression coverage, while Spot can continue evolving bounded review routing and human-resolution ingestion
5. deepen the new Spot Train seam beyond the first review-policy slice without letting Trinity absorb workbook or taxonomy ownership
6. deepen Spot artifact families beyond `spot_review_policy` while preserving the new company-scoped isolation boundary
7. keep the Train proposal seam explicit and bounded; use the richer bundle labels and memory summaries for offline learning, but do not let it bypass runtime acceptance or become a live-learning shortcut
8. preserve explicit artifact promotion, rollback, provenance, and holdout review rules while the core runtime expands
