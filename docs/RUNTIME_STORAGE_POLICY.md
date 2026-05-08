# Runtime Storage Policy

## Purpose

This document defines where `{trinity}` runtime data is allowed to live and how adapter-scoped storage should be organized.

## Separation Rule

The repository working tree is for source-controlled development assets.

Machine-local runtime directories are for operational state.

These must not be mixed.

## In-Repository Development Assets

These belong in git:

- source code
- tests
- SSOT documentation
- build scripts
- deterministic fixtures
- synthetic sample datasets
- documentation examples

## Out-of-Repository Runtime Assets

These must not live in the repository by default:

- evidence databases
- candidate stores
- feedback memory
- frontier state
- accepted artifact state
- model configuration
- logs
- caches
- runtime traces
- exported bundles
- real tenant or operator data

## Default Local Layout

Base runtime roots:

- app support: `~/Library/Application Support/Trinity/`
- cache: `~/Library/Caches/Trinity/`
- logs: `~/Library/Logs/Trinity/`

Preferred adapter-scoped runtime layout for new installs:

```text
~/Library/Application Support/Trinity/
  trinity_runtime/
    adapters/
      <adapter>/
        companies/
          <company_id>/
            cycles/
            exports/
            training_bundles/
        cycles/
        exports/
        training_bundles/
        accepted_artifacts/
        accepted_reply_policies/
        model_config.json
```

Tenant rule:

- new runtime cycles, exports, and training bundles should be written beneath `companies/<company_id>/...`
- flat top-level `cycles/`, `exports/`, and `training_bundles/` paths remain readable only for compatibility with older local state

## Reply Compatibility Rule

The Reply adapter may continue using the legacy local root:

```text
~/Library/Application Support/Trinity/reply_runtime/
```

only when:

- that root already exists locally, and
- the new adapter-scoped Reply root does not yet exist

This compatibility fallback exists to avoid breaking existing local machines during migration. New code must not introduce fresh hard-coded `reply_runtime` assumptions outside that explicit compatibility path.

## Repository Rule

`/Users/Shared/Projects/trinity` is not a runtime data root.

It must not become the default home for live application state.

## Implementation Rule

Runtime code should:

1. resolve a machine-local base root
2. resolve an adapter-specific runtime root beneath it
3. store per-company traces, bundles, and runtime state beneath `companies/<company_id>/`
4. store accepted policies, accepted artifact registry state, and config under the adapter root
5. reject repository-local runtime roots by default

## Practical Decision Rule

If a file is needed to build, test, review, or change the software, it belongs in the repository.

If a file exists because the software is running for an operator or product integration, it belongs in runtime storage.
