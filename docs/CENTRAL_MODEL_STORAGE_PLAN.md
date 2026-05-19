# Central Model Storage Plan

## Purpose

This document records the current `{trinity}` model-storage reality and the plan to centralize machine-local model assets under:

```text
/Users/Shared/Models
```

The goal is to centralize weight files, tokenizer assets, embedding assets, and related local AI binaries without violating the existing Trinity runtime-storage contract.

Current implementation status:

- Phase 2 is now partially implemented in code
- Phase 3 is now partially implemented in code
- Phase 4 is now partially implemented in code
- a first post-Phase-4 provenance step is now implemented in code
- Trinity now has a provider-neutral shared inventory loader under `core/trinity_core/adapters/model/inventory.py`
- this machine now also has an initial manifest at `/Users/Shared/Models/manifests/trinity-model-manifest.json`

## Current Audit

### Trinity Today

`{trinity}` currently stores model routing configuration, not model weights.

Current config roots on this machine:

- Reply config path resolves to `~/Library/Application Support/Trinity/reply_runtime/model_config.json`
- Spot config path resolves to `~/Library/Application Support/Trinity/trinity_runtime/adapters/spot/model_config.json`

Current runtime behavior:

- adapter model routing is configured in `core/trinity_core/model_config.py`
- adapter runtime storage roots are resolved in `core/trinity_core/ops/runtime_storage.py`
- the runtime supports `deterministic`, `ollama`, and `mistral-cli`
- no Trinity module currently resolves model files from `/Users/Shared/Models`
- no Trinity contract currently defines a central model-manifest or provider asset registry

Current live status on this machine:

- Reply and Spot are both configured with provider `deterministic`
- `llm_enabled` is currently `false` for both adapters
- the configured default route names still point at local-model names:
  - generator: `granite4:350m`
  - refiner: `mistral:latest`
  - evaluator: `qwen2.5:7b`

### Machine-Level Model Stores Observed

Observed shared model vault:

- `/Users/Shared/Models`

Observed provider-native store still in use:

- `~/.ollama`

Observed machine state:

- `/Users/Shared/Models` currently contains mixed assets:
  - `llms/`
  - `checkpoints/`
  - `vae/`
  - `loras/`
  - `adapters/`
  - `processors/`
  - `analysis/`
  - `controlnet/`
- `/Users/Shared/Models/llms/chat/` already contains locally downloaded chat models such as:
  - `granite-4.0-h-350m-4bit`
  - `qwen2.5-0.5b-instruct-4bit`
  - `gemma-3-270m-it-mlx-8bit`
  - `gemma-4-e2b-it-gguf-4bit`
- `~/.ollama` currently contains a separate provider-owned store and duplicates some Trinity route names such as:
  - `granite4:350m`
  - `mistral:latest`
  - `qwen2.5:7b`

## Decision Boundary

Centralizing model assets must not collapse two separate concerns:

1. model assets
2. Trinity runtime state

Keep these separate:

- `/Users/Shared/Models`
  This is the shared machine-local asset vault for weights, tokenizers, embeddings, and provider-side caches we intentionally centralize.

- `~/Library/Application Support/Trinity/...`
  This remains Trinity-owned runtime state for adapter config, traces, memory, bundles, accepted artifacts, and logs.

`/Users/Shared/Models` should not become the home for Trinity cycles, exports, memory state, or governance artifacts.

## Target Contract

### 1. One Shared Asset Root

Treat `/Users/Shared/Models` as the only approved machine-local root for durable model assets used by Trinity-adjacent local AI tooling.

### 2. Trinity Stores References, Not Weights

Trinity should continue to persist only:

- provider selection
- role routing
- provider connection info
- explicit model-asset references

Trinity should not copy model weights into its own runtime root.

### 3. Provider Adapters Resolve Through A Shared Inventory Layer

Add one new Trinity-owned seam under `adapter.model.*` for:

- model asset manifest loading
- provider-to-asset resolution
- path validation
- inventory reporting

This keeps provider path logic out of `workflow.*` and out of product adapters.

### 4. Provider Ownership Must Stay Explicit

There are two valid execution modes:

- provider-managed assets
  Example: Ollama keeps its own imported model store, but Trinity records where that provider sources or mirrors assets from.

- direct file-backed assets
  Example: MLX, GGUF, sentence-transformer, or local embedding runners load directly from `/Users/Shared/Models/...`

The contract must state which mode each provider uses.

## Proposed Layout Under `/Users/Shared/Models`

Use one normalized layout for LLM-relevant assets:

```text
/Users/Shared/Models/
  manifests/
    trinity-model-manifest.json
  llms/
    chat/
    instruct/
    encoders/
    rerankers/
    vision-language/
  providers/
    ollama/
    mlx/
    gguf/
    mistral-cli/
  caches/
    huggingface/
    xet/
  diffusion/
    checkpoints/
    vae/
    loras/
    controlnet/
    adapters/
    processors/
```

Notes:

- move non-LLM image-generation assets under `diffusion/` over time instead of leaving them at the root
- keep one `manifests/` area for Trinity-readable inventory files
- keep provider-specific import/export helpers under `providers/` only when those providers truly require distinct on-disk state

## Trinity Plan

### Phase 1. Document And Normalize

Goal:

- make the current storage split explicit without changing runtime behavior

Work:

- add this planning note
- keep current runtime storage policy unchanged
- define a Trinity-readable central manifest format for local model assets
- define stable model ids separate from provider-specific route names

Deliverable:

- a new contract doc for the model manifest and provider asset resolution seam

### Phase 2. Add A Central Inventory Seam

Goal:

- let Trinity understand `/Users/Shared/Models` directly

Work:

- add `core/trinity_core/adapters/model/inventory.py`
- load a manifest from `/Users/Shared/Models/manifests/trinity-model-manifest.json`
- expose normalized entries such as:
  - `model_id`
  - `family`
  - `capability`
  - `format`
  - `provider_modes`
  - `local_path`
  - `ollama_tag`
  - `embedding_dimensions`
  - `quantization`
- validate that referenced paths exist and stay outside the repo working tree

Deliverable:

- one provider-neutral inventory contract consumed only from `adapter.model.*`

Current status:

- implemented
- `runtime-status` now exposes one top-level `shared_model_inventory` block plus per-role inventory match fields
- the current seeded manifest is intentionally conservative and only maps assets we can name explicitly from the machine-local vault

### Phase 3. Extend Model Config To Reference Inventory Ids

Goal:

- stop treating raw provider route names as the only source of truth

Work:

- extend `TrinityModelConfig` so each role can carry:
  - `model_id`
  - `provider`
  - `route_name`
- preserve backward compatibility by deriving `model_id` from the current `model` field when needed

Deliverable:

- adapter config keeps working, but Trinity can now resolve roles through a central inventory

Current status:

- implemented for the config contract
- `TrinityRoleRoute` now carries optional `model_id`
- `load_model_config` now reads both nested persisted role payloads and older flat key lookups
- when `model_id` is missing, Trinity now derives it from the shared inventory when possible
- `write-config` can now persist explicit `--generator-model-id`, `--refiner-model-id`, and `--evaluator-model-id`

### Phase 4. Make Runtime Status Central-Inventory Aware

Goal:

- expose whether a configured route is backed by a known shared asset

Work:

- extend `runtime-status` with:
  - `inventory_enabled`
  - `inventory_model_id`
  - `inventory_path`
  - `inventory_format`
  - `inventory_status`
- distinguish:
  - configured but unknown to central inventory
  - known in inventory but missing on disk
  - known and present locally
  - provider-managed and externally imported

Deliverable:

- operators can see both route readiness and asset readiness

Current status:

- implemented for the runtime-status surface
- runtime-status now resolves inventory entries by `model_id` first and route name second
- each role now exposes `inventory_status`
- current status values are:
  - `unknown`
  - `present`
  - `missing`
  - `provider_managed`
  - `inventory_disabled`

## Next Landed Step

Shared model identity is now also preserved in persisted provenance artifacts:

- Reply runtime traces now carry `model_route_details`
- exported training bundles now carry `model_route_details`
- provider-comparison report artifacts now carry `route_details` and per-fixture `model_route_details`

This keeps the old route-string surface intact while giving later migrations one stable shared asset identity field to follow.

### Phase 5. Migrate Provider Stores Carefully

Goal:

- reduce duplicate model storage without breaking live local tooling

Work:

- decide provider by provider whether Trinity will:
  - import from `/Users/Shared/Models` into provider-native stores
  - symlink provider-native stores into `/Users/Shared/Models`
  - or accept provider-owned duplication temporarily
- for Ollama specifically, treat migration as an ops step, not a silent runtime assumption

Deliverable:

- documented migration playbooks instead of hidden path magic

### Phase 6. Add Central-Manifest Support For Post-Training Outputs

Goal:

- let later Trinity-trained artifacts land in the same shared vault

Work:

- define manifest entries for:
  - base model
  - adapter weights
  - merged weights
  - eval-only checkpoints
- keep promotion lineage in Trinity runtime storage while putting approved binary assets under `/Users/Shared/Models`

Deliverable:

- one place for local AI assets, one place for Trinity governance state

## Practical Recommendations

Recommended immediate choices:

1. keep Trinity runtime state in `~/Library/Application Support/Trinity/...`
2. treat `/Users/Shared/Models` as the shared asset vault only
3. do not point Trinity directly at raw folder heuristics under `/Users/Shared/Models` yet
4. add one explicit manifest before adding more providers
5. treat `~/.ollama` as an active duplicate store that needs an explicit migration decision later

## Risks To Avoid

- storing runtime state under `/Users/Shared/Models`
- teaching `workflow.*` about filesystem model paths
- hard-coding one provider's asset layout as the Trinity-wide contract
- assuming Ollama tags and local file-backed model ids are interchangeable
- silently moving or deleting `~/.ollama` assets without a migration step
- letting post-training outputs bypass Trinity acceptance and governance storage

## Recommended Next Implementation Step

The next smallest correct implementation step is:

- add a dedicated model-inventory contract and manifest loader under `core/trinity_core/adapters/model/`

That step keeps the active repository-contract lane intact:

- boundaries stay explicit
- runtime storage stays outside the repo
- provider logic stays under `adapter.model.*`
- `/Users/Shared/Models` becomes usable centrally without collapsing into ad hoc path guessing
