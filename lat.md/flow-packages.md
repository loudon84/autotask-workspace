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

Four packages enrich lines, save an SRM draft, submit a change-order, and
delete a draft before CS cancel.

They live under `rpa-flows/rpa_flow_srm_boe_pack_*`. Delete-draft 1.0.1
(`rpa_flow_srm_boe_pack_delete_draft`) searches by 发票箱单流水号. Empty list
or missing number is success (`alreadyMissing`). Otherwise it clicks the
frozen-column checkbox (the main-table checkbox is covered), then 影刀
「删除-草稿单删除」 and the 删除 confirm 「确定」, then clicks list 「搜 索」
and waits for 「暂无数据」.
Steps follow the 影刀
recording (`project-docs/prd/boe/影刀-京东方-selectorsV2.xml`), verified by
live-DOM probes (2026-09-07): login clicks 「供应商登录」on the portal SPA
(same-tab SSO to `#/dashboard/index?ticket=…`; login success = dashboard URL
or `.ant-menu` 首页 menu, never the ticket), CAS form fills
`#username`/`#password`, checks `#checkPrivacyPolicy`, clicks
`input[type=submit][name=submit]`; navigation clicks the 「交货计划管理」app
card which opens bsrm in a NEW tab (`open_invoice_packing` returns the active
page), then 送货管理 → 发票箱单.
On the create page, `prepare_invoice_create` first switches 启用AI识别 to 否
(default 是 locks every form item and disables 项目信息「新增」), then picks
BOE 工厂 via the field's `button.content-search` → 「获取工厂」 dialog
(without a factory, 「新增」 only toasts 请先填写基本信息中的工厂字段).
The 采购凭证查询 dialog is scoped by `.el-dialog[aria-label='采购凭证查询']`;
行项目/剩余开票数 are parsed from the backfilled 项目信息 row, not the popup.
Flows never `goto` ticket URLs and never wait on email OTP.
总体积 is an el-input-number carrying a static `aria-disabled="true"`
attribute, so Playwright `fill()` refuses it as disabled and times out — but
the input itself is NOT disabled and accepts typing (verified by live probe:
force-click + `Control+a` + `keyboard.type` sticks and Vue keeps the value).
save_draft/submit fill it via `_fill_input_number` (force-click keyboard
typing, JS native-setter fallback). Since 1.0.4 `prepare_invoice_create` reads
the factory input back after the dialog confirm and retries the pick once,
raising `BOE_FACTORY_NOT_SET` if the field stays empty.
Demo-phase safety (1.0.6): save_draft only ever clicks 保存
(`save_button` excludes any 提交-labelled button), enrich never saves the
document, and the submit flow hard-blocks with `BOE_SUBMIT_BLOCKED_DEMO`
unless the caller explicitly passes `allowRealSubmit=true` — real SRM
submission is impossible during demo/development. The Client 「提交 SRM 单据」
button also shows a warning confirm before dispatching.
save_draft 1.0.7 fills the backfilled 项目信息 row after 采购凭证保存:
本次开票数 / 净重 (el-input-number keyboard fill) and 原产国/地区
(el-select `placeholder=国/地区`, click the `regionSrmName` option —
Client already maps WMS `coo` via 基础数据). Before 保存 it deletes every
附件行 whose type is 双签PO/协议 (the create page seeds four types; an empty
dual-sign row blocks save; phase 1 still does not upload files). Draft
number is read from the 发票箱单流水号 input value, not inner_text.
Submit 1.0.15 uploads Client-picked PDFs onto those attachment rows.
1.0.11: 保存 closes the create window, so the draft number is **not** read
from the form. After save the flow waits for `.invoice-list`, searches by
供应商发票号, and takes the first row that is 草稿 **and** contains that
invoice number (`I\d+` 流水号). Frozen-left 流水号 cells are merged with
the main row text.
1.0.12 follows the 影刀 list-query steps: click 展开, fill
`placeholder='供应商发票号'` (not `发票箱单流水号`), pick 状态=草稿, then
`搜 索`. The first-row 流水号 is the text button `I\d+`. After save the
search retries while the list refreshes. A retry that opens an already-saved
draft skips re-attaching a PO that SRM already holds.
1.0.13: opening a list draft clicks the visible `I…` text button (影刀),
not the first `td` (that cell is a rowspan checkbox under the frozen
overlay and Playwright times out). If Client still has no `srmDraftNo`
and the list already has that invoice's 草稿, the flow writes the list
流水号 back and does not reopen the form.
Submit 1.0.14 follows 天地伟业 Binding `dryRun`: missing or `true` is
fail-closed (never click SRM 提交; trial-click only, `committed=false`).
Only explicit `dryRun: false` may click 提交. Write-guard is installed
in dryRun so POST/PUT/PATCH/DELETE to SRM are aborted.
1.0.15 still never clicks 提交 in dryRun, but **does** upload Client
attachment PDFs onto the SRM 附件信息 table (影刀: 新增 + `input[type=file]`)
and clicks 保存 so files persist on the draft. Write-guard starts only
after 保存, with upload allowed.
1.0.16 dryRun is save-only: apply diffs, upload PDFs, click 保存, then
stop. It does not trial-click 提交. SRM stays a draft so CS can keep
editing. Only explicit `dryRun: false` clicks 提交.
1.0.17 enrich also reads 订单数量 / 订单单位 / 净重单位 from the
backfilled 项目信息 row. Submit applies existing-row 本次开票数/净重 diffs.
1.0.18 finds that row by concatenating the left frozen table (PO/料号)
with the main table; 1.0.17 only read the main row and raised
`BOE_LINE_ROW_MISSING`. Trailing-zero number diffs are ignored.
1.0.19 follows the 影刀 「搜索有数据」step: after list/采购凭证 search
(and after opening a draft), wait until a row actually contains the
key — empty `tr` / 「暂无数据」do not count — then locate 本次开票数/净重.
Do not query row elements on an empty table.
1.0.20 opens a draft the 影刀 way: expand → fill `发票箱单流水号` →
search → wait for that 流水号 text button → click it. Do not scan every
list `tr` with Playwright `inner_text()` (hidden rows time out 30s).
1.0.21 uploads attachments in SRM order: rows 1–3 are 箱单/发票/提运单
(fixed; never 新增); each 双签 PDF clicks 新增 then uploads. save_draft
already deleted the empty dual-sign row.
1.0.22 clicks the frozen-right 「上传文件」 `a.elBtnA` (影刀) and feeds
the FileChooser; it does not `set_input_files` on an unbound hidden
input. Row locators use `.el-table__fixed-body-wrapper`.
1.0.23 save-draft: SRM `POST …/invoicepackinglist/create` can persist the
draft without returning HTTP (trace status -1). The form stays open so
`.invoice-list` never appears. After save, wait for the API or form 流水号;
if still on the form, click 返回 and search the list.
1.0.8 region pick: the 原产国/地区 column sits off-screen in the
horizontal scroller (`rect.x≈2000`); click the `.el-select` wrapper (the
input is `readonly` until opened), type `regionSrmName` (e.g. 中国台湾),
then click the exact dropdown item — typing alone or clicking an unfiltered
list does not commit the value.
Multi-line (1.0.9): each Client line is attached then filled **on that
row** (`item_data_row` last main-table tr after 采购凭证保存), not via a
page-wide `.last` input (frozen-column clones would steal qty/net/region).
After picking a region, Escape closes the dropdown before the next line.
Dual-sign attachment rows are deleted by type (up to 20), covering extra
rows SRM may seed per PO. The 操作/删除 button lives on
`.el-table__fixed-right` (1.0.10): the same button in the main body is
`visible=false` under the freeze overlay, so clicking the main-row 删除
times out; 箱单/发票/提运单 deletes are `disabled`, only 双签PO/协议 is
clickable. List-menu 删除草稿 (1.0.1 delete-draft Flow) is a different
control: `.avue-crud__left button.el-button--danger`.
