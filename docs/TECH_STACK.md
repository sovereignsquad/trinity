# Tech Stack

## Purpose

This document records the current technical direction for `{trinity}`.

## Current Stack

### Runtime And Tooling

- `Python 3.12+`
- `uv`
- `pytest`
- `ruff`

### Native App

- `Swift`
- `SwiftUI`
- `Swift Package Manager`

## Stack Rationale

### Python

Python is the right home for:

- workflow experimentation
- local data processing
- evaluation logic
- memory transforms
- deterministic test harnesses

### SwiftUI

SwiftUI is the right home for:

- macOS-first operator workflows
- local composer surfaces
- timeline review
- candidate inspection
- feedback capture

## Decision

`DECISION: {trinity} is macOS-first and local-first.`

That means:

- local execution is the primary path
- hosted infrastructure is optional later
- the native shell is part of the product, not an afterthought

