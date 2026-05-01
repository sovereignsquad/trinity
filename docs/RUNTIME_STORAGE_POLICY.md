# Runtime Storage Policy

## Purpose

This document defines where `{trinity}` runtime data is allowed to live.

The repository working tree is for development assets.

The machine-local runtime data root is for operational state.

These must not be mixed.

## Separation Rule

Keep these categories separate:

### In-repository development assets

These belong in the git repository:

- source code
- tests
- SSOT documentation
- build scripts
- sample fixtures and mock data intended for development
- deterministic test resources

### Out-of-repository runtime assets

These must not be stored in the git repository working tree by default:

- tenant evidence databases
- candidate stores
- feedback memory stores
- frontier state
- local operator state
- logs
- caches
- model downloads
- embeddings
- temporary exports
- runtime lock files
- cycle execution traces
- real private customer or tenant data

## Default macOS Locations

For local macOS operation, runtime data should live under user-scoped system directories rather than the repository.

Recommended locations:

- app support data:
  `~/Library/Application Support/Trinity/`
- caches:
  `~/Library/Caches/Trinity/`
- logs:
  `~/Library/Logs/Trinity/`

If the native app later gets a bundle identifier, the folder naming may become bundle-based, but the separation rule stays the same.

## Repository Rule

The repository root at `/Users/Shared/Projects/trinity` is not a runtime data root.

It may contain:

- source-controlled code
- docs
- tests
- local developer tooling metadata already ignored by git

It must not become the default home for live application state.

## Allowed Exceptions

These are acceptable in-repo only when clearly development-only:

- test fixtures
- synthetic sample datasets
- reproducible benchmark inputs
- documentation examples

These exceptions must never be confused with real runtime state.

## Implementation Guidance

When persistence work is implemented:

1. runtime code should resolve an explicit machine-local data root
2. the default macOS data root should point to `~/Library/Application Support/Trinity/`
3. logs and caches should resolve to their own macOS locations
4. the repository should remain free of live tenant data and operational state

The repository now includes a runtime storage resolver in code that enforces this boundary for default local path resolution.

## Git Rule

If a directory exists mainly to hold runtime state, it should be:

- outside the repository by default, and
- ignored by git if developers temporarily create it inside the repository during local experiments

## Practical Decision Rule

If the file is needed to build, test, review, or change the software, it probably belongs in the repository.

If the file is created because the software is running for a user or operator, it probably belongs in the runtime data root instead.
