# Worker Pool

The Worker Pool is the Engine's internal dispatch layer. It registers with Task,
heartbeats, optionally polls for leases, and drives Runtime attempts to a terminal
state before reporting FINISH.

The pool is implemented by [[src/nodeskclaw_rpa_engine/workers/pool.py#WorkerPool]] and
documented in `docs/PHASE3_WORKER.md`. It reuses the `rpa_worker_instances` and
`rpa_execution_attempts` tables in [[data-model#Execution Tables]] and never creates
them.

## Safe Defaults

`WORKER_ENABLED=false` disables all Task interaction. `WORKER_ENABLED=true` with
`WORKER_LEASE_ENABLED=false` enables only registration and heartbeat — the Phase 3
real smoke configuration.

`WORKER_LEASE_ENABLED=true` requires a Runtime `RunCommandHandler` and a
`RunCommandSource`, or construction fails. See [[configuration#Dependency Gating]].

## Lease Source

[[src/nodeskclaw_rpa_engine/workers/source.py#LeaseRunCommandSource]] adapts the Task
`lease`/`renew` HTTP API to the
[[src/nodeskclaw_rpa_engine/workers/source.py#RunCommandSource]] protocol.

The poll loop asks for `available_slots` leases and dispatches each. Renewal returns a
new `leaseExpiresAt`; the Engine never invents an expiry.

## Flow Version Resolver

[[src/nodeskclaw_rpa_engine/workers/resolver.py#FlowVersionResolver]] resolves
`rpaFlowId + rpaFlowVersion + tenantId` to the unique, exact, active, published
Registry version.

It rejects when the Flow or version is missing, not `ACTIVE`, not `PUBLISHED`, or has
incomplete package metadata. The Engine never substitutes the latest version.

## Attempt Lifecycle

A new lease is recorded as `dispatchMode=LEASE`, status `LEASED`, then transitions to
`RUNNING` and a terminal status on completion.

Duplicate `leaseId` never creates a second attempt. A new `leaseId` for the same `runId`
takes the next `attemptNo` under a PostgreSQL transaction advisory lock.

### Lease Renewal and Expiry

`_monitor_execution` waits on the Runtime task in slices bounded by the renew interval
and the remaining lease time.

If renewal fails, execution continues only until the known expiry, then cancels and
records `ABANDONED` with `LEASE_EXPIRED`.

### Recovery on Restart

`_recover_interrupted_attempts` runs at startup and transitions every `LEASED` or
`RUNNING` attempt for this `worker_id` to `ABANDONED`.

It enqueues a matching FAILED FINISH outbox entry in the same transaction. Therefore a
single `worker_id` must not run concurrent Engine instances.

## Capability Validation

`_validate_capabilities` requires `PLAYWRIGHT_CDP`, `BROWSER_SESSION_MANAGED`, and
every capability the Flow declares.

Missing capabilities reject the command with `WORKER_CAPABILITY_MISMATCH` before any
attempt is dispatched.

## Lease and Contract Validation

`_validate_lease` rejects non-`PLAYWRIGHT_CDP` engines, non-`MANAGED` sessions, and
already-expired leases.

`_validate_flow_contract` rejects engine-type mismatch and unsupported workflow codes.
These rejections use [[src/nodeskclaw_rpa_engine/workers/errors.py#RunCommandRejected]].

## Shutdown

`stop` records `DRAINING`, cancels heartbeat and poll loops, waits up to
`WORKER_SHUTDOWN_GRACE_SECONDS` for active slots, cancels stragglers, and records
`OFFLINE`.

Active Runtime children get a short cancellation window; if they ignore it, attempt
cleanup continues and the orphaned result is consumed in the background.

## Read-Only Worker API

The Engine exposes `GET /api/v1/workers` and `GET /api/v1/workers/{workerId}` via
[[src/nodeskclaw_rpa_engine/workers/service.py#WorkerQueryService]].

Stored `ONLINE`/`BUSY` workers whose heartbeat exceeds
`WORKER_OFFLINE_THRESHOLD_SECONDS` are reported as `OFFLINE`. Phase 3 provides no
drain/resume mutation endpoints.
