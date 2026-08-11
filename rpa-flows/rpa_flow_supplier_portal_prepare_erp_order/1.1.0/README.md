# Supplier Portal Import ERP Sales Order

Version 1.1.0 logs in through the Engine-managed browser, opens the requested
customer purchase order, downloads its XLSX attachment, builds the agreed ERP
sales-order array, obtains an OAuth access token, and posts that array to the
ERP sales-order import endpoint.

> **Binding warning:** unlike version 1.0.0, this version performs an external
> ERP write. A WorkflowBinding must not be moved from 1.0.0 to 1.1.0 without
> explicit approval for that side effect.

## Data contract

1. The page is used only for navigation and XLSX download. Page fields never
   enter the ERP request body.
2. The XLSX supplies every mapped source field. The mapping, fixed defaults,
   empty auto-match fields, JSON types, comments rule, and China business date
   are unchanged from version 1.0.0.
3. `sourceHeaderId` and `sourceLineId` remain empty because the XLSX does not
   provide stable source-record IDs. The Flow never generates random IDs.
4. The HTTP request body is the ERP payload array itself. Local runtime return
   metadata is not wrapped around the request.

## OAuth and import behavior

- Token: POST `http://192.168.99.111:8080/core/oauth/token` with
  `grant_type`, `client_id`, and `client_secret` as URL query parameters.
- Import: POST
  `http://192.168.99.111:8080/core/api/srm/so/salesOrderImport` with a bearer
  Authorization header and JSON content type.
- Success requires HTTP 2xx, `code` equal to `2000`, and `success` equal to
  `true`.
- Explicit ERP rejection is a business failure. Authentication or endpoint
  configuration errors are fatal. A timeout, disconnect, server error, or
  contradictory/throttled response after order submission becomes
  WAITING_HUMAN so the order is not submitted again automatically.
- Tokens, Authorization headers, OAuth query strings, and raw authentication
  responses are never logged, emitted, or saved as Artifacts.

## Required local configuration

Before packaging a runnable version, replace these two constants in `flow.py`:

```python
ERP_CLIENT_ID = '__FILL_ERP_CLIENT_ID__'
ERP_CLIENT_SECRET = '__FILL_ERP_CLIENT_SECRET__'
```

The placeholder package is intentionally non-runnable. Do not send the real
values through Codex chat. The Registry does not permit overwriting an existing
Flow version, so each credential rotation requires a new version and an updated
WorkflowBinding.

The only Flow input remains `po_no`. The supplier portal address is provided by
the production lease as `config.portalUrl` and exposed to the Flow as
`ctx.portal_url`; local test runners must provide the same value explicitly.

## Artifact and result boundary

The XLSX download and Playwright screenshots continue to use
`ctx.artifacts`. The current Artifact API cannot create arbitrary JSON
Artifacts, so the ERP response is emitted only as a whitelisted, non-sensitive
event and returned for local tests. Production Runtime ignores the Python return
value.

This Flow has no stable idempotency key because the XLSX does not contain source
record IDs. WAITING_HUMAN reduces ordinary retry risk, but a Worker/process
crash after ERP commit cannot be made at-most-once by Flow code alone. Production
activation therefore requires an ERP idempotency/query contract or an Engine
post-submit retry barrier.
