# AutoTask v5.3：对账单发票上传到 Task

| 项 | 内容 |
| --- | --- |
| 版本 | **v5.3** |
| 状态 | **2026-08-26 定稿并已改代码**；现场需重启唯一 Task 4520，并重开 Client（Main 有新 IPC） |
| 触发 | 正式演练扫描发票：本机 Task + 本机选文件能过；换到用户电脑报 `invoice file input missing` |
| 原则 | 发票文件必须落到 Task 服务器。用户上传是什么就存什么。Client 删除已上传的文件，Task 也要删掉。不要用用户本机路径跑 RPA。 |

---

## 1. 要解决什么

对账单「扫描发票 / 提交审核」需要把发票文件交给 Worker，由 Playwright `set_input_files` 推到 SRM。

原先 Client 走 `POST /statements/{billId}/invoice/paths`，JSON 里只有 `filePaths`（用户电脑上的绝对路径）。本机开发时 Client、Task、Engine 在同一台机器，路径碰巧能打开。用户电脑上的 Client 把 `C:\用户\...\发票.pdf` 传给服务器上的 Worker，那个路径不存在，Flow 把 `set_input_files` 失败记成 `invoice file input missing`（截图 `stmt-invoice-input-missing.png`）。

另一层：用户本机文件之后删了、换电脑再打开单据，如果只记路径，扫描和提交、以及提交成功后把发票挂到 SDMS，都会找不到文件。

Task 其实早就有真正传文件的接口 `POST /statements/{billId}/invoice`（`multipart`，字段 `files`）。Client 没用它。

---

## 2. 现场口径（2026-08-26）

1. **正常上传就是传到服务器。** 不能依赖用户本机路径。用户本地删了原文件，服务器上的那份还要能扫、能提交、能挂 SDMS。
2. **用户上传是什么就是什么。** 不按内容 hash 去重，不为「同一份文件」做唯一键。重复传就再存一份。
3. **Client 删除必须删 Task。** 详情页垃圾桶如果只改界面，刷新后又从服务器清单回来。已落到服务器的文件，点删除就要打 Task，磁盘和记录一起去掉。
4. **下次打开单据要能找回。** 上次这张单传了 2 个，再打开还是这 2 个（除非已经删过）。

不在本期：附件独立 UUID、内容指纹、跨对账单共用一份文件、Client 预览/下载发票字节。

---

## 3. 范围

| | 内容 |
| --- | --- |
| 纳入 | 扫描发票把文件字节传到 Task；按对账单目录保存；打开详情读服务器清单；删除已上传文件同步 Task；扫描/提交 RPA 只用服务器文件 |
| 不纳入 | 换 Flow 包版本；MinIO 存发票原件（本期仍落 Task 本机 `ARTIFACT_LOCAL_DIR`）；发票在 Client 里预览；同一文件跨单据去重 |

---

## 4. 怎么存、怎么认

一张对账单一个目录：

`{ARTIFACT_LOCAL_DIR}/statements/{bill_id}/{序号}_{原始文件名}`

例：`00_发票.pdf`、`01_发票.pdf`。序号只避免同名互相覆盖，不是业务主键。

| 对象 | 怎么认 | 说明 |
| --- | --- | --- |
| 对账单 | `bill_id` | 目录、下次打开找回 |
| 每个文件 | 目录里的存储文件名 | 删除时带这个名字；展示用去掉目录后的文件名 |
| 原始文件名 | 给人看 | 允许重名；不当唯一键 |

**磁盘是清单真相。** 详情 `scannedFilePaths` 优先列该目录里还在的文件；没有目录时才回退 `summary.invoice_scan.filePaths`。

**上传是追加，不是整包覆盖。** 已有 2 个再选 1 个扫描，目录变成 3 个。不要覆盖用户没删的文件。

**删除才减少。** 删一个就从目录拿掉那一个，并清掉该单已扫回的发票号/总额（`invoice_status` 回到未上传），必须重新扫描才能提交。

---

## 5. 接口

前缀均为 `/api/v1/autotask/statements`。

| 动作 | 方法 | 路径 | 行为 |
| --- | --- | --- | --- |
| 上传并扫描 | `POST` | `/{bill_id}/invoice` | `multipart` 字段 `files`；追加写入目录；用**目录里全部文件**排队扫描 |
| 仅用已存文件再扫 | `POST` | `/{bill_id}/invoice/paths` | `filePaths` 为空 = 用目录已有文件再扫；若仍传本机路径且服务器上不存在，直接 400，不要让 Worker 空转 |
| 删除一个已上传文件 | `DELETE` | `/{bill_id}/invoice-file?fileName=` | `fileName` 为存储名（如 `00_发票.pdf`）；删磁盘、改 summary、清发票号/总额 |
| 提交审核 | `POST` | `/{bill_id}/submit-review` | 忽略 Client 传来的本机路径；RPA 和事后挂 SDMS 都用目录里还在的文件 |
| 打开详情 | `GET` | `/{bill_id}` | `scannedFilePaths` 返回服务器清单 |

限制与原来一致：最多 10 个、单文件 20MB、后缀 `png/jpg/jpeg/pdf/ofd`。

旧接口 `/invoice/paths` 带真实本机路径只留给「Client、Task、Engine 同一台机器」的开发捷径。正式和用户电脑必须走 `multipart` 上传。

---

## 6. 谁干什么

| 层 | 做什么 |
| --- | --- |
| Client 渲染进程 | 选文件、列清单、点删除/扫描/提交；不读磁盘、不传路径当文件 |
| Client Main | 读用户选中的本地文件字节，`multipart` 交给 Task（新 IPC `uploadInvoiceFiles`） |
| Task | 落盘、列清单、删除、把**服务器路径**写进 Run `input.filePaths` |
| Engine / Flow | 不改包。继续 `set_input_files(filePaths)`，但这些路径必须在 Worker 能读到的 Task 磁盘上 |

提交成功后把发票挂到 SDMS，读的也是同一批服务器文件，不再读用户电脑。

---

## 7. Client 交互

1. **选择发票**：只进当前页列表。还没上传的，删掉只改界面。
2. **扫描发票**：列表里尚未在服务器上的文件走 `multipart` 上传；若列表全是已上传文件，则走「再扫」不重复传。成功后列表改显示服务器清单。
3. **删除已上传文件**：必须 `DELETE /invoice-file`。成功后列表与服务器一致；发票号/总额作废，提交按钮不可用，直到再扫。
4. **提交审核**：不再带用户本机路径。

换电脑打开同一张单：只显示服务器上还在的文件，不显示上一台电脑的路径。

---

## 8. 验收

1. 在用户电脑选发票点扫描：Task 目录出现文件；Worker 不再因本机路径报 `invoice file input missing`。
2. 关掉 Client 再打开该对账单：仍能看到上次那几个文件名。
3. 点垃圾桶删掉其中一个：刷新后少一个；服务器目录少一个；必须重新扫描才能提交。
4. 用户电脑上把原文件删了：再扫、提交、挂 SDMS 仍用服务器那份。
5. 本机开发若误走 `/invoice/paths` 且路径不在 Task 本机：接口立刻 400，不把失败丢给 Worker 重试。

---

## 9. 溯源

| 时间 | 事件 |
| --- | --- |
| 更早 | Task 已实现 `POST /{bill_id}/invoice` 存文件；Client 详情却调用 `/invoice/paths` 只传路径 |
| 2026-08-26 17:18 | 用户电脑扫描发票。日志到「Scanning invoice files」后失败：`invoice file input missing`；制品 `stmt-invoice-input-missing.png` |
| 同日口径 | 上传到服务器；不去做重；Client 删除必须删 Task；打开单据能找回 |
| 同日代码 | Client Main `multipart` 上传；Task 按单追加/删除；提交改用服务器文件。单测 `test_statement_service.py` + `test_statements_api.py` |

相关代码（便于以后改）：

- Task：`service/app/api/statements.py`、`service/app/services/statement_service.py`
- Client：`app/src/features/statements/statement-detail.tsx`、`app/src/main/autotask-api/autotask-api-client.ts`、`app/src/ipc/autotask-api/`
- Flow（未改包）：`rpa-flows/rpa_flow_srm_stmt_upload_invoice/1.1.2`、`rpa_flow_srm_stmt_submit_review/1.1.5` 仍读 `input.filePaths`
