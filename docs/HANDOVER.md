# Handover

## Purpose

This document exists so work can be resumed cleanly by:

- the same developer later
- another developer
- another coding agent

## Current Handover

### What Changed Last

Last completed increment:

- initial repository bootstrap for `{trinity}`

Implemented:

- repository operating docs
- coding standards and definition of done
- design system baseline
- macOS development guide
- Python workspace scaffold
- minimal SwiftUI app scaffold

### What Was Verified

Verified:

- `uv run pytest`
- `uv run ruff check .`
- `swift build` in `apps/macos`

### What Needs To Happen Next

1. create the GitHub project board
2. add the initial detailed issue set
3. build the first workflow and memory contracts
4. replace placeholder verification with real command validation

### Watch Carefully

- do not collapse `{trinity}` into `{train}`
- keep workflow core separate from product adapters
- keep the first embedding `{reply}`-aware but not `{reply}`-shaped
- keep local-private data out of git
