# macOS Development

## Purpose

This document defines the macOS-first development baseline for `{trinity}`.

## Current Shell

The repository includes a minimal SwiftUI shell under `apps/macos/`.

This shell exists to establish:

- a buildable native target
- a stable place for operator workflows
- a future home for timeline, candidate, and feedback surfaces

## Build

```bash
cd apps/macos
swift build
```

## Current Expectations

- keep the app buildable with `swift build`
- keep workflow logic out of view code
- introduce state models before introducing complex UI flows
- add bundle and packaging work only after the shell contract is stable
- keep runtime app data out of the repository working tree

## Runtime Data Locations

When `{trinity}` begins storing real local state on macOS, prefer:

- `~/Library/Application Support/Trinity/` for app data
- `~/Library/Caches/Trinity/` for caches
- `~/Library/Logs/Trinity/` for logs

Do not default live runtime data to the repository root.

See:

- `docs/RUNTIME_STORAGE_POLICY.md`
