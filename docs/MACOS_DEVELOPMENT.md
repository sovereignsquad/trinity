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

