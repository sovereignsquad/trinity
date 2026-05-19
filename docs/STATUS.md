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
- the CLI/runtime seam is now harder to integrate incorrectly: `runtime-status` carries explicit contract metadata plus readiness/capability fields, and CLI failures now emit structured JSON payloads instead of raw untyped exceptions
- GitHub planning artifacts were refreshed against external leader-platform research, and the Trinity board now uses the same 8-state status taxonomy as org project `#3`
- the ideabank now has 25 structured feature issues seeded from current platform patterns across memory, orchestration, evaluation, browser ops, guardrails, and release governance
- a concrete third-app preparation plan now exists so the next downstream adapter can land through the current seam without another round of architecture cleanup
- local install documentation now explicitly covers required versus optional dependencies so a fresh checkout can install the runtime, CLI, and macOS shell without prior repository context
- generic adapter registration and runtime dispatch are now descriptor-driven rather than hardcoded branch wiring, and the top-level docs now explicitly position new downstream apps as new adapters rather than Reply variants
- a Trinity-native scoring-architecture review note now exists at `docs/SCORING_ARCHITECTURE_NOTE.md`, capturing which factorized scoring, history-aware calibration, similarity-to-history, and score-audit ideas are worth borrowing without collapsing product semantics into core workflow
- the scoring review has now been translated into a concrete GitHub implementation lane: issue `#66` is the next contract-first tranche for factorized score profiles, issues `#67` to `#69` capture the near-term follow-ons for similarity, delivery-difficulty semantics, and per-dimension rationale, and issue `#70` holds the later score-audit pipeline work; related memory prerequisites `#42` and `#41` are now placed on the org board as part of the same planning chain
- the first bounded implementation slice of issue `#66` is now landed: `CandidateScores` can carry an optional nested score-profile contract with factor-level sub-signals and provenance, stage execution preserves that profile across generator/refiner/evaluator flows, and the existing trace/export serialization path can now persist the richer score payload without breaking current adapters
- the first bounded implementation slice of issue `#67` is now landed: Trinity can derive deterministic family-based similarity signals from retrieved runtime memory and merge them into candidate score profiles, and Reply now persists those similarity factors in evaluated candidate payloads before frontier ranking and trace export
- the first bounded implementation slices of issues `#68` and `#69` are now landed: the runtime now treats `ease` as a compatibility-preserving alias for delivery difficulty, stage outputs can provide explicit `delivery_difficulty` values without breaking existing `ease` payloads, and score profiles now preserve dimension-level rationale strings alongside factor-level evidence anchors
- the first bounded implementation slice of issue `#70` is now landed: Trinity can preserve proposed headline scores, apply deterministic audit flags and calibration notes, and persist calibrated score state before frontier ranking when repeated tuples, weak support, novelty, failure history, disagreement, or unsupported high claims trigger bounded penalties
- the next bounded `#70` extension is now landed too: persisted runtime traces now expose a top-level `runtime_score_audit` summary with per-candidate proposed-versus-final headline scores, audit flags, and calibration notes, so replay, export inspection, and later eval curation do not need to reconstruct score-governance state from nested candidate payloads alone
- the next bounded `#70` extension is now landed too: score audit now also applies deterministic rationale-quality penalties and bounded cross-run tuple-clustering checks, with Reply loading a recent company-local export window as explicit historical tuple input rather than hiding persistence access inside `workflow.*`
- the next bounded `#70` extension is now landed too: Trinity can now build explicit score-health report artifacts from persisted traces, aggregating runtime score-audit flags and recurring final-score tuples through a generic ops/CLI seam without changing live ranking behavior
- the next bounded `#70` extension is now landed too: score-health reports can now be reviewed through an operator-facing surface, and that review can optionally correlate aggregate score-governance patterns with one replay report to highlight likely quality risk
- Spot persisted reasoning candidates are now score-bearing too: the Spot contract now carries explicit `impact/confidence/ease` and frontier-input score fields per candidate, with persisted `ice_score` and computed priority semantics so Spot traces are no longer opaque to cross-app score inspection
- the next bounded governance step is now landed too: score-health reviews can now persist explicit decision artifacts, and multiple score-health reports can be compared into one trend report so governance work is no longer trapped at one-report-at-a-time inspection
- the next bounded workflow-integration step is now landed too: Trinity can evaluate one score-health report plus optional decision and trend artifacts into a deterministic governance gate, `policy-accept` and `train-propose-policy --accept` can now fail closed on blocked governance unless an explicit override note is supplied, and accepted artifact transitions now persist score-governance lineage and override provenance
- the next bounded release-and-triage step is now landed too: Trinity can persist explicit release-governance reports with release risk and operator recommendations, and it can build persisted triage queues from unresolved review decisions, risky trend reports, and accepted-artifact override history
- the next bounded closure step is now landed too: operators can now persist triage resolutions and release decisions as first-class artifacts, suppress resolved triage items from later queue rebuilds, and keep explicit lineage from a release decision back to its release-governance report
- release metadata and public documentation are now refreshed for repository version `0.1.4`, including install, overview, CLI, architectural, contributor-facing, and Reply hot-path prepared-draft contract docs
- a root `CHANGELOG.md` now exists for `0.1.4`, giving downstream integrators one concise release summary for the current prepared-draft contract plus the earlier scoring and governance tranche
- the Reply hot-path prepared-draft contract is now explicit in Trinity docs: on conversation open, Reply may force `get-prepared-draft`/refresh behavior and Trinity is expected to return a usable best-available draft even when no fresh prepared artifact existed beforehand
- the next workflow-integration tranche is now landed too: acceptance flows that use score-governance artifacts now also require a release-governance report and persist a linked release decision artifact during acceptance, so the release-governance loop is no longer optional in the governed path
- operator-facing governance surfaces are now materially stronger: `governance-status` joins latest review/release/triage/artifact lineage for one adapter, the macOS shell now has a native Governance page backed by persisted adapter artifacts, and `policy-status` plus `policy-review-surface` now surface the joined governance state directly
- cross-adapter score inspection is now explicit: `report-cross-adapter-scores` can compare Reply and Spot persisted traces in one machine-readable report with ICE, priority semantics, audit flags, and latest adapter governance state
- aggregate governance dashboards are now available too: `report-score-governance-dashboard` summarizes rising flags, recurring tuple clusters, unresolved triage work, and override churn across adapters
- downstream compatibility hardening now includes a dedicated public-contract test slice for Reply trace export and Spot persisted trace payloads, in addition to the existing integration suite
- a bounded post-training adoption plan now exists at `docs/POST_TRAINING_ADOPTION_PLAN.md`: Trinity will keep ownership of governed datasets, annotation, evaluation, and activation lineage; the active delivery lane stays backend-neutral on Apple Silicon, `Ollama` remains the likely first local serving target, and any later backend decision remains deferred until the prototype proves worth operationalizing
- GitHub planning artifacts for that lane now exist too: issue `#72` is the umbrella, issue `#73` is the next critical-path dataset-contract tranche, issues `#74` to `#76` cover annotation, local `Unsloth + QLoRA` prototyping, and evaluation, and issues `#77` to `#78` hold the later local-serving and durable-backend decision work on org project `#3`
- a Trinity-native self-learning research note now exists at `docs/SELF_LEARNING_LOCAL_AI_RESEARCH.md`: it maps `QLoRA`, `Unsloth`, `LLaMA-Factory`, `Axolotl`, and `Ollama` into a bounded daily offline learning loop where Trinity keeps ownership of dataset curation, operator-feedback weighting, holdout evaluation, promotion, and rollback rather than allowing live autonomous weight mutation
- the active post-training plan is now corrected for the actual hardware baseline too: Apple Silicon-only delivery may not treat `Unsloth`, `LLaMA-Factory`, or `Axolotl` as active implementation dependencies; the immediate lane is now backend-neutral until an Apple-Silicon-safe local fine-tune runner is chosen
- the first bounded implementation slice of issue `#73` is now landed: Trinity now has a generic `post_training` dataset contract plus a persisted `export-post-training-dataset` CLI seam that can build provenance-linked post-training datasets from existing Reply and Spot training bundles, preserving positive/corrected examples plus explicit negative examples where the source bundle supports them
- the next bounded `#73` extension is now landed too: post-training examples now preserve explicit annotation status, and Trinity can persist deterministic `train` / `validation` / `holdout` split artifacts through `build-post-training-split` while skipping explicitly excluded examples
- the next bounded post-training lifecycle step is now landed too: exported post-training datasets now start in `candidate` state, Trinity can persist explicit per-example curation decisions, operators can promote datasets into `curated` or `ready`, and split generation now refuses to run on unpromoted candidate datasets
- a model-storage audit and centralization plan now exists at `docs/CENTRAL_MODEL_STORAGE_PLAN.md`: Trinity today stores only model routing config under Application Support while `/Users/Shared/Models` and `~/.ollama` remain separate machine-local asset stores, and the next bounded implementation step is a provider-neutral model-inventory seam under `adapter.model.*` rather than moving runtime state into the shared model vault
- that next bounded implementation step is now landed too: Trinity now has a provider-neutral shared model inventory loader under `core/trinity_core/adapters/model/inventory.py`, `runtime-status` now exposes a `shared_model_inventory` block plus per-role inventory matches, and this machine now has an initial manifest seeded at `/Users/Shared/Models/manifests/trinity-model-manifest.json`
- the next bounded model-config step is now landed too: `TrinityRoleRoute` now carries optional stable `model_id`, config loading now supports both nested role payloads and older flat lookups, missing `model_id` values can now be derived from the shared inventory, and `write-config` can now persist explicit per-role model ids without breaking existing route-name behavior
- the next bounded runtime-status step is now landed too: inventory resolution now prefers explicit `model_id` over route-name fallback, and each role now exposes `inventory_status` so operators can distinguish unknown, present, missing, provider-managed, and inventory-disabled asset states without inferring them from path heuristics
- the next bounded provenance step is now landed too: Reply traces, Reply training bundles, and provider-comparison report artifacts now preserve shared-model identity through explicit `model_route_details` or `route_details` payloads instead of only route strings

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
- candidate scoring contracts now also support optional nested factor profiles for `impact`, `confidence`, and delivery-difficulty semantics, with JSON-round-trippable schema normalization from dataclass or persisted dict payloads
- Reply runtime candidate evaluation now also carries memory-derived `success`, `failure`, `correction`, `disagreement`, `human-resolution`, and `novelty` similarity signals in the score profile when retrieved memory supports them
- dimension-level score-profile rationale is now first-class for `impact`, `confidence`, and `delivery_difficulty`, and persisted traces can carry those rationales through the existing cycle/export serialization path
- calibrated candidate payloads can now preserve both proposed and final headline score tuples, along with audit flags and calibration notes, so trace exports can distinguish proposal state from calibrated runtime judgment
- persisted runtime traces now also carry a top-level score-audit summary with flagged-candidate counts, flagged candidate ids, and per-candidate proposed-versus-final score views for direct replay and governance inspection
- score calibration is now still deterministic but no longer purely cycle-local: Reply can pass a bounded recent company history of prior headline tuples into the generic audit pass, and high headline scores with thin rationale or missing evidence anchors now degrade explicitly instead of being treated as supported by factor presence alone
- persisted runtime traces can now also be promoted into aggregate score-health reports, so governance work can inspect recurring flags and score-tuple clustering across many traces instead of reading one trace at a time
- aggregate score-health reports no longer stop at raw counts: operators can now load one persisted report and optionally one replay report into a triage-ready review surface with top flags, recurring tuple clusters, recommendations, and coarse replay-quality risk
- cross-app score inspection is now less Reply-specific: Spot traces still do not use full generic `CandidateRecord` persistence, but their persisted candidates now expose the same headline and frontier-input score dimensions needed for ICE and priority-style ranking
- score-governance is now not only inspectable but stateful: operators can persist review outcomes for one report and compare recurring flags or tuple clusters across multiple reports without custom scripting
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
- CLI/runtime-status now also exposes explicit `contract_version`, `status_schema_version`, `generated_at`, `provider_inventory_supported`, and a normalized `readiness` block so downstream apps can distinguish runtime-alive, runtime-disabled, provider-unsupported, and role-capable states without reconstructing them from ad hoc fields
- CLI/runtime-status now also exposes shared model-vault metadata and per-role inventory matches, so downstream apps can distinguish route readiness from shared-asset availability under `/Users/Shared/Models`
- model config now also has a stable shared-asset seam: per-role routes can carry both provider route name and shared `model_id`, which keeps current provider execution unchanged while giving later runtime and post-training work one stable asset identifier
- runtime-status is now more explicitly asset-aware too: it resolves inventory by `model_id` first, then route name, and it emits one bounded `inventory_status` value per role instead of forcing adapters or operators to guess from missing paths
- persisted provenance is now more asset-aware too: route strings remain for backward compatibility, but trace, bundle, and provider-comparison artifacts now also carry explicit `model_id`-bearing route-detail payloads
- the CLI entrypoint now fails through machine-readable JSON error payloads with stable error metadata instead of raw traceback text, which makes adapter-side process supervision and compatibility handling safer across local Mac installs
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
- neutral new-app onboarding is now documented in `docs/INTEGRATING_NEW_APP.md`, and generic docs now describe `{reply}` as the first mature embedding rather than the default integration model

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
- `uv run pytest tests/test_post_training_datasets.py tests/test_integration_contracts.py -q`
- `uv run ruff check core/trinity_core/schemas/post_training.py core/trinity_core/ops/post_training_datasets.py core/trinity_core/schemas/__init__.py core/trinity_core/ops/__init__.py core/trinity_core/cli.py tests/test_post_training_datasets.py`
- `uv run pytest tests/test_model_config.py tests/test_mistral_cli_provider.py tests/test_adapter_runtime.py`
- `uv run pytest tests/test_model_inventory.py tests/test_model_config.py tests/test_adapter_runtime.py tests/test_public_contracts.py -q`
- `uv run ruff check core/trinity_core/adapters/model/inventory.py core/trinity_core/adapters/model/__init__.py core/trinity_core/cli.py tests/test_model_inventory.py tests/test_model_config.py tests/test_adapter_runtime.py tests/test_public_contracts.py`
- `uv run ruff check core/trinity_core/model_config.py core/trinity_core/cli.py tests/test_model_config.py tests/test_adapter_runtime.py`
- `uv run ruff check core/trinity_core/cli.py tests/test_adapter_runtime.py tests/test_public_contracts.py`
- `uv run pytest tests/test_public_contracts.py tests/test_integration_contracts.py tests/test_provider_comparison.py -q`
- `uv run ruff check core/trinity_core/schemas/integration.py core/trinity_core/reply_runtime.py core/trinity_core/ops/provider_comparison.py tests/test_public_contracts.py tests/test_integration_contracts.py tests/test_provider_comparison.py`
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
9. turn the scoring-architecture note into contract work by adding explicit factor-level score profiles, memory-derived similarity signals, and score-audit rules before attempting prompt-only score tuning
10. execute the scoring lane in issue order `#66 -> #67/#68/#69 -> #70`, keeping `#42` as the near-term memory metadata prerequisite and `#41` as the later memory-governance follow-on
11. use the newly landed `#66` contract seam as the base for `#67`, so similarity-to-history signals can land as explicit score-profile inputs rather than another prompt-only heuristic layer
12. use the now-landed `#67` similarity seam as the base for later calibration work, keeping the next critical-path focus on score semantics (`#68`) and per-dimension rationale (`#69`) before the audit pipeline (`#70`)
13. deepen `#68` and `#69` from their bounded contract slices into richer operational semantics and stronger adapter-owned rationale generation before starting the broader calibration/audit work in `#70`
14. deepen the new `#70` audit slice from its current rationale-quality, recent-history checks, aggregate reporting, persisted review decisions, and first trend reporting into richer operator-facing governance workflows, but keep proposed-vs-calibrated state explicit and bounded
15. build on the new acceptance-gate integration by adding release-facing governance checks and operator triage queues, rather than adding more raw scoring heuristics
16. start the bounded post-training adoption lane at issue `#73` by adding a Trinity-owned post-training dataset contract before attempting annotation workflows, local fine-tuning prototypes, or trained-adapter serving
17. keep the post-training lane governed as an offline daily learning loop: automate dataset curation, split building, local fine-tune proposals, training, and evaluation, but keep promotion and rollback behind explicit Trinity acceptance and operator review
18. keep the active post-training delivery lane Apple-Silicon-safe: do not make `Unsloth`, `LLaMA-Factory`, or `Axolotl` primary implementation dependencies unless their official support story matches the actual machine baseline
