# NoDeskClaw RPA Engine Knowledge Graph

Structured markdown describing the Engine's architecture, design decisions, and domain
concepts, managed by [lat.md](https://www.npmjs.com/package/lat.md).

Install the `lat` command with `npm i -g lat.md` and run `lat --help`. Source code is
anchored to these sections with `@lat:` comments and `[[wiki links]]`.

## Sections

Index of architecture and domain documentation for the Engine.

- [[architecture]] — System overview, module map, and ownership boundaries.
- [[flow-registry]] — Flow Registry domain, manifest, package validation, and version state machine.
- [[worker-pool]] — Worker Pool, lease contract, attempt lifecycle, and recovery.
- [[runtime]] — RPA Runtime: loader, browser, context, artifacts, errors, and output.
- [[callback-outbox]] — Callback outbox: idempotency, ordering, retry, and dispatcher.
- [[configuration]] — Settings, dependency gating, and external dependency policy.
- [[health-logging]] — Health/readiness endpoints and structured logging with redaction.
- [[data-model]] — Engine-owned PostgreSQL tables in the `rpa_engine` schema.
- [[integration-boundaries]] — Task integration contract and current limitations.
