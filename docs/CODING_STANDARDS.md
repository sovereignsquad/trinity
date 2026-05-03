# Coding Standards

## Purpose

This document defines the minimum coding standards for `{trinity}`.

## General Rules

- Prefer explicit contracts over hidden conventions.
- Keep functions narrow and auditable.
- Avoid provider-specific assumptions in core code.
- Keep local-only data out of git.
- Add tests for contract behavior, not only happy-path demos.
- Treat `{trinity}` as a native app product, not a website, when touching shipped operator surfaces.
- Keep all shipped visual assets local and reliably available offline.
- Prefer explicit visual rendering contracts over heuristic parsing of markup, icon, and asset values.

## Native App UI Rules

- Core operator actions belong in shell chrome, panels, and dialogs rather than page-style detours.
- Do not ship website-era fallback UX for native operator actions.
- Use one local icon system and one shared icon size contract across app-controlled surfaces.
- Do not use emoji or ad hoc glyphs as shipped product iconography.
- Verify readability in day mode, night mode, and system-follow mode for UI changes.
- For user-facing UI work, verify against the installed native app runtime, not only source previews.

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
