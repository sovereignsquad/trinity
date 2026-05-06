# Coding Standards

## Purpose

This document defines the minimum engineering standards for `{trinity}`.

## General Rules

- Prefer explicit contracts over implicit conventions.
- Keep reusable workflow logic separate from adapter-specific mapping.
- Use deterministic transforms whenever a stage can be deterministic.
- Keep runtime storage outside the repository working tree.
- Add tests for boundary behavior, not only happy paths.
- Write comments only when they clarify intent, ownership, or invariants that are not obvious from the code itself.

## Adapter Rules

- Every product-specific assumption must live behind an adapter seam.
- Generic runtime modules must not encode `{reply}`-only naming, storage rules, or operator semantics.
- Backward-compatibility aliases are acceptable when they preserve a production integration contract during migration.
- New adapters must use the generic CLI before any adapter-specific convenience aliases are added.

## Python Rules

- Use type hints on public functions and dataclasses.
- Keep modules purpose-specific and auditable.
- Prefer dataclasses and small helpers over opaque mutable state.
- Do not hide core behavior in shell scripts when it belongs in package code.
- If a function exists only for one adapter, name that ownership explicitly.

## Storage and Policy Rules

- Storage paths must be adapter-scoped for new work.
- Accepted-artifact promotion and rollback must remain explicit and traceable.
- Policy application must be deterministic from stored state.
- Never use repository-relative default paths for runtime data.

## CLI Rules

- Generic commands are the primary public contract.
- Adapter selection must be explicit through `--adapter` unless a compatibility alias is intentionally used.
- CLI help text should describe operational intent, not implementation trivia.

## Documentation Rules

- Keep repository docs aligned with the actual runtime surface.
- Document migrations and compatibility behavior when storage or CLI contracts evolve.
- Write open-source-quality explanations that another engineer can follow without internal context.
