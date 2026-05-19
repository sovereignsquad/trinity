# Self-Learning Local AI Research

## Purpose

This document explains how `{trinity}` should use `QLoRA`, `Unsloth`, `LLaMA-Factory`, `Axolotl`, and `Ollama` to build a strong local learning system that improves over time without breaking the current operator-feedback and governance model.

This is a research and operating note, not an instruction to let runtime mutate itself live.

## Executive Conclusion

Recommended near-term stack:

- `{trinity}` owns dataset creation, annotation, provenance, evaluation, acceptance, and rollback
- active delivery stays backend-neutral until an Apple-Silicon-safe local training runner is chosen
- `QLoRA` remains a candidate method, not an active backend commitment
- `Ollama` is the first local serving target for approved trained adapters
- `LLaMA-Factory` and `Axolotl` are not part of the active delivery lane
- `Unsloth` is not a primary path for now on Apple Silicon-only machines

The safe design is not "self-learning" in the sense of live online weight mutation.

The safe design is:

1. runtime captures outcomes and operator feedback
2. Trinity curates teachable examples explicitly
3. local training runs produce candidate adapters offline
4. Trinity evaluates them against holdouts and governance checks
5. only approved adapters get activated locally

That gives day-by-day improvement without losing control.

## Official Source Highlights

### `QLoRA`

The QLoRA paper shows that 4-bit quantized fine-tuning makes larger models practical on constrained hardware and reports strong results from relatively small, high-quality instruction data.

Relevant source:

- [QLoRA paper](https://arxiv.org/abs/2305.14314)

### `Unsloth`

Unsloth's official docs position it as a local fine-tuning framework with low VRAM requirements, local installation, Docker support, and a recommendation to start with QLoRA before heavier methods. But its official requirements page still says `Apple/Silicon/MLX is in the works`, so it should not be treated as an active delivery dependency for Apple Silicon-only machines.

Relevant sources:

- [Unsloth fine-tuning guide](https://unsloth.ai/docs/get-started/fine-tuning-llms-guide)
- [Unsloth Docker install](https://unsloth.ai/docs/get-started/install/docker)

### `LLaMA-Factory`

LLaMA-Factory is broader than Unsloth. It includes training, evaluation, export, and WebUI surfaces, and its docs explicitly support using Unsloth acceleration via configuration. But its installation docs are centered on CUDA/Linux and Windows, so it should not be part of the active Apple Silicon delivery lane.

Relevant sources:

- [LLaMA-Factory acceleration docs](https://llamafactory.readthedocs.io/en/latest/advanced/acceleration.html)
- [LLaMA-Factory WebUI](https://llamafactory.readthedocs.io/en/latest/getting_started/webui.html)
- [LLaMA-Factory eval docs](https://llamafactory.readthedocs.io/en/latest/getting_started/eval.html)

### `Axolotl`

Axolotl is broader and more infrastructure-shaped than Unsloth. It supports LoRA, QLoRA, preference tuning, evaluation, and more durable YAML-driven pipelines. But its requirements are still written around NVIDIA or AMD GPU training, so it should not be part of the active Apple Silicon delivery lane.

Relevant sources:

- [Axolotl overview](https://docs.axolotl.ai/)
- [Axolotl FSDP + QLoRA](https://docs.axolotl.ai/docs/fsdp_qlora.html)
- [Axolotl LoRA optimizations](https://docs.axolotl.ai/docs/lora_optims.html)
- [Axolotl Unsloth integration](https://docs.axolotl.ai/docs/unsloth.html)

### `Ollama`

Ollama is the serving and import layer, not the main training system. Its official docs support loading `(Q)LoRA` adapters through `Modelfile` `ADAPTER` instructions and importing fine-tuned adapters created by frameworks including Unsloth.

Relevant sources:

- [Ollama Modelfile reference](https://docs.ollama.com/modelfile)
- [Ollama importing models and adapters](https://www.mintlify.com/ollama/ollama/advanced/import)

## What Each Part Should Do In Trinity

### Part 1: `{trinity}` dataset and annotation ownership

This must stay inside Trinity.

Why:

- Trinity already owns accepted artifacts, traces, eval datasets, score governance, release governance, and operator lineage
- external training frameworks are not the right source of truth for approval semantics
- operator feedback is the strongest signal in the current system and must remain first-class

Trinity should own these example families:

- positive delivered examples
- accepted-but-edited examples
- rejected or declined examples
- corrected examples
- abstain / escalate examples
- policy-sensitive negative examples

Each example should carry:

- adapter name
- company id
- source trace id
- source candidate id
- operator outcome
- correction lineage
- policy-resolution context
- score-governance context where relevant

### Part 2: `QLoRA` as the first method

Use `QLoRA` first because it is the lowest-risk way to make local fine-tuning cheap enough to run repeatedly.

In Trinity terms, `QLoRA` should be the default for:

- first personalization runs
- first company-specific adaptation runs
- first daily or nightly refresh experiments

It should not be treated as a free pass to train everything all the time. The trigger should still be governed by:

- enough new reviewed examples
- enough holdout coverage
- a minimum signal threshold from operator feedback

### Part 3: Apple-Silicon-safe local fine-tune runner

Do not treat `Unsloth` as the first active backend on this machine class.

The active question is:

"Which Apple-Silicon-safe local runner can consume Trinity-owned approved examples without weakening governance?"

Trinity should use a backend-neutral local runner seam like this:

- generate a bounded dataset artifact
- shape it into the conversational or instruction format required by the target model
- launch the local fine-tune run through an explicit Trinity ops contract
- persist training config, base model id, output adapter path, dataset id, and run metadata

Do not let the local runner own:

- annotation truth
- promotion decisions
- activation policy
- runtime memory

### Part 4: `LLaMA-Factory` as deferred research only

Use `LLaMA-Factory` if the team wants a broader training platform later.

It becomes attractive when you need:

- more operator-friendly configuration
- training plus evaluation plus export in one tool
- WebUI-backed experiment management
- easier movement beyond the first narrow prototype

It is a better fit for "many experiments and more operators" than for the first proof.

### Part 5: `Axolotl` as deferred research only

Use `Axolotl` if the lane becomes more infrastructure-heavy.

It becomes attractive when you need:

- strong YAML-driven reproducibility
- multi-GPU or larger-scale runs
- more durable training pipeline control
- broader post-training methods beyond simple SFT/QLoRA

It is a better fit for "serious training infrastructure" than for the first local proof.

### Part 6: `Ollama` as the serving seam

Use `Ollama` after evaluation, not before.

Trinity should use it like this:

- import the approved adapter against the exact matching base model
- register the imported local model as a new controlled serving candidate
- activate it only after evaluation and operator approval
- keep rollback to the prior model or adapter explicit

`Ollama` should be the last step in the learning loop, not the first.

## Recommended Daily Learning Loop

This is the recommended automatic local loop for day-by-day improvement.

### Stage A: Capture

During normal runtime:

- store traces
- store candidate rankings
- store operator approvals and rejections
- store edited final outputs
- store policy decisions
- store triage and governance outcomes

This part already aligns with Trinity's current direction.

### Stage B: Curate

On a scheduled local control-plane job:

1. scan new accepted and resolved artifacts since the last curation run
2. extract teachable examples
3. classify them into positive, corrected, negative, and abstain buckets
4. exclude weak or ambiguous samples
5. persist a post-training dataset candidate artifact

Important:

- curation should be deterministic
- exclusion reasons should be persisted
- operator edits should be treated as stronger than raw accept signals

### Stage C: Holdout and split

Before any training run:

- keep a fixed holdout set per adapter and company segment
- keep a recent-delta validation set
- keep the newest examples out of the training split when needed for drift checks

Without this, the system will only learn to imitate the last few operator actions and you will not know whether it actually improved.

### Stage D: Train

Nightly or on threshold:

- use the Apple-Silicon-safe local runner once chosen
- treat `QLoRA` as a candidate method where the chosen runner supports it safely
- train only when enough new curated examples exist
- keep model families small enough for local iteration

Persist at minimum:

- dataset artifact id
- holdout artifact id
- base model id
- training backend
- hyperparameters
- output adapter path
- run start/end times
- run status

### Stage E: Evaluate

After training:

- run holdout replay
- compare baseline versus candidate adapter
- compare policy-sensitive behavior
- compare abstain / escalation behavior
- compare operator-alignment metrics

The first useful metrics should be Trinity-native, not benchmark vanity metrics:

- operator-accept rate on replay
- correction-rate reduction
- abstain correctness
- policy regression count
- score-governance regression count

### Stage F: Promote or reject

If the candidate adapter passes:

- create a promotion recommendation artifact
- require operator review or explicit acceptance policy
- import into `Ollama`
- activate as a reversible local serving target

If it fails:

- persist the failed evaluation
- keep the dataset and run metadata for future analysis
- do not activate it

### Stage G: Observe

After activation:

- keep logging operator outcomes against the active adapter version
- track whether improvement is real or only apparent in offline eval
- demote or roll back if policy or quality regressions appear

## How To Keep Operator Feedback Strong

The system should treat operator feedback as the main teaching signal, not an optional tag.

Recommended weighting:

- strongest: delivered after operator edit or explicit correction
- very strong: delivered without edit
- medium: accepted for review but not delivered
- negative: declined, rejected, policy-blocked, or escalated
- special negative: confident-but-wrong outputs

The system should learn at least four behaviors from operator feedback:

1. what to say
2. what not to say
3. when to abstain
4. how much confidence is appropriate

That means the dataset contract should not only capture final target text. It should also capture:

- preferred style
- disallowed framing
- correction reason
- escalation reason
- policy context

## What Should Be Automated

Safe to automate:

- daily dataset-candidate generation
- dataset split generation
- threshold-based training-run proposal
- local training execution through the chosen Apple-Silicon-safe runner
- replay and holdout evaluation
- candidate adapter registration
- recommendation artifact creation

Should remain gated:

- promotion into active serving
- rollback suppression after regressions
- policy-sensitive dataset inclusion rules
- exceptions to governance gates

## Best Initial Stack

For the next real Trinity implementation tranche, the best stack is:

1. Trinity-owned post-training dataset contract
2. Trinity-owned curation and annotation workflow
3. Apple-Silicon-safe local prototype lane
4. Trinity-native replay and holdout evaluation
5. `Ollama` import and reversible activation

Only after that:

- revisit whether any broader backend research is even necessary

## Recommended Implementation Shape

The control-plane shape should look like this:

1. `curate-post-training-dataset`
2. `build-post-training-splits`
3. `propose-local-finetune-run`
4. `run-local-finetune`
5. `evaluate-local-adapter`
6. `propose-adapter-promotion`
7. `import-local-adapter`
8. `activate-local-adapter`
9. `rollback-local-adapter`

These should all persist explicit artifacts under Trinity ops storage.

## Blunt Recommendation

If the goal is a local AI system that gets better day by day:

- do not build live autonomous self-retraining first
- build a daily governed offline learning loop
- keep operator feedback as the strongest teacher
- start with the dataset and evaluation lane first, then choose the Apple-Silicon-safe runner
- use `Ollama` only as the approved serving seam
- keep `Unsloth`, `LLaMA-Factory`, and `Axolotl` out of the active delivery lane on the current hardware baseline
