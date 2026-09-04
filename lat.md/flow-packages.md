# Flow Packages

`rpa-flows/` holds versioned Playwright Flow packages consumed by the Engine
Runtime — not a standalone service.

Each family is `rpa_flow_<name>/<semver>/` with `manifest.json`,
`selectors.json`, `flow.py`, tests, and usually a Chinese README.

## Package Contract

A shippable package is a ZIP of manifest + selectors + entry module; entry is
always `flow.py:run`.

Example demo entry: [[rpa-flows/rpa_flow_login_demo/1.1.0/flow.py#run]]. Manifest
declares `rpaFlowId`, `engineType` (`PLAYWRIGHT_CDP`), `entrypoint`,
`supportedWorkflowCodes`, portal types, input schema, and capabilities.

## Version Trees

Semver directories are immutable contracts; publish receipts record checksum and
Engine `versionId`.

Demo portals often use `data-rpa=*`; official Element UI portals use Chinese
text/CSS selectors and ship as separate versions. Formal drill and production
share one official Flow; Binding carries sample PO / dryRun knobs.

## Tooling

Build and local run helpers import Engine validators/runtime from sibling
`rpa-engine/`.

- `scripts/build_flow_package.py` — ZIP with Engine upload limits
- `tools/local_flow_runner.py` — validate by default; `--run` executes via Runtime

Flows may import `nodeskclaw_rpa_engine.runtime` helpers (errors, shared login,
`login_boe_srm`).
They must not open browsers or access Task/Engine databases directly. See
[[design-decisions#Flow Sandbox Contract]].

## BOE packing Flows

Three packages enrich lines, save an SRM draft, and submit a change-order.

They live under `rpa-flows/rpa_flow_srm_boe_pack_*`. Navigation clicks 送货管理
then 发票箱单. Flows never `goto` ticket URLs and never wait on email OTP.
