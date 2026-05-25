# Design System

## Purpose

This document defines the baseline visual and interaction system for `{trinity}` operator surfaces.

## Product Direction

`{trinity}` is an operator-facing intelligence surface with adapter-aware runtime context.

The visual system should feel:

- focused
- calm under density
- editorial rather than decorative
- explicit about provenance and state

## Structural Principles

- surface evidence, candidate, and policy provenance clearly
- distinguish reusable runtime state from adapter-local state
- prefer native density over oversized web-style presentation
- keep artifact status, adapter identity, and model status inspectable without deep navigation

## Core UI Zones

1. evidence and timeline context
2. candidate comparison
3. frontier and accepted output
4. feedback and outcome capture
5. runtime status, adapter state, and policy provenance

## Visual Rules

- use typography hierarchy to separate evidence, candidate, and system metadata
- use color sparingly for state, confidence, and warnings
- keep the top-ranked actionable candidate visually primary
- never bury provenance and source context behind decorative interactions
- display adapter identity explicitly when one surface can operate on multiple adapters

## Interaction Rules

- runtime actions must be attributable
- policy and artifact state changes must be explicit
- adapter switches must not silently reuse incompatible context
- error states should tell the operator whether the failure is runtime-wide or adapter-specific

## Current Native Primitives

The current macOS shell implementation standardizes on the shared SwiftUI primitives in [apps/macos/Sources/TrinityApp/ConstellationUI.swift](/Users/Shared/Projects/trinity/apps/macos/Sources/TrinityApp/ConstellationUI.swift):

- `TrinityShell` for the app-wide shell background and tint contract
- `trinityPanel()` for standard operator cards and sections
- `TrinityStatusPill` for compact state badges
- `TrinitySectionHeader` for repeated title and subtitle treatment
- `TrinityInlineBanner` for visible warning and info states
- `TrinityEmptyState` and `TrinityLoadingState` for explicit load-state rendering
- `TrinityFormField` and `TrinityPathBadge` for repeated settings UI chrome

## Reliability Rules

- filesystem reads and writes for operator surfaces must not block the main actor
- load states must distinguish `loading`, `missing`, and `failed` instead of collapsing them into one neutral fallback
- adapter-aware surfaces should derive their visible adapter list from the shared runtime catalog rather than hardcoded per-product assumptions
