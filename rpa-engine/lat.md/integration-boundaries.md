# Integration Boundaries

The Engine integrates with `nodeskclaw-task` over a lease/renew/callback HTTP contract.

Real lease polling stays disabled until dedicated test data, an exact published
Registry version, scoped credentials, and the full callback path are approved end to
end. The Task Worker API client is
[[src/nodeskclaw_rpa_engine/workers/task_client.py#TaskWorkerApiClient]]. It preserves a
mixed transport contract: Worker request bodies use snake_case, `WorkerLeaseResponse`
uses camelCase, and Engine public API responses use camelCase.

## Ownership Boundary

The Engine owns Flow Registry metadata, Flow Packages, the technical execution attempt,
and the callback outbox.

`nodeskclaw-task` owns `Workflowbinding`, business tasks, runs, events, Artifact
metadata, and HumanAction. The Engine never writes to Task-owned tables; it only calls
Task HTTP endpoints and stores its own attempt/outbox rows.

## Lease Contract

A `WorkerLeaseResponse` carries the dispatch fields plus an immutable execution
snapshot (`rpaFlowId`, `rpaFlowVersion`, `tenantId`, `credentialRef`,
`config.portalUrl`, `config.browserSession`, `leaseExpiresAt`).

Missing version, expiry, or browser-session fields reject the contract. `renew`
returns a new `leaseExpiresAt`. See [[worker-pool#Lease Source]] and
[[worker-pool#Flow Version Resolver]].

## Artifact Contract

Artifact upload uses `POST /worker-api/artifacts/upload-url` with `worker_id`,
`task_id`, `run_id`, `name`, `mime_type`, followed by a signed PUT and a
`worker-api/runs/{runId}/artifacts` metadata callback.

A 2026-07-16 read-only OpenAPI check confirmed the route and request shape; it did not
upload an artifact. See [[runtime#Artifacts]].

## Callback Contract

EVENT and FINISH callbacks are persisted in the outbox and delivered at-least-once
with a stable `Idempotency-Key`.

Task must persist and deduplicate by that key, and later reject stale FINISH by
`leaseId`. See [[callback-outbox]].

## Current Limitations

These boundaries are not yet production-ready and gate the lease-poll rollout.

- `TASK_AUTH_MODE=none` and `X-Actor-Id`/`X-Tenant-Id` headers are test-environment
  context, not production authentication. Service-account auth remains required.
- Task dispatch uses an HTTP lease/renew compatibility source; production queue ack,
  visibility timeout, retry, and dead-letter behavior are future work.
- Flow Python modules run in the Engine process; static policy checks are not OS-level
  isolation.
- Whole-Flow retry may repeat external side effects; Phase 5 Flows must be idempotent.
  Step-level retry is future work.
- Lease polling stays off until a dedicated real end-to-end test passes and production
  service-account auth is complete.
