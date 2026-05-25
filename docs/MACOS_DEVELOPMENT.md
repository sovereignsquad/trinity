# macOS Development

## Purpose

This document defines the macOS-first development baseline for `{trinity}`.

## Current Shell

The repository includes a native SwiftUI operator shell under `apps/macos/`.

This shell exists to establish:

- a buildable native target
- a stable place for operator workflows
- an adapter-aware governance surface
- a machine-local settings and foundation-policy surface

## Build

```bash
cd apps/macos
swift build
```

Install prerequisites for the full local repository are documented in:

- [docs/LOCAL_INSTALL.md](/Users/Shared/Projects/trinity/docs/LOCAL_INSTALL.md)

## Current Expectations

- keep the app buildable with `swift build`
- keep workflow logic out of view code
- introduce state models before introducing complex UI flows
- keep filesystem-backed operator actions off the main actor
- preserve explicit `loading`, `missing`, and `failed` UI states for shell data sources
- derive visible adapter state from the shared adapter catalog rather than hardcoded per-product lists
- add bundle and packaging work only after the shell contract is stable
- keep runtime app data out of the repository working tree

Current reference files:

- [apps/macos/Sources/TrinityApp/TrinityApp.swift](/Users/Shared/Projects/trinity/apps/macos/Sources/TrinityApp/TrinityApp.swift)
- [apps/macos/Sources/TrinityApp/AdapterCatalog.swift](/Users/Shared/Projects/trinity/apps/macos/Sources/TrinityApp/AdapterCatalog.swift)
- [apps/macos/Sources/TrinityApp/GovernanceSurface.swift](/Users/Shared/Projects/trinity/apps/macos/Sources/TrinityApp/GovernanceSurface.swift)
- [apps/macos/Sources/TrinityApp/AdminSettingsSurface.swift](/Users/Shared/Projects/trinity/apps/macos/Sources/TrinityApp/AdminSettingsSurface.swift)
- [apps/macos/Sources/TrinityApp/ConstellationUI.swift](/Users/Shared/Projects/trinity/apps/macos/Sources/TrinityApp/ConstellationUI.swift)

## Runtime Data Locations

When `{trinity}` begins storing real local state on macOS, prefer:

- `~/Library/Application Support/Trinity/` for app data
- `~/Library/Caches/Trinity/` for caches
- `~/Library/Logs/Trinity/` for logs

Do not default live runtime data to the repository root.

See:

- `docs/RUNTIME_STORAGE_POLICY.md`
