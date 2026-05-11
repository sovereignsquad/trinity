# Tech Stack

## Purpose

This document records the current technical direction for `{trinity}`.

## Current Stack

### Runtime And Tooling

- `Python 3.12+`
- `uv`
- `pytest`
- `ruff`
- `git`

### Native App

- `Swift 6.1`
- `SwiftUI`
- `Swift Package Manager`
- `macOS 15` target for the current shell package

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

## Install Notes

- the base runtime install path is documented in [docs/LOCAL_INSTALL.md](/Users/Shared/Projects/trinity/docs/LOCAL_INSTALL.md)
- `ollama` and `mistral-cli` are optional provider dependencies, not required for a fresh deterministic install
- Gobii credentials and connectivity are optional and only required for the bounded external browser-agent seams
