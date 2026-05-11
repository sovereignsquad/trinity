# Provider Comparison Harness

## Purpose

This document defines the first bounded provider comparison lane for `{trinity}`.

The goal is to compare route sets without mutating live runtime behavior:

- replay one bounded corpus
- run multiple provider/model route sets
- measure quality fit, latency, and fallback behavior
- persist a machine-readable report artifact
- leave adoption decisions to later governance

## Current Scope

The first implemented comparison harness is intentionally narrow:

- adapter: `reply`
- corpus: Reply shadow fixtures
- route granularity: one route set containing `generator`, `refiner`, and `evaluator`
- artifact path: adapter runtime `provider_comparisons/reports/<report_id>.json`

This proves the measurement seam without claiming a generalized route-policy system yet.

## CLI

Primary command:

- `compare-providers --adapter reply`

Useful flags:

- `--fixture-dir <dir>`
- `--corpus-id <id>`
- `--route-set-file <path>`
- `--include-current-config`
- `--include-deterministic-baseline`

Default behavior when no route-set file is provided:

- compare the deterministic baseline
- compare the current active adapter config

## Route Set File Contract

A route-set file may contain either:

- one route set object
- or `{ "route_sets": [ ... ] }`

Each route set must provide:

- `route_set_id`
- `provider`
- `generator`
- `refiner`
- `evaluator`

Optional fields:

- `description`
- `ollama_base_url`
- `timeout_seconds`
- `mistral_cli_executable`
- `mistral_cli_args`
- `mistral_cli_mode`
- `mistral_cli_model_binding`

Role entries must provide:

- `provider`
- `model`
- `temperature`
- `keep_alive`

## Metrics

The report records:

- route identity per role
- corpus identity
- per-fixture latency
- per-fixture provider error, if any
- per-fixture fallback roles
- per-role attempted and failed provider calls
- aggregate success/failure counts
- aggregate fallback fixture count
- aggregate quality-fit score
- aggregate overlap and edit-distance summaries

## Quality-Fit Rule

For the first Reply comparison slice, quality fit is measured against:

- the legacy suggestion in the shadow fixture
- any golden examples embedded in the fixture thread snapshot

The current score is:

- similarity against each reference text
- where similarity is the average of:
  - token overlap ratio
  - `1 - normalized edit distance`
- the best reference match becomes the `quality_fit_score`

This is intentionally explicit and replayable. It is not a hidden model judge.

## Fallback Measurement

Fallback behavior is measured through tracked provider calls:

- attempted calls per role
- failed calls per role
- fixture-level fallback roles when a provider call failed and the runtime continued through bounded fallback behavior

This is why the harness lives in `ops.*` and wraps the provider seam rather than changing workflow code.

## Governance Boundary

Comparison reports do not:

- mutate live runtime configuration
- promote routes automatically
- change Train artifacts directly

They do:

- create evidence for later route-policy work
- give `{train}` and operators a bounded measurement artifact
- make provider changes inspectable before promotion decisions

## Current Limitation

The first harness is Reply-only and corpus-bound to shadow fixtures.

That is acceptable for this tranche because the goal is to prove:

- route-set replay
- machine-readable artifacts
- per-role fallback measurement
- provider/model provenance

before broadening into a larger route-policy system.
