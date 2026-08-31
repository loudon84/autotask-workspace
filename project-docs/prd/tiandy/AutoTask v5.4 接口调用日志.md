# AutoTask v5.4：接口调用日志

| 项 | 内容 |
| --- | --- |
| 版本 | **v5.4** |
| 状态 | **2026-08-27 迁库已执行，正式 Binding 已切 1.2.17 / 1.3.3** |
| 触发 | 对接系统变多后，任务只知道报错码，运维看不到当时打了哪个 URL、入参和出参是什么 |
| 原则 | 任务信息和报错不变。运维打开失败任务，同一页能看到这次主动打出去的接口：URL、入参、出参。用 `taskId` 关联，不塞进证据文件。 |

---

## 1. 要解决什么

任务详情已经有任务信息和报错。证据中心是截图、下载件。`RunEvent` 只有一两百字摘要。建单 Flow 调 ERP 失败时往往只抛错误码，请求体和响应体丢掉。

运维排障需要的是：**这份任务打过哪些接口、URL 是什么、入参是什么、对方回了什么。**

不在本期：用日志替代报错；把报文当截图/下载件；录浏览器访问门户的全部网络请求。

---

## 2. 口径（2026-08-27）

1. **一张调用日志表。** 一次 HTTP 一行。
2. **用任务关联。** 必填 `task_id`；RPA 再带 `run_id`。Task 自己打的接口（没有 Run）只写 `task_id`。
3. **看入口是任务详情。** 打开失败任务 → 报错旁边能点开接口调用。不进证据中心翻文件。
4. **只记我们主动打出去的 HTTP**（ERP、SDMS、以后的 OA 等）。门户页面点击、Playwright 请求不记。
5. **密钥不进表。** `Authorization`、Cookie、密码、`client_secret`、access token 写入前抹掉。Token 接口只记打了 token、URL、HTTP 状态，不记 token 正文。

---

## 3. 范围

| | 内容 |
| --- | --- |
| 纳入 | Task 表 `integration_call_logs`；按任务列出 URL/入参/出参；Engine `ctx.http` 与 Task HTTP 客户端统一落库；第一期接 ERP 建单、SDMS 附件、SDMS 对账查询 |
| 不纳入 | 证据中心新类型；HAR/整包网络录制；独立「对接中心」跨任务检索页；改现有报错文案；换 Flow 业务逻辑（只换 HTTP 出口） |

---

## 4. 运维怎么找

1. 打开失败任务（现有任务信息、报错照旧）。
2. 详情增加 **接口调用**（与执行日志、关联证据并列）。
3. 列表：时间、系统、方法、URL、HTTP 状态、`error_code`。
4. 点开一行：入参、出参全文（脱敏后）。

同一任务多次重试：每次 Run 各有若干行，按时间排。列表可带 `run_id` 以免和上次执行混在一起。

---

## 5. 存储

新表 `integration_call_logs`（名称以迁移为准），Task 库，至少：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `id` | 是 | UUID |
| `tenant_id` | 是 | 与任务同租户 |
| `task_id` | 是 | 和任务关联 |
| `run_id` | 否 | RPA 当次执行；Task 侧调用可空 |
| `system` | 是 | `ERP` / `SDMS` / `OA` 等，列表展示 |
| `method` | 是 | `GET` / `POST` / … |
| `url` | 是 | 完整 URL；query 里的密钥去掉 |
| `request_body` | 否 | 入参文本（JSON 则格式化存储；form 则脱敏后的键值） |
| `response_body` | 否 | 出参原文；非 JSON 也原样存 |
| `status_code` | 否 | HTTP 状态；连不上则为空 |
| `error_code` | 否 | 与任务报错码对齐，如 `ERP_TOKEN_REJECTED` |
| `duration_ms` | 否 | 耗时 |
| `request_truncated` / `response_truncated` | 是 | 超 1MB 截断并标 true |
| 时间戳、软删 | 是 | 与现有表一致 |

索引：`task_id + created_at`；`run_id`（可空）。不对外部系统表建外键。

**迁移文件可以提交；未获用户授权不得对数据库执行 DDL。**

单行硬顶 1MB（入参、出参各算）。超出截断，并置截断标记。不要把报文写进 `run_events.payload`。

---

## 6. 谁写、谁读

| 层 | 做什么 |
| --- | --- |
| Engine | 提供 `ctx.http`。Flow 禁止再直连 `httpx` 打业务系统。每次请求结束后把记录回调 Task（带当前租约的 `task_id`/`run_id`）。 |
| Flow（第一期） | 建单 ERP token + 导入、传合同 SDMS 附件：改走 `ctx.http`，业务逻辑不变。 |
| Task HTTP 客户端 | 对账单查 SDMS 金额、提交成功后挂发票等到 SDMS：同一套拦截器，只带 `task_id`。 |
| Task API | `GET /api/v1/autotask/tasks/{taskId}/integration-calls`，权限与看该任务相同。 |
| Client | 任务详情「接口调用」列表 + 点开入参/出参。不改证据中心。 |

Worker 写日志走内部接口（与 Artifact/Event 回调同鉴权），不要让 Flow 直接写库。

连不上、超时、HTTP 4xx/5xx、业务 JSON 失败：**只要发出去了或试图发出去，都要有一行。** 响应体能拿到就记；网络错误则 `response_body` 记异常摘要，`status_code` 为空。

---

## 7. 脱敏

写入前处理，日志里不得出现明文密钥。至少：

- Header：`Authorization`、`Cookie`、`Set-Cookie` → `[REDACTED]`
- 字段名（不区分大小写）含 `password`、`secret`、`token`、`access_token`、`client_secret`、`authorization` → 值替换为 `[REDACTED]`
- Query：同上
- OAuth token 接口：不存响应里的 `access_token`；请求里的 `client_secret` 抹掉

本文档和 `PROJECT_CONTROL.md` 仍不得记录真实密钥或带签名的对象存储 URL。

---

## 8. 第一期接入

| 调用 | 谁打 | `system` |
| --- | --- | --- |
| ERP OAuth token | 建单 Flow | `ERP` |
| ERP 销售订单导入 | 建单 Flow | `ERP` |
| SDMS 附件上传 | 传合同 Flow | `SDMS` |
| SDMS 对账金额查询 | Task `sdms_client` | `SDMS` |
| 提交审核后发票挂 SDMS | Task | `SDMS` |

以后新系统：只进统一 HTTP 客户端，不必再为每个 Flow 手写落库。

---

## 9. 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/autotask/tasks/{taskId}/integration-calls` | 该任务全部调用，按时间升序；可 query `runId` |
| POST | Worker 内部回调（路径实现时与 Event/Artifact 对齐） | 写入一行；无任务权限的外部调用方不可用 |

列表项含：`id`、`runId`、`system`、`method`、`url`、`statusCode`、`errorCode`、`durationMs`、`createdAt`、截断标记。入参/出参可同包返回（运维要一次看清）；单任务调用次数很少，不必再拆详情接口。

---

## 10. 验收

1. 建单 Run 调 ERP 被对方拒绝：任务报错仍是现有错误码；详情「接口调用」能看到导入 URL、脱敏后的请求 JSON、对方响应正文。
2. 同一 Run 的 token + 导入是两行；token 行没有 access token 明文。
3. 对账单查 SDMS 金额失败：该对账相关任务能看到查询 URL、query/入参、响应或错误摘要（无 `run_id` 也可）。
4. 任务详情不把报文写进报错文案；证据中心不出现这份 JSON 文件。
5. 直连 `httpx` 的旧路径在第一期接入的 Flow/客户端上已去掉（单测覆盖拦截器会写库、会脱敏）。

---

## 11. 本期落地顺序

1. 表 + 写入 API + 脱敏（含单测）。**授权后再执行迁移。**
2. Engine `ctx.http` + Task 客户端拦截器。
3. 第一期五个调用改出口。
4. Client 任务详情「接口调用」。

相关现状（便于实施时对照）：

- 证据：`service/app/models/artifact.py`；Client 任务详情「关联证据」
- 事件摘要：`service/app/models/run_event.py`；`RunLogPanel`
- ERP 直连：`rpa-flows/rpa_flow_supplier_portal_prepare_erp_order/1.2.16/flow.py`
- SDMS：`service/app/services/sdms_client.py`、`sdms_attachment_client.py`
