# AutoTask v5.0：门户存密码、清掉运行时硬编码

| 项 | 内容 |
| --- | --- |
| 版本 | **v5.0** |
| 状态 | **代码已改（2026-08-19）**；硬编码对照见第 7 节。运维（填 `.env`、重填门户密码、切 Flow Binding）未做完 |
| 原则 | 换人、换门户不准改 Engine `.env`、不准改 Flow 源码。人登录走 Client；SRM 账号走门户；SDMS/ERP 环境基址走 Task `.env`；服务器互访才走各服务自己的 `.env`。 |

---

## 1. 要解决什么

客户订单、对账单已经能跑。换人用不了，不是缺角色权限，也不是登录页 Endpoint 没配好。

开发时把「这一次能跑」写进了三处：Engine `.env`、Flow 源码、Task 代码常量。执行任务时登录页管不到这些，所以看起来像摆设。

---

## 2. 执行时数据从哪来

| 谁 | 决定什么 | 不决定什么 |
| --- | --- | --- |
| 登录页 Endpoint | 这台 Client 连哪套 Auth / Task | 机器人登哪家 SRM、SDMS/ERP 调哪个地址、SDMS 网页链接 |
| Task `.env` | `SMC_API_BASE_URL`（内部查询接口平台）、`SDMS_BASE_URL`（SDMS 网页跳转）、ERP/OA、OAuth、文档上传主机；以及库/JWT/Engine 互访 | 哪个操作人、哪个门户的 SRM 密码 |
| Engine `.env` | Engine↔Task↔MinIO、Worker 开关。`CREDENTIAL_RESOLVER_MODE=disabled` | 门户密码、SDMS/ERP 业务地址 |
| 门户记录 | SRM 网址、登录账号、密码、客户编码/名称、我方业务实体（ERP `orgName`）、OU（存档） | 服务装在哪台机器、SDMS 域名 |
| Binding.config | 仅 `portalUrl` / `dryRun` / `browserSession` | SDMS/ERP 域名和密钥 |
| 租约 API | 把门户凭据 + Task 环境基址带给 Engine | Engine 不读 Task 库 |

登录页改了，服务器进程不知道。两边要对齐同一套 Task，靠装机配好，不靠运行时同步。

**上线只切 Task `.env` 里的基址/OAuth，重启 Task。不要逐个改 Binding JSON。**

---

## 3. 门户密码（原方案，不变）

1. 建/改门户填登录账号和密码；改时密码框留空 = 不改。
2. 密码存在现有 `credential_ref` 列。列表、详情不返回。界面改成「密码」，去掉「凭据引用」。
3. 领任务时租约带上该门户的账号和密码。Engine 直接用来登 SRM。关掉 `mock_env`，不要按门户 id 对 `.env`。
4. 人登录 AutoTask 不变。本期不做角色权限。

已有门户这一列是旧编号，上线后要在编辑里重新填一次密码。

---

## 4. 运行时硬编码：本期清掉

任务真正执行会读到的，才进本期。一次性脚本、`.local` 探测、单测里的 `127.0.0.1` 不算。

### 4.1 Engine `.env`（开发插销）

搬走：`CREDENTIAL_RESOLVER_MODE=mock_env`、全部 `MOCK_SRM_*`、示例里的 `TIANDY_PROD_*`。  
删掉没用的：`TASK_CLIENT_ID` / `SECRET`、`LOCAL_TASK_CLIENT_*`（`TASK_AUTH_MODE=none`，没在用）。

留下：端口、库、JWT、Auth 地址、`TASK_API_BASE_URL`、`RPA_ENGINE_PUBLIC_BASE_URL`、MinIO、`TASK_ARTIFACT_UPLOAD_BASE_URL`、Worker 开关。这是机房接线，换门户不改。

### 4.2 Flow 源码（建销售订单 / 传合同）

这些是开发时写死的测试 SDMS，换环境要改包：

- `ERP_TOKEN_URL`、`ERP_ORDER_IMPORT_URL`、上传附件 URL
- `ERP_CLIENT_ID` / `ERP_CLIENT_SECRET`
- 建单抬头 `customerName` 写死「天地偉業…」

改成：地址和客户端密钥放 **Task `.env`（`SDMS_BASE_URL` / `ERP_BASE_URL` / `OA_BASE_URL` / `ERP_CLIENT_ID` / `ERP_CLIENT_SECRET`）**，领任务时写进租约 `config`，Flow 只拼路径。客户名称用门户已有的 `erpEntityName`。不要写进 Binding JSON，否则上线要改每一个 Binding。

密钥不要进 Git、不要进 `.env` 当「某个门户」。

### 4.3 Task 代码（对账单）

`sdms_client.py` 里查询地址和 `CUSTOMER_SITE = C007193-…` 写死天地伟业。换客户会错。

改成：查询地址 = Task `SMC_API_BASE_URL`（公司内部 SQL→JSON 接口平台）+ 固定路径 `/sdms/ar_check/view_doc_srm`；客户站点用门户已有的 `erpEntityCode`（建门户时填 SDMS 站点编码）。  
发票上传主机 `SDMS_ATTACHMENT_API_BASE_URL`、SDMS 网页 `SDMS_BASE_URL` 各是各的域名，也都在 Task `.env`。

### 4.4 Client SDMS 网页链接

登录页不要再配 `sdmsWebBaseUrl`。打开销售订单/对账单网页读 Task `SDMS_BASE_URL`（网页域名，不是 `SMC_API_BASE_URL`）。Client 登录后向 Task 拉基址；没配就不渲染链接。换测试/正式只改 Task `.env` 并重启 4520。

---

## 5. 明确不做

- 独立密码库、Engine 直连 `portal_accounts`、为密码再加一条 API
- 角色权限、改登录页当总控台
- 新增数据库列或执行 DDL
- 改探测脚本 / 手工运维脚本里的租户 id、演示门户地址
- 演示包验证码文件名对照表（只服务演示站）
- 把 Task/Engine/MinIO 互访地址搬进门户或登录页

---

## 6. 验收

- 换门户：改门户账号密码和客户编码/名称，不必改 Engine `.env`，不必改 Flow 源码。
- 演示门户和正式门户可同时存在，各用各的密码。
- 换操作人：用自己的 Auth 账号登录；SDMS 工号仍是当前登录账号。
- 换测试/正式：改 Task `.env` 的 `SMC_API_BASE_URL`、`SDMS_BASE_URL`（及 ERP/文档基址），重启 Task。不改 Flow 源码、不逐个改 Binding、不往 Engine `.env` 加门户项、不在登录页配 SDMS。
- 列表/详情看不到门户密码；租约以外的日志不打密码。
- Engine 去掉 `mock_env` 后，任务仍能领到并登 SRM。

---

## 7. 硬编码对照清单（2026-08-19 对照代码）

核对范围：任务真正执行会读到的。密钥不写入本文档。  
状态分三列：**代码**（仓库新路径是否已改）／**线上生效**（本机 `.env`、门户数据、Binding 版本是否已切）。

漏的风险主要在：旧 Binding 仍跑 1.2.7/1.2.2、门户密码没重填、Task `.env` 基址没填。这三步不做，线上行为和改代码前几乎一样。

### 7.1 本期要清的

| # | 原来写死在哪 | 内容 | 怎么解决 | 代码 | 线上生效 |
| --- | --- | --- | --- | --- | --- |
| 1 | Engine `.env` | `CREDENTIAL_RESOLVER_MODE=mock_env` + `MOCK_SRM_*` 登 SRM | 产品路径 `disabled`；账号密码走门户 → 租约 `credentials`。`.env.example` 已去掉 MOCK 凭据项；`mock_env` 只留给旧单测 | 已改 | **未确认**：本机 Engine `.env` 需设 `disabled` 并删掉 `MOCK_SRM_*` 凭据 |
| 2 | Engine `.env` 示例 | `TIANDY_PROD_*` 第二组门户凭据 | 删示例；正式门户密码放门户记录 | 已改 | 本机若还留这些键可删，执行已不依赖 |
| 3 | Engine `.env` 示例 | 无用的 `TASK_CLIENT_ID` / `SECRET` | 示例删掉；`TASK_AUTH_MODE=none` | 已改 | 机房接线，换门户本来不用动 |
| 4 | 建单 Flow 源码 | `ERP_TOKEN_URL` / `ERP_ORDER_IMPORT_URL`（测试环境主机） | Task `ERP_BASE_URL` → 租约 `erpBaseUrl` → Flow 拼路径 | **1.2.9 已改** | **已生效**：1.2.9 已发布并切 Binding |
| 5 | 建单 Flow 源码 | `ERP_CLIENT_ID` / `ERP_CLIENT_SECRET` | Task `.env` → 租约；密钥进 `ctx.credentials`，不进日志 | **1.2.9 已改** | 同上 |
| 6 | 建单 Flow 源码 | 抬头 `customerName` 写死固定公司名 | 门户 `erpEntityName` → 租约 `customerName` | **1.2.9 已改** | 同上 |
| 7 | 传合同 Flow 源码 | ERP token / `uploadAttachment` URL、文档上传 URL、OAuth 密钥 | Task `ERP_BASE_URL` + `SDMS_ATTACHMENT_API_BASE_URL` → 租约 `erpBaseUrl` / `docBaseUrl` | **1.2.3 已改** | **已生效**：1.2.3 已发布并切 Binding |
| 8 | Task `sdms_client.py` | 查询 URL + 写死站点编码 | `SMC_API_BASE_URL` + 路径 `/sdms/ar_check/view_doc_srm`；`custom_son_code` 由门户客户编号 + 我方公司编号拼接 | 已改 | **已生效**：Task `.env` 已填 `SMC_API_BASE_URL`；门户编号已拆为 `C007193-01` + `ou=104` |
| 9 | Client 登录页 | `sdmsWebBaseUrl` 写死内网 IP / 每人配一份 | 登录页去掉该项；Client 从 Task `GET /integration-endpoints` 读网页用的 `SDMS_BASE_URL` | 已改 | **已生效**：Task `.env` 已填 `SDMS_BASE_URL` |
| 10 | 门户表单 | 「凭据引用」当编号 | 改成密码框；列名仍是 `credential_ref`；列表/详情不返回 | 已改 | **待做**：已有门户那一列还是旧编号，编辑里须重填真正密码，否则登不上 SRM |
| 11 | 建单 Flow 源码 | 抬头 `orgName` 用 XLSX 供应商名称 | 门户「业务实体」→ 租约 `businessEntity` → ERP `orgName`。当前接口按名称反推 OU，不传 `orgCode` | **1.2.9 已改** | **已生效**：门户业务实体已填 `深圳市芯云信息科技有限公司`；1.2.9 已发布并切 Binding |

### 7.2 有意保留（不算漏）

| 项 | 为什么不算漏 |
| --- | --- |
| 接口路径 `/core/oauth/token`、`/sdms/ar_check/view_doc_srm`、`/upload` | 环境无关，换测试/正式只换主机 |
| `flag=SDMS_SO1` / `SDMS_ARR`、税率、订单类型等业务常量 | 不是某套环境的域名 |
| 演示站验证码文件名对照表 `CAPTCHA_CODES` | 第 5 节明确不做 |
| 探测脚本、`.local`、单测里的本机/假地址 | 第 4 节开头：不算本期 |
| Auth / Task / Engine / MinIO / 库地址 | 机房接线，本来就在各服务 `.env` |
| 历史包：建单 ≤1.2.7、传合同 ≤1.2.2 源码里的主机和密钥 | **故意不改历史包**。Binding 还指着它们，执行仍会用旧硬编码 |

### 7.3 运维未做完（代码改了也不算上线完成）

1. Task `.env` 填写并重启 4520：`SMC_API_BASE_URL`、`SDMS_BASE_URL`、`ERP_BASE_URL`、`ERP_CLIENT_ID`、`ERP_CLIENT_SECRET`、`SDMS_ATTACHMENT_API_BASE_URL`（空则失败，不会回退到源码常量）。以后 OA 用 `OA_BASE_URL`。**已完成**。
2. 每个门户编辑里重填一次 SRM 密码。**待做**。
3. 门户 `erpEntityCode` = 客户/供应商编号，`erpEntityName` = 建单抬头客户名；`businessEntity` = 我方公司全称（须与 ERP 组织名称一致，接口据此反推 OU）；`ou` = 我方公司编号（对账单 `custom_son_code` 拼接用）。**天地伟业test 已填**。
4. 发布 Registry 并切 Binding：建单 **1.2.10**（演示门户专用包，`81c94b03-…`，已切，取代有选择器 bug 的 1.2.9），传合同 **1.2.3**（已切）。**已完成**。正式门户后续单独出版本（不复用 1.2.10 的 `data-rpa` 选择器）。
5. Engine `.env`：`CREDENTIAL_RESOLVER_MODE=disabled`，去掉 `MOCK_SRM_*` 凭据。**已完成**。
6. Binding JSON 不要再塞 ERP/SDMS 域名；只留 `portalUrl` / `dryRun` / 浏览器会话。
7. **多门户定时扫单**：`ScanScheduler` 已改为只扫「有 ENABLED `srm_scan_pending_orders` 绑定的门户」（join binding+template 过滤），不再对所有启用门户盲扫。新客户要纳入定时扫单，建一条扫单绑定即可，无需改代码。**已完成**。
8. **门户唯一性**：已从 `(租户+实体类型+地址+登录账号)` 改为只校验 `(租户+门户名称)`；`erpEntityCode` 编辑模式放开可改。迁移 `e2b7c14a3d05` 已执行。**已完成**。
9. **后台作业开关上线清单**（代码默认全 false，靠 `.env` 打开；`service/.env.example` 已补全三项及说明）：
   - `SUCCESSOR_JOB_ENABLED=true` — 子任务跑完自动推进下一阶段。流程实例自动流转靠它，**上线必须 true**。当前 `.env` 已 true。
   - `SCAN_JOB_ENABLED=true` — 每天到点自动扫「有扫单绑定的门户」建流程实例。要自动扫单就 true，开发可 false（用手动按钮）。当前 `.env` **未设→false**，上线按需开。
   - `SIGN_POLL_JOB_ENABLED=true` — 定时轮询回签状态。要自动回签探测就 true。当前 `.env` 已 true。
   - 上线前在 Task `.env` 确认这三项，重启 4520。看启动日志确认每个调度器是"已启动"还是"保持关闭"。

### 7.4 验收对照（当前卡在哪）

| 验收 | 状态 |
| --- | --- |
| 换门户只改门户账号密码和编码/名称，不改 Engine `.env`、不改 Flow 源码 | 代码路径已通；须先做 7.3 的 2–4 |
| 演示 / 正式两门户可同时跑 | 代码可以；密码必须各填各的 |
| 换人：Auth 登录；SDMS 工号仍是当前登录账号 | 未改这条链路 |
| 换测试/正式：只改 Task `.env`（`SMC_API_BASE_URL` + `SDMS_BASE_URL` 等） | 代码已通；须填 `.env` 并切新 Flow |
| 列表/详情无密码；RunEvent 无密钥 | 代码已做 |
| `mock_env` 关掉后仍能领任务登 SRM | 代码已做；依赖门户里是真密码 + Engine `disabled` |
