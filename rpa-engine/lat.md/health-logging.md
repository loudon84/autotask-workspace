# Health and Logging

The Engine exposes liveness and readiness endpoints and emits structured JSON logs
with secret redaction.

Health is implemented by [[src/nodeskclaw_rpa_engine/core/health.py]] and logging by
[[src/nodeskclaw_rpa_engine/core/logging.py]].

## Liveness

`GET /health/live` returns service, version, and environment without checking any
dependency. It is always available.

## Readiness

`GET /health/ready` is implemented by
[[src/nodeskclaw_rpa_engine/core/health.py#ReadinessService]].

It probes each enabled dependency (`database`, `objectStorage`, `taskApi`,
`runtimeFilesystem`) and returns 200 only when every required dependency is `healthy`.
Disabled dependencies are `disabled` and not required; `taskApi` is required only when
Worker or Runtime is enabled. On failure readiness returns 503 with a safe
`check_failed:{ExceptionType}` detail — never a server path or secret.

The Runtime filesystem probe creates, reads, and deletes a temporary file in both
`RUNTIME_CACHE_DIR` and `RUNTIME_WORK_DIR` to confirm writability.

## Structured Logging and Redaction

`configure_logging` installs a `StructuredJsonFormatter` that emits timestamp, level,
logger, message, bound `runId`/`workerId`/`flowVersionId`, and redacted extras.

`bind_log_context` sets these contextvars for the duration of a run. `redact_sensitive`
masks values under sensitive keys (password, secret, token, authorization, credential,
database_url, cookie, session, api/access/private key) and scrubs inline secrets,
bearer tokens, URL credentials, and S3 signed-query parameters. Flow log/event payloads
pass through this redactor before being persisted as callbacks.
