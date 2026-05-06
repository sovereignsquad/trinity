# Handover

## Purpose

This document captures the current resume point for `{trinity}`.

## Current Resume Point

Most recent meaningful tranche:

- `{trinity}` moved from an implicitly Reply-shaped runtime shell to an explicit adapter-aware runtime surface

Implemented in that tranche:

- generic adapter helpers in `core/trinity_core/adapters`
- generic `TrinityRuntime` facade in `core/trinity_core/runtime.py`
- generic CLI commands with `--adapter` in `core/trinity_core/cli.py`
- adapter-scoped runtime storage for new installs
- Reply compatibility aliases for CLI and legacy storage
- documentation rewrite for repository, adapter, and CLI contracts

## What Was Preserved

- `ReplyRuntime` remains the concrete implementation for the Reply adapter
- existing `reply-*` CLI commands still work
- existing Reply runtime state can still resolve through the legacy `reply_runtime` root when present
- existing Reply tests remain the primary contract coverage baseline

## What Was Verified

- `uv run pytest`
- generic CLI config path works for `--adapter reply`
- generic runtime rejects unsupported adapter names explicitly
- adapter runtime paths are namespaced for new installs and can fall back to legacy Reply roots when needed

## Practical Meaning

The repository is now safer to extend for other projects because:

- the generic runtime surface exists
- adapter naming is explicit
- storage layout is no longer hard-wired to Reply for new work
- the CLI contract is no longer product-specific by default

## Watch Carefully

- do not move product transport or approval semantics into core runtime modules
- do not expand generic schemas only because Reply currently uses a field
- do not remove Reply compatibility aliases until a second adapter is live and the generic CLI has proven stable
- do not reintroduce fresh hard-coded `reply_runtime` paths in new code
