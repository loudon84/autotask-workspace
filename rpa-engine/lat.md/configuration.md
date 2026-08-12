# Configuration

All runtime behavior is driven by environment variables loaded into
[[src/nodeskclaw_rpa_engine/core/config.py#Settings]], a pydantic-settings model that
reads `.env` (UTF-8) and validates cross-field dependencies at construction time.

`Settings` is the single source of truth for feature flags, limits, and dependency
gating. `public_snapshot` exposes a safe subset (no secrets or endpoints) used in
startup logs and readiness responses.

## Settings

`Settings` groups application identity, Flow package limits, database, MinIO/S3, Task
API, Worker identity and timing, Runtime directories/timeouts, and the restricted
`mock_env` credential resolver.

`FLOW_PACKAGE_MAX_*` bounds compressed/uncompressed size, file count, and compression
ratio. Worker timing controls heartbeat, poll, renew, and offline thresholds. Runtime
controls cache/work directories, timeout, retries, trace mode, and output size.

## Dependency Gating

`validate_enabled_dependencies` enforces the safe-feature matrix.

- `DATABASE_ENABLED=true` requires a `postgresql+asyncpg` URL targeting the
  `nodeskclaw_task` database.
- `MINIO_ENABLED=true` requires endpoint, access key, secret key, and bucket.
- `WORKER_ENABLED=true` requires the database and the `PLAYWRIGHT_CDP` +
  `BROWSER_SESSION_MANAGED` capabilities, and `OFFLINE_THRESHOLD > HEARTBEAT_INTERVAL`.
- `WORKER_LEASE_ENABLED=true` requires `WORKER_ENABLED=true`.
- `RUNTIME_ENABLED=true` requires `MINIO_ENABLED=true`.
- `CREDENTIAL_RESOLVER_MODE=mock_env` is allowed only in `development`/`test` and
  requires all `MOCK_SRM_*` settings.
- `RUNTIME_CACHE_DIR` and `RUNTIME_WORK_DIR` must be different paths.

## Package Identity

The installable project name is `rpa-engine`; the importable Python package remains
`nodeskclaw_rpa_engine`. Local uvicorn must target `nodeskclaw_rpa_engine.main:app`.

Do not add unrelated PyPI packages to `pyproject.toml` dependencies. A mistaken
`myapplication` dependency previously installed a Flask `app` package that collided
with the uvicorn target `app.main:app`.

## External Dependency Policy

PostgreSQL and MinIO/S3 are disabled by default.

The application never calls `create_all`, runs Alembic, creates schemas, creates
buckets, or seeds data. Database passwords, MinIO keys, and service-account secrets
must come from a local `.env`, deployment environment variables, or managed secret
injection — never committed or copied into logs. `TASK_AUTH_MODE=none` is a
test-environment compatibility mode; service-account token exchange is reserved for a
later phase.

## Database Hold Point

The ORM baseline defines nine Engine-owned tables in the `rpa_engine` schema.

The SQL baseline `sql/0002_rpa_engine_initial_schema.sql` and Alembic revision
`20260713_0001` are operator-controlled artifacts. Application startup and tests never
stamp, migrate, execute DDL, or seed data. See [[data-model#Engine-Owned Tables]].
