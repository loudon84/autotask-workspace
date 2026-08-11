# Task 1 RPA Flow 包开发规范与交接说明

最后更新：2026-08-04

## 1. 文档用途

本文面向接手 `rpa_flow_supplier_portal_prepare_erp_order` 的 Flow 开发工程师，说明这个包要完成什么业务、源码和 ZIP 应包含什么、哪些契约不能随意改变，以及如何测试和交付新版本。

通用平台规则仍以以下文档为准：

- `D:\AutoTask-Workspace\project-docs\designs\rpa-flow-development-guide.md`
- `D:\AutoTask-Workspace\project-docs\designs\v0.6_rpa-engine-server-worker-production-baseline.md`
- `D:\AutoTask-Workspace\project-docs\PROJECT_CONTROL.md`

本文件放在 Flow 根目录，仅用于开发交接，不得打入运行 ZIP。

## 2. 这个 Flow 要做什么

这是业务任务 1：根据任务输入的客户采购订单号，从供应商门户取得订单 XLSX，校验附件确实属于当前门户订单，构造 ERP 销售订单报文并提交 ERP。

完整流程是：

```text
接收 po_no
→ 使用 Engine 注入的浏览器页面登录供应商门户
→ 按 po_no 搜索并进入订单详情
→ 只读采集门户全部“订单行号 + 客户料号”
→ 点击一次“下载订单”并保存 XLSX Artifact
→ 解析 XLSX 的供应商及全部订单行字段
→ 门户和 XLSX 做双向完整对账
→ 只纠正已通过对账行的 XLSX poNo
→ 构造 ERP 请求体
→ 获取 ERP Access Token
→ 只提交一次 ERP 订单导入请求
→ 严格校验 ERP 行级结果
→ 返回订单号、供应商和完整逐行明细
```

Task 服务可在 Task 1 成功后根据输出创建 Task 2；Flow 本身不得直接创建后继任务、修改 Task 状态或写 Task 数据库。

## 3. 不属于本 Flow 的职责

本 Flow 不负责：

- 维护预计交货日期、保存或签章；这是 Task 2。
- 下载已回签订单并上传附件系统；这是 Task 3。
- 启动浏览器、创建 BrowserContext 或自行连接 CDP。
- 创建 Task、Run、Binding、Portal 或修改任务状态。
- 直接连接任何业务数据库。
- 在 ERP 结果不明确时查询不到状态却自动重复提交。

## 4. 稳定接口契约

| 项目 | 固定值 |
| --- | --- |
| Flow ID | `rpa_flow_supplier_portal_prepare_erp_order` |
| Workflow Code | `srm_prepare_erp_order` |
| Engine Type | `PLAYWRIGHT_CDP` |
| Entry Point | `flow.py:run` |
| 最低 Engine 版本 | `0.5.0` |
| 成功输出 Schema | `ORDER_DOWNLOAD_PUSH_OUTPUT_V1` |

输入只有一个必填字段：

```json
{
  "po_no": "POJS2607180002"
}
```

校验规则：

- `ctx.input` 和 `ctx.credentials` 必须按 `collections.abc.Mapping` 处理，兼容 Engine 的 `MappingProxyType`。
- `po_no` 去除首尾空白并转大写。
- 格式为 1～64 位大写字母、数字、下划线或连字符，首位必须为字母或数字。

成功输出只能保留以下顶层字段：

```json
{
  "schemaVersion": "ORDER_DOWNLOAD_PUSH_OUTPUT_V1",
  "poNo": "POJS2607180002",
  "orderNumber": "ERP生成的销售订单号",
  "supplierCode": "供应商编码",
  "supplierName": "供应商名称",
  "lineCount": 2,
  "lines": []
}
```

`lines` 保留规范化后的完整业务明细，包括 XLSX 解析得到的字段以及计算得到的 `taxRate`、`unTaxPrice`。成功输出不得包含 `erpPayload`、`erpResponse`、`orderDetail`、`draft`、Token、Authorization Header 或任何凭据字段。

## 5. 数据来源与映射边界

### 5.1 门户页面

门户页面只用于：

- 登录和导航。
- 确认当前订单号。
- 读取全部订单行的 `lineNumber + customerItemNumber`。
- 下载订单 XLSX。
- 生成过程截图。

门户页面的数量、价格、日期、供应商名称等字段不得直接覆盖 XLSX 数据。

### 5.2 XLSX

ERP 业务数据以 XLSX 为准。以下列必须存在：

```text
供应商编号、供应商名称、订单编号、订单行号、料号、料品名称、
料品规格、数量、单位、单价（元）、价税合计（元）、要求交货日期
```

同时保留 XLSX 中存在的可选业务字段：

```text
物料状态、内码、标准交货日期（天）、是否满足LT、供方交期、
欠交数量、备注、直发备注
```

解析器必须防止无效 ZIP/XLSX、危险工作表路径、异常膨胀、重复列名、空明细、无效数值和供应商身份不一致。

### 5.3 门户与附件对账

明细身份键固定为：

```text
lineNumber + customerItemNumber
```

必须满足：

1. 门户和 XLSX 均至少一行。
2. 两边行数完全相同。
3. 两边行号各自唯一。
4. 两边身份集合完全相同。
5. 相同料号出现在不同唯一行号时允许通过。

只有 XLSX 行内 `poNo` 错误可以兼容。通过完整对账后，复制原明细并将每行 `poNo` 改为当前任务 `po_no`；不得修改解析器传入的原对象，也不得丢失数量、单位、价格、金额、日期或备注。

严禁通过以下方式“修复”串单：

```python
lines = [line for line in lines if line["poNo"] == po_no]
```

这种过滤会丢掉身份正确、但订单号字段写错的有效行。缺行、多行、重复行号或料号不一致必须在 ERP OAuth 之前失败。

### 5.4 ERP 报文

当前约定：

- `customerName`、`orderType` 使用既定业务默认值。
- `orderedDate` 使用执行当日中国时区日期。
- `orgName` 来自 XLSX 供应商名称。
- `comments` 来自 XLSX 行备注去重汇总。
- `isAttachment = "Y"`。
- `custPoLine` 来自 XLSX 订单行号。
- `custPoNumber` 必须全部等于当前任务 `po_no`。
- `custItemNum`、数量、含税单价、需求交货日期来自 XLSX。
- `taxRate` 默认 `0.13`。
- `unTaxPrice = unitSellingPrice / 1.13`，四舍五入保留四位小数。
- 由 ERP 自动匹配的字段保持空字符串，不从页面猜测。

## 6. ERP 成功、失败与幂等边界

只有同时满足以下条件才可返回成功：

- HTTP 为 2xx。
- 顶层 `code = "2000"`。
- 顶层 `success = true`。
- `rows` 为非空数组。
- 每一行 `processStatusCode = "COMPLETE"`。
- 所有成功行给出同一个非空 ERP `orderNumber`。

处理规则：

- 任一行 `processStatusCode = "ERROR"`：`FAILED / ERP_ORDER_IMPORT_ROW_FAILED`，事件中保留脱敏后的具体 `processMessage`。
- 明确认证、端点、请求或业务拒绝：按对应 Fatal/Business 错误失败。
- ERP POST 后发生超时、断连、取消、HTTP 408/429/5xx、响应矛盾或订单号无法确认：`WAITING_HUMAN / ERP_ORDER_IMPORT_OUTCOME_UNKNOWN`。
- 结果不明确时禁止自动再次 POST；必须先人工核实 ERP 是否已生成订单。

当前 XLSX 没有可靠的源记录 ID，因此尚无稳定 ERP 幂等键。维护代码时不得把提交后的不确定结果改成普通可重试错误。

## 7. Flow 源码结构

`flow.py` 建议继续保持以下分层：

| 模块/对象 | 职责 |
| --- | --- |
| `SupplierPortalAdapter` | 登录、订单搜索、详情导航、门户明细身份读取、下载和页面稳定等待 |
| `parse_order_xlsx()` | 安全解析 XLSX，输出供应商和完整明细 |
| `reconcile_attachment_with_portal()` | 纯函数，完成双向明细身份对账和 `poNo` 规范化 |
| `build_erp_draft()` | 只根据规范化 XLSX 和既定默认值构造 ERP 请求体 |
| `ErpSalesOrderClient` | OAuth、单次订单导入、响应和错误分类 |
| `_prepare_erp_order()` | 编排 ERP 提交前的门户、下载、对账、构造和截图步骤 |
| `run(ctx)` | 校验运行条件、提交 ERP、记录结果事件并返回冻结输出 |

纯数据逻辑应保持为可独立单测的纯函数；门户差异应留在 Adapter；选择器应放在 `selectors.json`，不要散落到业务逻辑里。

## 8. 目录和包内容

开发目录结构：

```text
rpa_flow_supplier_portal_prepare_erp_order/
├─ DEVELOPMENT_SPEC.md              # 本交接文档，不进 ZIP
├─ 1.2.3/                           # 已发布历史版本，禁止修改
│  ├─ flow.py
│  ├─ manifest.json
│  ├─ selectors.json
│  ├─ README.md
│  └─ tests/
│     └─ test_flow.py
├─ 1.2.4/                           # 下一修复版本，开发时新建
└─ rpa_flow_supplier_portal_prepare_erp_order-1.2.4.zip
```

每个源码版本目录包含：

- `flow.py`：运行实现。
- `manifest.json`：Flow ID、版本、入口、输入 Schema、能力和最低 Engine 版本。
- `selectors.json`：门户页面定位器。
- `README.md`：该版本业务行为、输入输出、错误和风险说明。
- `tests/test_flow.py`：开发测试，不进入 ZIP。

发布 ZIP 根目录只能包含：

```text
flow.py
manifest.json
selectors.json
README.md
```

ZIP 不能多包一层目录，也不能包含测试、缓存、`.env`、临时文件、本交接文档或其他说明文件。

## 9. Engine 运行边界

Flow 必须：

- 使用 `ctx.page`，不能调用 `playwright.start()`、`browser.launch()` 或 `connect_over_cdp()`。
- 从 `ctx.portal_url` 获取门户入口。
- 从 `ctx.input` 获取任务输入。
- 从 `ctx.credentials` 获取门户账号凭据。
- 通过 `ctx.artifacts` 保存下载和截图。
- 通过 `ctx.events`、`ctx.log` 上报非敏感过程信息。
- 通过标准 RPA 异常让 Runtime 映射 `FAILED`、`WAITING_HUMAN` 或可重试状态。

普通 Flow 凭据应由 `credentialRef` 注入。Task 1 当前存在经所有者明确批准的“受控私有包内嵌 ERP OAuth 凭据”例外：

- 不得在 README、测试快照、日志、事件或交接回复中写出实际值。
- 源码、ZIP、Registry 对象和 Worker 缓存必须限制为授权开发/运维人员访问。
- 不得提交公开 Git 或公开制品库。
- 凭据轮换必须创建新 Flow 版本、重新测试和发布，不能覆盖已发布版本。
- 此例外不得自动复制到其他 Flow；新系统凭据仍需单独确认管理方式。

## 10. Artifact 和可观察性

至少保留：

- 下载得到的非空 XLSX Artifact。
- `supplier-portal-erp-draft-prepared` 截图。
- Runtime 在失败时生成的失败截图和 Playwright Trace。

截图前必须等待：下载确认框消失、详情和明细渲染完成、加载遮罩消失、字体和可见图片加载完成、布局连续两次稳定，最后再等待约 300ms。

关键事件包括：

- 登录、搜索和下载步骤开始/完成。
- `ORDER_ATTACHMENT_RECONCILED`。
- `ERP_ORDER_DRAFT_PREPARED`。
- ERP OAuth 和导入步骤开始/完成/失败。
- `ERP_ORDER_IMPORT_SUCCEEDED`。

事件只记录当前订单号、计数、错误码和经过长度限制的业务消息，不记录凭据、Token、Authorization Header、OAuth 查询参数或完整敏感配置。

## 11. 主要错误码

| 类别 | 错误码示例 | 处理 |
| --- | --- | --- |
| 输入/配置 | `FLOW_INPUT_INVALID`、`PORTAL_URL_MISSING`、`FLOW_SELECTOR_MISSING` | FAILED |
| 登录 | `SRM_CREDENTIALS_MISSING`、`SRM_LOGIN_FAILED`、`SRM_LOGIN_TIMEOUT` | Fatal/Business/Retryable，按异常类型处理 |
| 人工验证 | `HUMAN_VERIFICATION_REQUIRED` | WAITING_HUMAN |
| 门户订单 | `BUSINESS_NOT_FOUND`、`ORDER_DETAIL_UNAVAILABLE` | FAILED 或 Retryable |
| 门户明细 | `ORDER_DETAIL_LINES_UNAVAILABLE`、`ORDER_DETAIL_LINE_DUPLICATE` | FAILED，且不得进入下载/ERP |
| XLSX | `ORDER_ATTACHMENT_INVALID`、`ORDER_ATTACHMENT_DATA_INCOMPLETE`、`ORDER_ATTACHMENT_DATA_INVALID` | FAILED |
| 对账 | `ORDER_ATTACHMENT_LINE_COUNT_MISMATCH`、`ORDER_ATTACHMENT_LINE_DUPLICATE`、`ORDER_ATTACHMENT_LINE_MISMATCH` | FAILED，且不得调用 ERP |
| ERP 明确失败 | `ERP_ACCESS_TOKEN_INVALID`、`ERP_ORDER_IMPORT_REJECTED`、`ERP_ORDER_IMPORT_ROW_FAILED` | FAILED |
| ERP 结果不明确 | `ERP_ORDER_IMPORT_OUTCOME_UNKNOWN` | WAITING_HUMAN，不得自动重提 |

## 12. 当前版本状态与下一项修复

| 版本 | 状态 | 说明 |
| --- | --- | --- |
| `1.2.2` | 当前 Binding 使用 | 可以执行，但没有 1.2.3 的门户/XLSX 双键完整对账 |
| `1.2.3` | 已发布，停止用于新 Run | 新增完整对账，但真实门户 Element UI 固定列导致行号读取回归 |
| `1.2.4` | 待开发 | 修复行号采集，完整保留 1.2.3 的串单保护 |

1.2.3 的问题不是订单缺少明细。真实 Trace 已证明两条料号可读、页面可见行号为 `10/20`，但代码用 `cells[0].innerText` 读取时得到空字符串。接手人必须在新版本修复该 DOM 假设：

- 不得只依赖固定列单元格的 `innerText`。
- 可使用经真实 DOM 验证的 `textContent`，或从同行稳定 `data-rpa` 后缀解析行号。
- 必须同时兼容普通订单详情页和待签章详情页。
- 仍然使用同一个 `ctx.page`，不得另开浏览器。
- 修复仅改变门户行号采集，不改变对账键、ERP 映射或输出 Schema。

已发布的 1.2.3 禁止原地修改。应复制为 `1.2.4`，同步修改 manifest 和 README 版本，再重建新 ZIP。

## 13. 必测场景

每个新版本至少覆盖：

1. `MappingProxyType` 输入和凭据可用。
2. 合法/非法 `po_no`。
3. 已知验证码登录；未知验证码进入 `WAITING_HUMAN`。
4. 普通详情页和待签详情页均能进入并读取行身份。
5. Element UI 固定列 `innerText` 为空时仍能读取真实行号。
6. 门户首行未渲染、身份不完整、重复行号时失败。
7. XLSX 必填列、所有映射字段、数值、日期、ZIP 安全及大小限制。
8. 干净附件完整匹配。
9. XLSX 个别 `poNo` 错误但双键匹配时通过并统一规范化。
10. 缺行、多行、重复行号、同行号不同料号时拒绝。
11. 同料号出现在不同唯一行号时允许通过。
12. 对账失败时 ERP Client 零调用。
13. ERP 所有 `custPoNumber` 和输出所有 `lines[].poNo` 都等于任务 `po_no`。
14. 数量、单位、价格、金额、日期和备注在规范化后保持不变。
15. 税率和未税单价计算正确。
16. ERP 成功、行级 ERROR、认证失败、业务拒绝和结果不明确矩阵。
17. ERP POST 最多一次；结果不明确不重试。
18. 成功输出只包含冻结契约，且不存在载荷、响应和凭据字段。
19. 截图发生在页面稳定等待完成之后。

## 14. 构建和质量门禁

开发完成后必须执行：

1. 从版本目录运行全部 pytest。
2. 从 Engine 根目录运行同一测试，确认测试不依赖当前工作目录。
3. Ruff 全部通过。
4. Python 语法、两个 JSON 和全部文本 UTF-8 无 BOM 检查通过。
5. 生成确定性 ZIP，根目录只有四个运行文件。
6. 校验 ZIP 四个文件与版本源码逐字节一致。
7. Engine 五项包策略全部通过且无警告：
   - `ZIP_STRUCTURE`
   - `MANIFEST_SCHEMA`
   - `ENTRYPOINT_ASYNC`
   - `RUNTIME_POLICY`
   - `PACKAGE_SHA256`
8. 记录 ZIP 路径、字节数和 SHA-256。
9. 扫描包和报告，确保不输出凭据、Token、Authorization Header 或不应出现的环境信息。

## 15. 发布与 Binding 规则

- `rpaFlowId + version` 不可变；任何代码、选择器、README 或凭据变化都必须升版本。
- 上传后先校验，再发布；发布成功不等于业务启用。
- Binding 必须保存精确 Flow Version UUID 和 checksum，不能使用 latest、占位 UUID 或零校验和。
- 新版本不会自动替换旧 Binding；切换和真实任务运行必须单独获得授权。
- 回滚通过把 Binding 显式指回旧版本完成，不能覆盖或删除旧包。
- 未获授权时，Flow 工程师只开发、测试和构建候选包，不上传、不发布、不切换 Binding、不创建 Task、不调用 ERP。

## 16. 交付汇报模板

```text
Flow ID：
Workflow Code：
新版本：
相对上一版本的改动：
输入契约：
输出 Schema：
Playwright/CDP 行为：
门户/XLSX 对账边界：
ERP POST 次数与结果判断：
异常映射：
pytest：
Ruff：
Engine 五项包校验：
ZIP 路径：
ZIP 大小：
SHA-256：
Artifact：
已执行的外部写操作：无 / 列明
未执行事项：上传、发布、Binding、Task、ERP、数据库等
待 Engine/Task 配合事项：
已知风险与下一步：
```

