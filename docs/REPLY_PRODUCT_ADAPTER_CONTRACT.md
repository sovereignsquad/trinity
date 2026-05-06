# {reply} Product Adapter Contract

## Purpose

This document defines the Reply adapter boundary inside `{trinity}`.

The contract is owned by `{trinity}` because `{trinity}` owns:

- runtime vocabulary
- candidate semantics
- ranking semantics
- outcome semantics
- artifact provenance

`{reply}` may adapt product data into this contract, but it must not redefine the runtime concepts.

## Contract Version

Current adapter contract version:

- `trinity.reply.v1alpha1`

## Runtime Boundary

Reply owns:

- channels
- contact and conversation storage
- operator workflow
- transport behavior
- approval and send semantics

Trinity owns:

- normalized runtime request vocabulary
- ranked draft output vocabulary
- feedback and outcome semantics
- accepted-artifact provenance
- replayable runtime traces and bundles

## Payload Families

### Evidence Into Trinity

`ReplyEvidenceEnvelope` carries:

- `company_id`
- `conversation_ref`
- `channel`
- `sender_handle`
- `message_text`
- `occurred_at`
- optional `external_message_id`
- optional string metadata

### Thread Snapshot Into Trinity

`ThreadSnapshot` carries:

- `thread_ref`
- `channel`
- `contact_handle`
- `latest_inbound_text`
- ordered `messages`
- optional `context_snippets`
- optional `golden_examples`

### Ranked Drafts Out Of Trinity

`RankedDraftSet` and `ReplyDraftCandidate` carry:

- runtime cycle identity
- accepted artifact provenance
- ranked draft candidates
- rationale and source evidence ids
- delivery eligibility flags

### Outcomes Back Into Trinity

`ReplyFeedbackEvent` and `DraftOutcomeEvent` carry:

- candidate identity
- conversation or thread reference
- deterministic disposition
- occurred-at timestamp
- optional edited text or operator notes

## Compatibility Rules

- Reply remains the only implemented adapter today.
- The generic CLI path `--adapter reply` is preferred.
- Legacy `reply-*` CLI commands remain supported as compatibility aliases.
- Legacy local Reply storage may still resolve through `reply_runtime` when that root already exists on a machine.

## Non-Goals

This adapter contract does not move the following into `{trinity}`:

- send execution
- transport policy
- product-local merge semantics
- contact resolution rules
- UI approval logic
