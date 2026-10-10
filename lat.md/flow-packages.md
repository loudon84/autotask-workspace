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

Official statement generate `1.1.3` sets page size to 100, clicks the header
checkbox, and pages only when 「共 N 条」is over 100. It checks that total
against Client `lines` length and does not tick rows. `dryRun` still skips
生成对账单. See
[[rpa-flows/rpa_flow_srm_stmt_generate/1.1.3/flow.py#ReceiptListAdapter#select_all_and_assert_count]].

Official invoice scan flows (`srm_stmt_upload_invoice` 1.1.3,
`srm_stmt_submit_review` 1.1.6+) wait for the upload to finish before clicking
弹窗「确定」: the portal shows a fullscreen 「上传中，请稍候...」
`el-loading-mask` that covers 确定, so clicking after a fixed 400 ms raced the
upload and timed out or no-oped (`STMT_INVOICE_OCR_EMPTY`). The fix waits for
the success toast or mask disappearance (≤60 s, error toast fails fast) before
the confirm click. See
[[rpa-flows/rpa_flow_srm_stmt_submit_review/1.1.7/flow.py#StatementSubmitAdapter#_wait_invoice_upload_done]].

`srm_stmt_submit_review` 1.1.7 fixes a false-SUCCESS mode: the submit click was
confirmed by any `.el-message--success`, so the still-visible 「上传成功」toast
from the invoice scan satisfied the check and the run reported SUCCESS while
SRM stayed 未对账/未上传 (output statuses were hardcoded, not observed). 1.1.7
clears stale toasts before the click, treats route change back to the statement
list (the portal's own `$router.push` on success) or a fresh success toast as
success, maps `.el-message--warning` to `SRM_STMT_SUBMIT_BLOCKED` (portal-side
validation, e.g. 请上传发票 / rcvQty), and reads the real row statuses back
from the list into the output. See
[[rpa-flows/rpa_flow_srm_stmt_submit_review/1.1.7/flow.py#StatementSubmitAdapter#click_submit]]
and
[[rpa-flows/rpa_flow_srm_stmt_submit_review/1.1.7/flow.py#StatementSubmitAdapter#read_statement_status]].

## Tooling

Build and local run helpers import Engine validators/runtime from sibling
`rpa-engine/`.

- `scripts/build_flow_package.py` — ZIP with Engine upload limits
- `tools/local_flow_runner.py` — validate by default; `--run` executes via Runtime

Flows may import `nodeskclaw_rpa_engine.runtime` helpers (errors, shared login).
They must not open browsers or access Task/Engine databases directly. See
[[design-decisions#Flow Sandbox Contract]].
