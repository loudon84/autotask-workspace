# Callback Outbox

The callback outbox persists EVENT and FINISH callbacks to Task with at-least-once
delivery, stable idempotency keys, and per-attempt ordering.

The outbox lives in the `rpa_callback_outbox` table in [[data-model#Execution Tables]]
and is implemented in [[src/nodeskclaw_rpa_engine/workers/outbox.py]]. Artifact upload
and metadata callbacks remain direct; only pre-attempt rejections use a direct
best-effort callback.

## CallbackOutboxService

[[src/nodeskclaw_rpa_engine/workers/outbox.py#CallbackOutboxService]] enqueues EVENT
and FINISH messages inside the same database session that transitions the attempt.

FINISH uses the stable key `rpa:{attemptId}:finish`; RUN_STARTED uses
`rpa:lease:{leaseId}:run-started`. Enqueuing re-locks the attempt row for update so the
sequence is consistent with the attempt state.

## Idempotency and Ordering

Each outbox row has a per-attempt `sequence_no` and a unique `idempotency_key`.

The unique constraint on `idempotency_key` makes enqueue idempotent: re-enqueuing the
same key returns the existing row without creating a duplicate. Task must persist and
deduplicate by this key, and later also reject stale FINISH by `leaseId`.

## Dispatcher

[[src/nodeskclaw_rpa_engine/workers/outbox.py#CallbackOutboxDispatcher]] is the
background loop started by [[architecture#App Assembly]].

It recovers stale in-flight locks, claims ready rows with `SKIP LOCKED`, and delivers
them in `sequence_no` order per attempt — a row is not claimed while an earlier unsent
row for the same attempt exists.

## Retry and Dead Letters

A failed delivery transitions to `RETRY` with exponential backoff (capped at 300s) or
to `DEAD` once `attempts` reaches `max_attempts` (default 10).

Stale in-flight locks older than `stale_lock_seconds` are recovered to `RETRY` or
`DEAD` on each poll. The dispatcher drains remaining messages on shutdown.

## Direct Fallback

Only rejections that happen before an attempt row exists use a direct best-effort
`finish` callback through the Task client with a deterministic idempotency key.

Once an attempt exists, all EVENT and FINISH callbacks go through the outbox.
