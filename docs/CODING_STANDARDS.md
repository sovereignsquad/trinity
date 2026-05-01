# Coding Standards

## Purpose

This document defines the minimum coding standards for `{trinity}`.

## General Rules

- Prefer explicit contracts over hidden conventions.
- Keep functions narrow and auditable.
- Avoid provider-specific assumptions in core code.
- Keep local-only data out of git.
- Add tests for contract behavior, not only happy-path demos.

## Python

- Use type hints on public functions.
- Keep modules small and purpose-specific.
- Prefer plain data contracts and deterministic transforms.
- Do not bury business logic in scripts when it belongs in package code.

## Swift

- Keep view models thin and state transitions explicit.
- Prefer native SwiftUI patterns over ad hoc imperative UI glue.
- Keep the macOS shell as a workflow surface, not a second runtime engine.

## Documentation

- Update docs when architecture or workflow rules change.
- Write public-quality docs, not private shorthand.

