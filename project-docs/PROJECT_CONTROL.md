# AutoTask 开发总控

最后更新：2026-08-26

## 1. 用途

本文档是 AutoTask 开发记录和每日开发日志的统一入口。

开始新的开发会话前：

1. 阅读本文档。
2. 检查当前决策、状态、未决问题和后续行动。
3. 阅读“每日开发日志”下的最新记录。
4. 会话结束前，将已验证的工作追加到当天记录中。

本文档不得记录密码、访问令牌、数据库凭据、私钥或带签名的对象存储 URL。

## 2. 项目位置

| 项目 | 位置 | 状态 |
| --- | --- | --- |
| AutoTask 产品工作区 | 本仓库根（Cursor workspace） | 活跃工作区 |
| AutoTask Client | `app/`（原 `AutoTask-studio/` / `copilot-autotask/`；package `name` 仍为 `AutoTask-studio`） | 开发中；允许扫描的代码根 |
| nodeskclaw-task | `service/`（原 `nodeskclaw/nodeskclaw-task/`）；测试服务 `http://192.168.102.247:4520` | 允许扫描的代码根；代码已迁移到 `service/`；测试服务器可达 |
| rpa-engine（原 nodeskclaw-rpa-engine） | `rpa-engine/` | 允许扫描的代码根；目录已从 `nodeskclaw-rpa-engine` 重命名；测试基线可运行 |
| RPA Flow 工作区 | `rpa-flows/` | 允许扫描的代码根 |
| RPA authoring | `rpa-authoring/`（含 `uipath/login_demo`） | 允许扫描的代码根；登录演示已完成 |
| nodeskclaw-backend | `http://192.168.102.247:4510` | 测试服务器可达；**不在**本工作区允许代码扫描根内 |

## 3. 当前架构决策

1. `rpa-engine`（工作区目录；Python 包/服务标识仍为 `nodeskclaw_rpa_engine` / `nodeskclaw-rpa-engine`）是独立的服务和项目。
2. Worker Pool 是 RPA Engine 的内部模块，不是另一个服务。
3. RPA Engine 负责 Flow Registry、Flow Package 元数据、Worker Pool、Runtime、浏览器会话管理器、Artifact 记录器、错误处理器和回调客户端。
4. `nodeskclaw-task` 负责任务业务、WorkflowBinding、RpaRun、RunEvent、StepRun、Artifact 元数据、HumanAction 和 RunCommand 发布。
5. RPA 执行使用 Playwright + CDP。首个实现支持 `MANAGED`；`PERSISTENT_PROFILE` 和 `CDP_ATTACH` 仍属于受控扩展。
6. RPA Flow 入口为 `flow.py:run(ctx)`。Flow 不能自行启动浏览器、直接连接 CDP 或访问业务数据库。门户凭据通常通过 `ctx.credentials` 注入；经所有者明确决定，受限的私有非 Git Flow 包可以内嵌外部系统凭据，但该包、Registry 对象和 Worker 缓存必须实施访问控制，并且不得在日志或本文档中记录任何密钥。
7. Flow 包按版本管理并存储在 MinIO/S3 中。Worker 本地目录仅作为缓存。
8. Flow Registry 同时支持 `GLOBAL` 平台 Flow 和 `TENANT` 组织私有 Flow。
9. 当前测试部署使用 PostgreSQL 数据库 `nodeskclaw_task`、Engine 专属 schema `rpa_engine` 及九张 Engine 专属表。跨服务引用继续以外部字符串保存，不对 Task 专属表建立外键。
10. 可以准备数据库设计和 DDL；未另行授权前不创建库、不执行其它 DDL。**v5.1 迁移 `f1a9c3e74b20` 已于 2026-08-24 经用户授权执行。v5.2 迁移 `g3b8e2a91c40`（`scheduler_jobs`）同日已执行。v5.1 `is_task_admin` 迁移 `a7e4b2c81d09` 已于 2026-08-25 经用户授权执行（当前 head）。**
11. **正式门户演练与上线共用同一份 Flow。** 演示站 / 正式站因页面不同仍拆包。演练与真上线不拆包：Flow 只实现上线操作；样例单号、`treatAsPending`、`dryRun` 进 Binding。操作说明：`project-docs/prd/AutoTask v4.1 天地伟业正式演练与上线SOP.md`。

## 4. 当前状态

| 工作流 | 状态 | 依据 |
| --- | --- | --- |
| Client 远程 API 模式 | 已连接 | Auth 和 Task 健康检查均返回 HTTP 200 |
| Client 端点默认值 | 已更新 | 已为端口 4510 和 4520 配置测试服务器 IP |
| 受保护 API 边界 | 已验证 | 无 Token 访问 `/auth/me` 和 `/autotask/tasks` 均返回 HTTP 401 |
| UiPath 登录流程 | 已转换 | 已在 Client 工作区下创建 Flow Package |
| 登录浏览器行为 | 已验证 | Playwright 已在模拟 SRM 门户到达 `/#/dashboard` |
| 登录验证码 OCR | 实验性 | 1.1.0 固定图片准确率为 60%，最终浏览器 Flow 成功率为 85% |
| RPA Engine 实现 | 测试基线可运行 | 0.5.0 提供 Flow Registry、Worker Pool、Runtime、MANAGED Playwright、Artifact 回调及 EVENT/FINISH Outbox 投递 |
| RPA Engine 数据库 | 测试 schema 已启用 | Engine 在 `nodeskclaw_task.rpa_engine` 中拥有九张表；2026-07-23 的 Flow 工作未执行数据库或 DDL 操作 |
| 开发记录 | 已整合 | 当前状态和每日日志均存放在本文档中 |
| 产品工作区迁移 | 已完成 | 新工作区已通过源码、运行时、Flow 和 UiPath 检查；旧路径经验证后已移至 `D:\AutoTask-Archive\workspace-migration-2026-07-10` |
| 供应商门户 ERP 订单 Flow（任务 1） | 1.2.3 已发布；首次 Run 在门户行号读取处失败，当前 Binding 为 1.2.2 | 1.2.3 Registry UUID `9323dbc8-e79c-473d-bd31-d51d719746b9`，摘要 `sha256:c46db0e74567de313f8122a77ef8347e7e3fb690eef034d97d04e99228778859`；Run `5dde0f74-1dc0-4f02-9dcd-7e9c81991eaf` 精确使用 1.2.3，并在 ERP OAuth 前因固定列 `innerText` 为空返回 `ORDER_DETAIL_LINES_UNAVAILABLE`；当前 Binding 只读回查为 1.2.2，未执行 ERP 写入 |
| ERP 订单 Task 端到端测试 | 传输闭环已验证、业务数据被拒绝 | 登录、详情导航、XLSX 下载、OAuth、ERP POST、事件、Artifact、租约续期和完成回调均已完成；ERP 返回行级物料匹配错误 |
| 本地 Auth/Task/Engine 闭环 | 已运行验证 | 三个服务健康检查均为 HTTP 200；本地 Task/Run 已完成一次 `rpa_flow_mock_srm_fetch_po` SUCCESS |
| Client 证据中心 | 已支持真实预览和下载 | 截图使用临时签名地址接近全屏预览；截图和 XLSX 通过 Electron 下载到用户下载目录 |
| 供应商门户任务 2→任务 3 自动链 | Task 2 1.2.0 停在 WAITING_HUMAN；Task 3 1.0.1 已发布 | Task 2 Run `635a6af1-c0c3-4d79-adf1-3ff4f8d56adb` 未生成后继任务；Task 3 跳过“已回签”校验版本已发布，UUID `85a896c4-f2df-4683-b41a-073872cded46`、摘要 `sha256:8284930376c590b8138f2ef74495414b6217db3d582464595e6588ca02714f37`，现有 Task 3 Binding 尚未切换，也未单独运行 |
| 天地伟业对账单（v3.0） | 生成 Flow 1.0.6 已切 Binding；Client 可重新生成 | 勾选：用订单编号 span 定位所在行，再点选择列 checkbox。 |
| 天地伟业对账单 SOP 体验（v3.01） | 详情已补回勾选明细；需重启唯一 Task 4520 | 六步进度：填单页待创建/SDMS核准；列表按 stage；详情对齐客户订单并展示 `summary.lines`。 |
| 天地伟业对账单优化（v3.02） | 代码已改，需重启唯一 Task 4520 | 详情「对账明细」；展示 SDMS `check_num` 链接；SRM 提交成功后 HTTP 把发票传到 SDMS（`flag=SDMS_ARR`）。 |
| 客户订单节点4 SDMS 附件（v2.02 R4） | Flow **1.2.2 已发布并切 Binding**；**需重启唯一 Task 4520** | `username`=Auth 登录工号。Registry `e8cdd181-…`；Binding `8c272818-…`。 |
| 天地伟业切正式演练（v4.0） | 正式门户已建；扫单 **1.1.3**（Binding 已写 `searches`）；建单 **1.2.15**；回签探测 **1.1.4**；下合同 **1.3.2**；收货查询 **1.1.3**；生成对账单 **1.1.0 dryRun=true**；扫描发票 **1.1.2**；提交审核 **1.1.5 dryRun=true**（需切 Binding；1.1.4 会拦正式站发票上传） | 扫单换样例 PO 改 Binding 第二条 `poNo`。列表筛已回签+单号后再进详情；合同入口是「查看签章」。收货查询走正式日期面板（开始 00:00:00 / 结束 23:59:59）+未提交筛选+导出 Excel。扫描选文件后必点弹窗确定。生成仍是可见+未禁用即过；提交 dryRun 为 trial click。演示 test 扫单仍 1.0.2、建单仍 1.2.11、回签仍 1.0.1、下合同仍 1.2.5、收货仍 1.0.4、生成仍 1.0.7、提交仍 1.0.7。**需重启唯一 Task 4520**；建议重启 Engine 4610。 |
| 门户存密码（v5.0） | 代码已改：密码走门户；SDMS/ERP 基址走 Task `.env`；Client SDMS 链接也读 Task `SDMS_BASE_URL`；建单 `orgName` 走门户业务实体（1.2.9 未发布） | 登录页不再配 SDMS。上线改 Task `.env` 后重启 4520；填业务实体后迁库并切 1.2.9。 |
| 权限 v5.1（管人接口后补） | 代码已接 Auth：`/me` 的 `is_super_admin` / `is_task_admin`；登录拉 `GET /members/{id}/subordinate` 写入 `managed_user_ids`。模块管理员与超管在 AutoTask 内全放开。迁移 `a7e4b2c81d09` **已执行**（当前 head）。登录后 `POST /session/sync` 强制刷新缓存；平时 TTL；新 token `iat` 也会强制刷新 | **需重启唯一 Task 4520** 后，用 AutoTask **重新登录**（不是只登 Auth 控制台）。 |
| 调度中心 v5.2 | **Binding 任务已上**：迁移已执行，6 条 job 已回填。4520 已于 09:48 换成 JobScheduler（pid 30444）。正式演练回签 `*/5` 在跑，但门户无待回签候选所以详情任务列表为空 | 要把 `POJS2607170008` 从 `SDMS_CREATED` 推进到待回签才会产生探测任务 |

## 5. 未决问题

1. 仍需在 AutoTask Client 中完成真实 nodeskclaw 账号登录，以验证已认证的 Task 数据。
2. 当前 nodeskclaw-task OpenAPI 尚未提供 Client 原型所需的 RPA Components、Settings 和 Audit Logs 端点。
3. Client 原型中的 HumanAction 路由与当前 nodeskclaw-task OpenAPI 不一致。
4. 测试服务器的 Redis 端口 `6379` 不可达，这会阻塞后续 RunCommand Queue 集成。
5. RPA Engine 仍需完成 Worker 认证、可靠 Artifact 恢复、操作系统级 Flow 隔离和提交后幂等处理等生产加固。
6. 仓库现有全项目 TypeScript 和格式诊断问题；定向端点测试已通过。
7. 演示验证码 OCR 准确率未达到无人值守要求，必须保留 `WAITING_HUMAN` 回退。
8. `npm ci` 报告 31 个依赖漏洞（4 个低危、27 个高危）；修复前需单独进行兼容性评审。
9. 本地 Client HEAD 比 `origin/master` 落后一个提交；远程登录修复与本地 `src/main/auth/auth-client.ts` 修改重叠。
10. ERP 新映射逐行复测已确认第 10、20、30、40、50、80 行客户料号可映射；业务侧于 2026-07-30 确认第 60 行 `1B.30040.020259` 和第 70 行 `1B.30040.020256` 也已建立映射，尚待一次完整八行 Task 复测验证实际生效。当前 ERP 测试环境允许相同字段反复创建订单，已生成的七张单行测试订单暂不要求核实或清理。
11. ERP 订单 Flow 没有稳定的幂等键，因为 XLSX 不提供源记录 ID。若 Worker 在 ERP 提交后崩溃，则在缺少 ERP 查询/幂等契约或 Engine 重试屏障时无法确定结果。
12. Task 1 本次 Run 已精确使用 `1.2.1` 并修复待签章详情页兼容，但 ERP 对本次八个客户料号返回物料编码匹配错误；完成 ERP 测试主数据映射并核实未生成订单前，不得重复运行。
13. 测试环境 Task 仍需确认并修正 Artifact `public/download base URL`，确保返回的下载地址可由实际 Client 所在网络访问；本地 `127.0.0.1` 闭环已验证。
14. 任务 2 Flow `1.2.0` 已切换精确 Binding 并完成一次受控八行验证。Flow 只点击一次签章并在刷新后发现订单仍为“待签章”、八行日期为空，Trace 的 51 条网络记录全部为 GET、写请求为 0，因此安全进入 `ORDER_SIGN_STATUS_UNCONFIRMED`。需由演示门户实现可持久化且可回读的签章接口/模拟契约；修复前不得重试该订单或放宽 Flow 的最终状态验证。
15. Task `.env` 中的 `SKIP_AUTO_MIGRATE=1` 当前不会被启动逻辑读取，因为 `app.main` 只检查进程环境变量；本次重启仍调用了 `alembic upgrade head`。当前数据库已在 head 且本次未新增迁移，后续重启前应修正配置读取或显式注入该进程变量。

## 6. 后续行动

1. 拉取或合并前，对已获取的远程登录修复与当前本地认证修改进行协调。
2. 验证账号登录以及认证后的 Dashboard/Task 响应。
3. 使 Client 远程 API 路径与当前 nodeskclaw-task OpenAPI 保持一致。
4. 准备 RPA Engine 数据库设计文档和 PostgreSQL DDL，但不执行。
5. 在用户明确授权启动后，对 Task 1 执行一次完整八行受控复测，验证第 60 行 `1B.30040.020259` 和第 70 行 `1B.30040.020256` 的新映射已在当前测试环境、客户名称及业务实体维度下生效。当前七张受控单行测试订单无需核实或清理。
6. 映射修复后，复核 Task 1 Binding/Run 快照仍为精确 `1.2.1` 且 Runtime 整段自动重试为 0，再创建一次新的受控 Run。
7. 生产启用前，定义 ERP 幂等或订单状态查询契约，或实现 Engine 提交后重试屏障。
8. 扩大验证码基准测试，并在考虑无人值守登录前评估门户专用 OCR 改进方案。
9. 修正测试环境 Task Artifact 的 public/download base URL，并在部署版 Client 中复测截图预览及 PNG/XLSX 下载。
10. 正式链路仍需修复演示门户的签章持久化契约；当前绕过方案已发布 Task 3 `1.0.1`，下一步需精确切换 Task 3 Binding，再由用户授权单独创建 Task 3。由于 Task 2 已是 `WAITING_HUMAN` 且没有成功输出，Task 服务不会自动创建后继任务；不得把独立 Task 3 成功记作 Task 2→3 自动链成功。
11. 修正 Task 自动迁移开关，使 `.env` 的 `SKIP_AUTO_MIGRATE=1` 能在启动阶段生效，并增加启动配置测试。
12. ~~**待授权**：执行 Alembic `b2e8a4c91f30`~~ **已执行（2026-08-13）**：`process_line_items` 已补齐 SRM 附件列；详情接口此前因缺列 500，现应可正常返回。
13. **v2.02 运维（已完成）**：`prepare` Binding→**1.2.6**；`srm_check_reply_status` Template+Binding→**1.0.0**；本机 Task 已开 `SIGN_POLL_JOB_ENABLED=true`（见 2026-08-13 日志）。
14. **R1 限制（已澄清）**：演示门户**当场签章**常不落库，该笔单据刷新后未必仍是「已回签」，不能拿它验轮询。初始化种子里另有单据本身就是「已回签」，可用这些 PO 把流程实例推到 `SIGN_REQUESTED` 再验 `check_reply`→自动归档。
15. TEMP 签章回填（`rpa_flow_srm_sign_order` 1.0.1）仍待门户落库修复后删除。
16. **对账单**：查询 RPA 已通，后续生成/发票/提交改由 Client 操作；SDMS 当月无单时生成会被拦住。
17. **v4.0 阶段 1 已落地**：正式门户「天地伟业-国际-正式演练」已绑扫单/回签/收货 **1.1.0**（正式选择器）。演示 Binding 仍 1.0.x。下一步：Client 手动扫单验收；阶段 2 出正式建单+下合同（不设 dryRun），阶段 3 写步骤 + dryRun。
18. **v5.0**：PRD 已扩。换人/换门户不准改 `.env` 和 Flow 源码。门户存密码；ERP/SDMS 地址进 Binding.config；Engine `mock_env` 去掉。探测脚本硬编码不纳入本期。
19. **正式 Flow 演练/上线**：现行说明见 v4.1 SOP。扫描正式 **1.1.3**（Binding 已写 `searches`，无包内默认 PO）、提交正式 **1.1.4 dryRun** 已绑。选文件后必须点弹窗「确定」才识别。dryRun 对「提交审核」做 trial click，不真点。填交期/签章正式包未绑。
20. **v5.1**：Auth `/me` 管理员字段与下属接口已到。代码已接：`is_task_admin` 全放开；登录缓存下属。迁移 `a7e4b2c81d09` **已执行**（`g3b8e2a91c40` → `a7e4b2c81d09`，当前 head）。**需重启唯一 Task 4520**。
21. **v5.2 调度中心（Binding 任务）**：迁移与回填已完成。4520 已于 2026-08-25 09:48 换成 `JobScheduler`。正式演练回签 `*/5` 会到点开火，但无待回签候选时不建任务。

## 7. RPA Engine 数据库准备行动计划

### 7.1 目标与暂停点

为 RPA Engine 准备面向生产的 PostgreSQL schema 包，使其可以在评审后执行而无需重新设计。

当前暂停点：

- 不使用写入凭据连接 PostgreSQL。
- 不创建数据库、schema、角色、表、扩展或迁移记录。
- 不对任何数据库执行引导、DDL、验证 SQL 或种子 SQL。
- 准备工作在设计文档和待执行 SQL 文件具备评审条件时结束。

### 7.2 已确认的数据库基线

| 项目 | 决策 |
| --- | --- |
| 数据库引擎 | PostgreSQL |
| 数据库名称 | `nodeskclaw_rpa_engine` |
| Schema 名称 | `rpa_engine` |
| 隔离方式 | 与 `nodeskclaw-task` 使用独立数据库 |
| Flow 范围 | `GLOBAL` 平台 Flow 和 `TENANT` 组织私有 Flow |
| 角色 | owner/migrator、app、readonly |
| 主键 | UUID |
| 时间字段 | UTC `TIMESTAMPTZ` |
| 灵活元数据 | 按需使用 JSONB 和 `TEXT[]` |
| 迁移框架 | 当前使用 SQL 文件；Engine 仓库创建后使用 SQLAlchemy 2 和 Alembic |

tenantId、taskId、runId、portalAccountId、userId 和 WorkflowBindingId 等跨服务 ID 以外部字符串引用保存。RPA Engine 不得对 `nodeskclaw-task` 或 `nodeskclaw-backend` 数据库建立外键。

### 7.3 Engine 专属表

| 表 | 职责 |
| --- | --- |
| `rpa_flows` | 稳定的 Flow 标识、GLOBAL/TENANT 范围、所有权、状态和标签 |
| `rpa_flow_versions` | 不可变版本、manifest、入口、兼容性、包对象和校验和 |
| `rpa_flow_validation_runs` | 上传、手动及发布校验结果 |
| `rpa_flow_release_audits` | 仅追加的发布及状态变更审计轨迹 |
| `rpa_worker_instances` | Worker 注册、能力、并发、版本和心跳 |
| `rpa_execution_attempts` | Engine 技术执行尝试和 RunCommand 执行快照 |
| `rpa_callback_outbox` | 向 `nodeskclaw-task` 进行可靠、有序、幂等的回调 |
| `rpa_browser_profiles` | 未来 `PERSISTENT_PROFILE` 会话的受控元数据 |
| `rpa_cdp_endpoints` | 未来 `CDP_ATTACH` 端点的受控引用 |

RPA Engine 不负责 AutomationTask、WorkflowBinding、RpaRun、RunEvent、StepRun、Artifact 元数据、HumanAction、PortalAccount、凭据、用户、组织或权限。

### 7.4 准备交付物

计划记录位置：

```text
D:\AutoTask-Workspace\project-docs\designs\
  rpa-engine-database-design.md
  rpa-engine-database\
    000_bootstrap.sql
    001_initial_schema.sql
    verify_schema.sql
```

设计文档必须包含：

1. 数据所有权边界和 ER 图。
2. 完整字段字典、类型、默认值、可空性和注释。
3. 状态值及允许的状态转换。
4. 主键、唯一、部分、GIN、心跳、Outbox 轮询和保留策略索引。
5. 外键删除行为和外部引用规则。
6. 已发布 Flow Version 的不可变规则和仅追加审计规则。
7. GLOBAL 和 TENANT Flow 记录的租户隔离约束。
8. 凭据、CDP 端点、BrowserProfile 和 Artifact 的安全边界。
9. 数据保留默认值和未来清理任务。
10. 数据库字段到 Flow Registry 和 Worker API 的映射。

待执行 SQL 文件必须准备：

1. 数据库/schema/角色引导脚本，密码仅在执行时提供。
2. 表、检查约束、外键、索引、注释和触发器。
3. app 和 readonly 授权，且运行时不具备 DDL 权限。
4. 用于检查 schema 对象、约束、权限和查询计划的验证查询。
5. 不包含硬编码密码、Token、签名 URL 或环境专属密钥。

### 7.5 准备顺序

1. 冻结表所有权和公开 ID 映射。
2. 编制 ER 图和字段字典。
3. 定义状态转换和不可变规则。
4. 将引导和初始 schema SQL 编写为待执行文件。
5. 对命名、SQL 语法、约束、索引和安全性执行静态评审。
6. 对照 RPA Engine PRD、Flow 开发指南和 `nodeskclaw-task` OpenAPI 交叉检查 schema。
7. 将未解决问题记录在本文档中，不得在执行 DDL 时自行猜测。
8. 停止并等待明确的数据库执行授权。

### 7.6 未来执行门禁

仅在满足以下全部条件后，才能开始数据库操作：

1. `rpa-engine` 仓库目录已存在（原名 `nodeskclaw-rpa-engine`）。
2. 设计和 DDL 已通过评审并获批准。
3. PostgreSQL 版本、数据库主机、备份策略和密钥注入方式已确认。
4. 经授权的管理员在不提交凭据的前提下提供连接方式。
5. 回滚和备份方案已获批准。
6. 已明确授权创建数据库。

获得授权后，按以下顺序执行：临时验证数据库、约束和权限测试、备份确认、测试服务器引导、初始 schema、验证 SQL，最后建立 Engine Alembic 基线。该顺序属于未来工作，目前尚未获得授权。

### 7.7 准备检查清单

- [x] 已确认独立数据库决策。
- [x] 已确认 GLOBAL + TENANT Flow 隔离。
- [x] 已确认三角色权限模型。
- [x] 已确认 Engine/Task 数据所有权边界。
- [ ] ER 图已准备。
- [ ] 字段字典已准备。
- [ ] 状态转换矩阵已准备。
- [ ] 待执行引导 SQL 已准备。
- [ ] 待执行初始 schema SQL 已准备。
- [ ] 待执行验证 SQL 已准备。
- [ ] 跨文档评审已完成。
- [ ] 数据库执行已授权。

## 8. 每日开发日志

### 2026-08-26

- **扫描发票改成真正上传到 Task**：原先 Client 只把用户本机路径传给 `/invoice/paths`，换电脑 Worker 找不到文件，报 `invoice file input missing`。现改为 Main 读文件后 `multipart` 传到 `POST /statements/{billId}/invoice`，按对账单目录追加保存；扫描/提交都用服务器上的文件。详情打开看磁盘清单。Client 删除已上传文件会打 `DELETE /invoice-file`，服务器文件和扫描结果一起清掉，下次打开与列表一致。`tests/test_statement_service.py` + `test_statements_api.py` 41 passed。**需重启唯一 Task 4520**；Client 需重开（Main 有新 IPC）。
- **本地模拟提交审核成功**：演练 dryRun 不点 SRM，本地停在待上传发票。新增 `service/scripts/simulate_stmt_submit_review.py`，按日期+金额写成已对账 / 审批中 / 已完成。不写 SRM。默认预览，`--yes` 才写库。
- **模块管理员缓存仍是 false**：Auth 已是 `is_task_admin: true`，Task 缓存停在登录前。已改成你说的模型：AutoTask **登录成功后立刻** `POST /session/sync` 强制拉 Auth `/me` 写入缓存；平时 Task 请求走 10 分钟 TTL；新 token 的 `iat` 晚于缓存也会强制刷新。不再每个接口都打 `/me`。**需重启唯一 Task 4520**，并用 AutoTask 重新登录一次。
- **提交审核点「确定」超时**：正式演练 1.1.4 在扫描前就装 dryRun 写闸；正式站发票上传 URL 不含 `/upload` 等关键字，POST 被 abort，Playwright 点弹窗确定 4s 超时。重试时弹窗还在，列表 `.el-table` 15s 找不到。Engine 写闸改为放行 `multipart/form-data`；提交包 **1.1.5** 改为扫描完成后再装写闸。**需重启 Engine 4610**；1.1.5 发布后把正式 Binding 从 1.1.4 切过去。

### 2026-08-25

- **本地模拟填交期脚本**：正式演练无填交期 Binding。新增 `service/scripts/simulate_fill_delivery_dates.py`，按 PO 把订单行标成已写入并推进到待签章；不写 SRM、不派 RPA。默认预览，`--yes` 才写库。
- **浏览器有时能起来有时 Target crashed**：生成对账单/查询收货同一句 `Managed browser session could not be started`。17:47 查询曾成功（有截图和 xlsx）。原因是 Windows 同时 `--disable-gpu` 和 `--disable-software-rasterizer`，没有渲染后端就会间歇崩。已改为 `--use-angle=swiftshader`，启动失败最多再试 2 次（间隔 0.8s）。`test_runtime_browser.py` 15 passed。**请在 rpa-engine 窗口重启 4610**（若报 10048，先结束占用端口的旧进程）。
- **扫单浏览器同样起不来（17:07）**：与生成对账单同一失败。Client 两条 ERROR 是 Runtime 事件 + Task finish 各记一次。第一次 chrome→chromium 回退仍会在已崩溃的 Chrome 上 `new_context`。已改为 MANAGED 一律自带 Chromium、Windows `--disable-gpu`；会话缓存恢复失败则关浏览器再空上下文重开。`test_runtime_browser.py` 14 passed。**已重启 Engine 4610** 后请再点扫单。
- **对账单生成浏览器起不来**：Client 只显示 `Managed browser session could not be started`。本机复现：`channel=chrome/msedge` 会 `Target crashed`，自带 `chromium` 可启动。Engine 已改为 chrome 失败则回退 Chromium，并把 Playwright 原因带进事件；Task 租约默认 channel 改为 `chromium`。**需重启 Engine 4610 和 Task 4520** 后再点生成对账单。
- **正式演练回签 `*/5` 看起来没触发**：JobScheduler 已在 09:48 进程上运行。同门户扫单 `*/5` 曾于 10:15/10:20 真正建出任务（随后扫单 job 已停用）。回签 job `5517f5e8-…` 启用、cron=`*/5 * * * *`、Binding 为 `srm_check_reply_status`。客户订单 `POJS2607170008` 停在 `SDMS_CREATED`，候选=0，所以详情「执行任务」为空。已补开火日志与详情空列表说明。要把实例推进到待回签才会出现探测任务。
- **v5.1 权限接上 Auth 接口**：`/me.is_super_admin` / `is_task_admin`；`GET /api/v1/members/{id}/subordinate` 登录写入 `managed_user_ids`。模块管理员 AutoTask 内全放开。
- **v5.1 迁库（用户授权）**：已执行 `alembic upgrade head`（`g3b8e2a91c40` → `a7e4b2c81d09`）。`autotask_user_cache.is_task_admin` 已建。**未**重启 4520。
- **v5.1 归属人全员接口**：Auth OpenAPI 已有 `GET /api/v1/orgs/{org_id}/members`。模块管理员走这条；人名在 `user_name`、工号在 `username`，归属必须用 `user_id` 不能用成员 `id`。下拉展示「姓名（工号）」可搜索。
- **调度中心 v5.2 回填 Binding JSON**：用户授权维护 `config.schedule`。已执行 `backfill_scheduler_jobs.py --apply`，6 条 ENABLED 扫单/回签 Binding 写入默认 schedule，并插入 `scheduler_jobs`。扫单默认 `0 8 * * *` / 扫单；回签默认 `*/30 * * * *` / 回签轮询。门户：芯云test、国际test、芯云-正式演练（各扫单+回签）。库中无「天地伟业-国际-正式演练」扫单/回签 Binding。4520 未重启。
- **扫单排队卡死**：用户要求去掉「扫单：SRM 待签章订单」排队中任务。旧 4520 全局扫单循环仍在跑，约每 2 分钟插一条，堆积 268 条 QUEUED。已走 `cancel_task` 全部取消（任务+Run）。当前 inflight=0。未重启 4520，旧循环可能继续插新单。
- **未对账影子账单种子门户**：`seed_official_unchecked_statement.py` 默认门户从「天地伟业-国际-正式演练」改为「天地伟业-芯云-正式演练」（同 id `fbf07b4e-…`）。预览已找到门户；未加 `--yes`，未写库。同改 `run_official_stmt_payable_click.py`。

### 2026-08-24

- **调度中心 v5.2（扫单/回签轮询迁入 autotask_settings，cron 化热更新）**
  - PRD：`prd/AutoTask v5.2 调度中心.md`（定稿，含范围/语义/验收/待办）。
  - 痛点：扫单/回签轮询开关与时间参数在 `.env`，改一次要上服务器改文件并重启 Task。
  - Task：新增 `scheduler_config_service`（读写 `autotask_settings`，键 `scheduler.signPoll.*` / `scheduler.scan.*`；表缺值回退 `.env` 默认）。`SignPollScheduler` / `ScanScheduler` 常驻启动，每个 tick 查库读配置；`main.py` 不再按 `.env` 开关决定是否创建。新增 `GET/PUT /api/v1/autotask/settings/schedulers`（门户 admin/operator/超管可改，写审计）。`SUCCESSOR_JOB_*` 仍走 `.env` 未动。
  - 旧 `.env` 键（`SIGN_POLL_JOB_ENABLED` / `SIGN_POLL_INTERVAL_SECONDS` / `SCAN_JOB_ENABLED` / `SCAN_JOB_HOUR` / `SCAN_JOB_MINUTE`）降级为首次回退默认，**服务重启后即以表为准**。
  - **迭代 2（同日）：调度模型统一为 5 段 cron（分 时 日 月 周，本地时间）**——上一版"回签=间隔秒、扫单=每天时刻"表达不了"每半小时扫一次"这类需求。改动：
    - 新增 `cron_schedule.py`：自研解析器（`*`、`*/n`、`a-b`、`a-b/n`、`n/m`、逗号列表；dom/dow 双受限按 Vixie OR；7=周日；`previous_before` 支持补跑判断），无第三方依赖。
    - 配置键改为 `scheduler.signPoll.enabled/cron` + `scheduler.scan.enabled/cron`（上一版 interval/hour/minute 键从未落库，直接替换无迁移负担）。`.env` 回退自动折算：`SIGN_POLL_INTERVAL_SECONDS=1800` → `*/30 * * * *`，`SCAN_JOB_HOUR/MINUTE` → `M H * * *`。
    - 两调度器统一"30s tick + `_next_fire` 到点触发"：改 cron 只换计划不重启；到点后 10 分钟内重启会补触发一次（防停机错过当天扫单）；开关关闭清计划，重开即时按新计划走。
    - API/DTO：`GET/PUT` 返回并校验 cron（解析失败 422），响应含 `next_run_at`（下次触发预览）。
    - Client 调度中心卡片改「开关 + 预设下拉（每15/30分钟、每1/2小时、每天8点、每天8&14点、工作日8点）+ 自定义 cron 输入 + 下次触发展示」，两个调度器同一套交互。
    - 验证：Task pytest 214 passed（含 cron 解析/配置回退/调度器触发与热更 24 项）；Client tsc 无本次改动文件错误。
  - **迭代 3（同日）：Client 修复三连**——① `fromDTO` 读 snake_case 但 `mapItemResponse` 已转 camelCase，导致 `Cannot read properties of undefined (reading 'enabled')`，DTO 改 camelCase；② 调度中心两个 Select 缺 `SelectTrigger/SelectContent` 包裹层，整页崩溃（`SelectItem must be used within SelectContent`），已补齐；③ 加 custom 模式状态 + 前端 cron 解析器（`features/settings/cron.ts`，与后端同语义）实现「自定义」切换与下次触发实时预览。
  - **未决**：用户现场反馈自定义模式/实时预览仍不生效；已确认 4520 运行 cron 版代码（openapi `SignPollSettings` 含 `cron` 字段）、Vite 5173 分发新版模块。新增组件测试 `scheduler-settings.test.tsx` 7 例 4 过 3 挂，挂点为无障碍关联（combobox/按钮无可访问名，`Field` 的 Label 未 htmlFor 关联、保存按钮文案为「保存调度配置」与用例不符），下一步修 Label 关联与 aria 后复测。
  - 待办：重启唯一 Task 4520 后生效；首次 PUT 前表中无这些键，GET 返回 `.env` 折算值。
  - **迭代 4（同日，按现场口径收窄）**：调度配置是全局一份，页面读写不再跟登录组织走。非法/无下次触发的 cron 保存拒绝。Client 补 Label/aria。不按租户做多套调度。
  - **迭代 5（同日，准时触发）**：`*/5` 现场 15:04:27 提前跑（加载 cron 把 10 分钟内的上个到点当补跑）、15:10:22 延后跑（固定每 30 秒才醒）。已去掉补跑；到点前按剩余秒数睡醒。改完需重启 4520。
  - **迭代 6（同日，需求重定）**：全局两开关方案废弃。定时器挂 Binding id；`config.schedule` 仅首次插入默认 cron；调度中心列表/详情维护变量并看任务日志；用户不新建。PRD 已整篇替换；计划 `.cursor/plans/v5.2_调度中心_binding任务.plan.md`。代码未改；DDL 未执行。
  - **迭代 7（同日，按 Binding 任务方案开发中）**：落地 `scheduler_jobs` 模型与 Alembic `g3b8e2a91c40`。保存 Binding 时按 `config.schedule` 首次插入 job；再改 JSON 不覆盖 cron；停用 Binding 必停 job，重新启用 Binding 不自动打开 job。`JobScheduler` 替换全局扫单/回签循环，按门户开火。REST `GET/PATCH /scheduler-jobs` 与任务日志。Client 管理中心「调度中心」列表/详情，无新建按钮；设置页全局调度卡片已撤。回填脚本 `scripts/backfill_scheduler_jobs.py` 默认 dry-run。
  - **迭代 8（同日，用户授权迁库）**：已执行 `alembic upgrade head`（`f1a9c3e74b20` → `g3b8e2a91c40`）。`scheduler_jobs` 已建（含 `uq_scheduler_jobs_binding_id`）。**未** `--apply` 回填；**未**重启 4520。
- **v5.1 权限代码（管人接口后补）**
  - Task：门户加 `owner_user_id`；登录缓存 `managed_user_ids`（Auth `/me` 尚未返回时当空）。
  - 列表/详情按归属人过滤：admin/超管全开；其他人只看自己名下。停用 grants 鉴权。
  - 任务/对账单/人工操作/看板补齐同一套可见性；改归属人由 Task 校验。
  - 归属人下拉：普通人只有自己；admin 走组织成员接口。
  - 归档工号改走门户归属人，去掉写死工号。
  - Client：门户列表/详情/编辑展示归属人。
  - 迁移 `f1a9c3e74b20`：**用户授权后已执行** `alembic upgrade head`（`e2b7c14a3d05` → `f1a9c3e74b20`，当前 head）。已有门户回填 `owner_user_id = created_by`；`autotask_user_cache` 增加 `managed_user_ids`。未重启 Task。
  - 验证：Task pytest 60 passed（permission / portal / user_sync / process_instances）。

### 2026-08-21

- **v5.1 权限定稿（文档）**
  - 门户只认 `owner_user_id`；能看 = 归属人是自己或自己管的人。`portal_org_role=admin` 全放开。停用 `portal_access_grants` 鉴权。任务/订单/对账单同一过滤。
  - Auth `/me` 需后补「管理的人」；登录写入 Task 缓存。未补前非 admin 只看自己名下。
  - 加列须授权才迁库。未改代码。

- **扫单 Binding `searches` 落地（1.1.3）**
  - 问题：SOP 写 Binding 控样例单号，实际 1.1.2 把 `POJS2607170008` 写死在 `flow.py`；正式 Binding 也从未写入 `searches`。Task 租约原先只传 `portalUrl` / `browserSession` / `dryRun`。
  - Task：租约 `config.searches`；同时写入任务 `input.searches`（兼容尚未重启的 Engine）。
  - Engine：`RunConfig` / `_safe_config` 透传 `searches`。
  - 正式扫单 **1.1.3** Registry `73eb83a7-…`，checksum `sha256:1344dc32…`。Binding `2f3a6e10-…` 已写 `searches`：待签章 + `POJS2607170008`/`treatAsPending`。演示仍 1.0.2。
  - 签章 `temp_e2e_backfill_dates` 只给演示门户 URL（`192.168.102.247`）。
  - 计划：`.cursor/plans/binding_searches_对齐_2026-08-21.plan.md`。**需重启唯一 Task 4520**。建议重启 Engine 4610。Client 打开正式演练扫单 Binding 应能看到 `searches`；换第二条 `poNo` 再扫才会换单。
  - 未做：正式填交期/签章包（演示 1.0.3 不读 dryRun，禁止绑正式站）。

- **v4.1 正式演练与上线 SOP**
  - 新文档 `project-docs/prd/AutoTask v4.1 天地伟业正式演练与上线SOP.md`：演练/上线 Binding 怎么配；两条 SOP 每步谁点、SRM 会不会改；哪些现在能演练、哪些要人核对、哪些等待签章或关 dryRun。
  - v4.0 与「演练与上线同一份包」改为指向 v4.1。对账单扫描+提交演练已跑通；填交期/签章仍等正式站待签章；真生成/真提交仍等关闸。

- **扫描发票必须点弹窗「确定」才会识别（1.1.2 / 提交 1.1.4）**
  - 旧逻辑：`set_input_files` 后「确定」点不到就 `pass`，接着读发票号；读失败重试又回到列表。
  - 现改为必等可见、未禁用、必点「确定」，弹窗关掉再读发票号/总额。点不到直接失败，不再默默跳过。
  - 扫描 **1.1.2** Registry `806b0a20-…`，checksum `sha256:6d066355…`。Binding `b36b5628-…`。提交 **1.1.4** Registry `92226c2c-…`，checksum `sha256:4dc9a393…`。Binding `e64d3354-…`，`dryRun: true`。演示未改。

- **dryRun 提交审核改为 trial click（1.1.3），脚本已在正式门户验证「能看就能点」**
  - 看得见不等于能点。Playwright `click(trial=True)` 检查可见、可用、稳定、中心点不被挡住，但不真点。再加 `elementFromPoint` 命中检测。
  - Engine：`runtime/actionability.py` 的 `inspect_clickable` / `assert_clickable`。
  - 正式门户探针（未点提交）：`2026-04-01` / `5768205.32` 收货应付真点 ok；「扫描发票信息」「提交审核」均 `trialOk=true`、`hitsSelf=true`、未禁用。
  - 提交包 **1.1.3** Registry `2b9e25b7-…`，checksum `sha256:58f9b894…`。Binding `e64d3354-…` 1.1.2→1.1.3，`dryRun: true`。演示仍 1.0.7。
  - 生成对账单 1.1.0 仍只查可见+未禁用，尚未 trial click。

- **正式门户脚本已点通「收货应付」（1.1.1 JS，不经 Client）**
  - 先前包内 pytest 只扫源码字符串，不能证明按钮能点。补了正式门户探针：`service/scripts/run_official_stmt_payable_click.py` → Engine `scripts/probe_official_stmt_payable_click.py`。只打开收货应付，不点提交审核。
  - 实测：`2026-04-01` / `5768205.32` 匹配 `rowIndex=0`；冻结列 `fixed-right` 的 `body-wrapper` 行数 0、`fixed-body-wrapper` 行数 1；`CLICK_PAYABLE_JS` 返回 `ok`；扫描发票/提交审核按钮可见。结果 `rpa-engine/runtime-cache/tiandy-stmt-payable-click.json`。
  - 包内补了冻结列表选择器回归：`rpa-flows/rpa_flow_srm_stmt_upload_invoice/1.1.1/tests/test_payable_click_js.py`。

- **扫描点「收货应付」失败：冻结列可见按钮（1.1.1）**
  - 1.1.0 能按日期+金额匹配（入参 `2026-04-01` / `5768205.32`），但点不到冻结操作列里的「收货应付」。
  - 扫描 **1.1.1** Registry `acdc426b-…`。提交 **1.1.2** 同样改点击，Registry `d25d744d-…`，`dryRun: true`。匹配成功会把日期/金额写进步骤日志。演示包未改。请再点扫描发票。
  - 点「提交审核」= 客服已核对页面上的发票号/总额。第二次扫描必须与页面一致，否则失败、不点门户提交。
  - Client：扫描发票 + 提交审核。提交在有发票字段且文件未换时才可点。
  - Task：`upload_invoice` 真排队扫描；成功回写发票号/总额，仍未对账。`submit_review` 带 `expectedInvoiceNo` / `expectedInvoiceAmount`。
  - 正式扫描包 **1.1.0** Registry `0fd304e3-…`，checksum `sha256:af9d9911…`。Binding `b36b5628-…` 新插入，无 dryRun。
  - 正式提交包 **1.1.1** Registry `87138a09-…`，checksum `sha256:aa273235…`。Binding `e64d3354-…` 1.1.0→1.1.1，`dryRun: true`。
  - 演示扫描仍 1.0.6、提交仍 1.0.7（演示提交包尚未加二次比对）。
  - 需求已写入 v3.0 #26–#28、v3.01 S7、v4.0 §4.2 / §12。**需重启唯一 Task 4520**。演练：详情先扫描，核对页面后再点提交；门户提交不会点下去。

- **正式提交审核 1.1.0：扫描真做，dryRun 不点门户提交**
  - 生成演练成功后门户没有对账单。待生成草稿不得改成未对账。下一节点用门户已有未对账当替身。
  - 种子：`service/scripts/seed_official_unchecked_statement.py`（`--check-date` + `--check-amount` 必须与门户那行一致）。阶段待上传发票。Client「提交审核」必须能点。
  - 正式包 1.1.0：对账列表 `#/reconciliation/reconciliationStatement` 按日期+金额找行 → 收货应付 → 真扫描 → 等到「提交审核」可见可点，截图后不点。正式不绑单独上传包。演示提交仍 1.0.7。
  - Task `on_submit_finished` 见 `committed: false` 保持未对账 / 未上传，不传发票到 SDMS。
  - Registry `d96d7674-…`，checksum `sha256:d44d3153…`。Binding `e64d3354-…` 新插入，`dryRun: true`。演示提交仍 1.0.7。
  - 需求修订已写入 `prd/AutoTask v4.0 天地伟业正式演练.md` §4.2 / §5.4 / §12 与 `prd/正式门户 Flow 演练与上线.md` §6。
  - **需重启唯一 Task 4520**。种子写库后，详情选发票再点提交审核。不要点门户提交。

- **正式生成对账单 1.1.0：真找按钮，dryRun 不 click**
  - 演练若只查收货不跑生成，上线才会第一次碰「生成对账单」，选择器问题会漏掉。
  - 正式包 1.1.0：同一套日期面板 + 未提交 + 勾选行，等到「生成对账单」可见且可点，截图后不点。缺按钮或禁用算失败。
  - Binding `dryRun: true` 只挂正式演练。演示生成仍 1.0.7。Task `on_generate_finished` 见 `committed: false` 保持待生成草稿，不改未对账。
  - Registry `1f83e5e3-…`，checksum `sha256:acf471d2…`。**需重启唯一 Task 4520** 后，填单页勾选三行再点生成。

- **正式收货查询 1.1.3：开始必须是 00:00:00**
  - 1.1.2 点日历后再 click 时间框，时间面板把输入下标打乱，起止都写成 `23:59:59`，当天没有数据。
  - 1.1.3：日历只选日期；开始写 `YYYY-MM-DD 00:00:00`，结束写 `YYYY-MM-DD 23:59:59`。不 click 时间框。确定后回读，不对就失败。
  - Registry `64790d58-…`，checksum `sha256:df8bb497…`。Binding `37628f8c-…` 1.1.2→1.1.3。演示收货仍 1.0.4。
  - 单测 24 通过。请用 `2026-08-01`～`2026-08-01` 再搜一次。

- **正式收货查询 1.1.2：日期面板与正式站一致，筛未提交后导出 Excel**
  - Client 仍只传 `YYYY-MM-DD`。Flow 点开「入库确认时间」范围面板，日历点起止日，时间保持 `00:00:00` / `23:59:59`，再点面板「确定」。
  - 查询前在表单选对账状态=未提交，再点查询；结果走「导出」xlsx，解析给填单页并落 Artifact。不再翻页刮 HTML。
  - Registry `c3d2e6cf-…`，checksum `sha256:4d403c85…`。Binding `37628f8c-…` 1.1.1→1.1.2。演示收货仍 1.0.4。
  - 单测 21 通过。请在正式演练填单页选 `2026-08-01`～`2026-08-01` 再搜一次（预期约 3 行未提交）。不要点生成对账单。

### 2026-08-20

- **正式回签/下合同：列表筛已回签+单号，详情不再读状态（回签 1.1.4、下合同 1.3.2）**
  - 原先在详情等 `.el-tag` 找「已回签」是演示站写法。正式站「已回签」是列表筛选项；筛到再进详情，进了就是已回签。
  - 回签探测 1.1.4：查询条件=回复状态已回签+订单编号；有行则进详情并输出已回签；没有行则输出待回签、不进详情。Registry `3357b19d-…`。Binding `fef4ea03-…` 1.1.3→1.1.4。
  - 下合同 1.3.2：同样先筛已回签+单号；能进详情后只点「查看签章」下载，不再读状态。Registry `c2f9a81b-…`。Binding `ffa96cad-…` 1.3.0→1.3.2。演示回签仍 1.0.1、下合同仍 1.2.5。
  - 实例已在已回签的，请点「手动触发签章合同下载」或重试失败的下合同任务。

- **正式回签探测不再等 `.el-tag`（1.1.3 已发布并只绑正式演练）**
  - 1.1.2 已能打开详情，但 `reply_status` 仍 `wait_for` `.el-tag:visible`。正式已回签详情没有演示站那种 Element UI tag，10 秒超时 → `ORDER_REPLY_STATUS_UNAVAILABLE`。
  - 1.1.3：详情可见「查看签章」即视为已回签；否则读「回复状态」旁的 `已回签/待回签/待签章`。不再等待 `.el-tag`。Registry `6fad94a0-…`，checksum `sha256:b2daf4b3…`。Binding `fef4ea03-…` 1.1.2→1.1.3。演示回签仍 1.0.1。
  - 单测 11 通过。请再点「立即回签轮询」；认出已回签后会自动排下合同 1.3.0。

- **正式回签探测详情点击与建单对齐（1.1.2 已发布并只绑正式演练）**
  - 1.1.1 点隐藏「详情」后空等 `.el-drawer / .el-tag`，列表页没有抽屉所以超时。建单 1.2.15 已改可见点击，回签探测当时没跟上。
  - 1.1.2 共用同一套冻结列可见「详情」；进详情认「查看签章」或「导出订单明细」。Registry `95f0b13d-…`。Binding `fef4ea03-…` 1.1.1→1.1.2。演示回签仍 1.0.1。
  - 单测 10 通过。请再点「立即回签轮询」。

- **正式下合同认「查看签章」（1.3.0 已发布并只绑正式演练）**
  - 正式详情已回签单有「查看签章」，即下载双方签章合同。演示包 `data-rpa` 不能绑正式站。
  - 正式包 1.3.0：OCR 登录、`#/order/list`、可见「详情」、点「查看签章」下载后真传到测试 SDMS。无 `dryRun`。Registry `1abe0ae0-…`，checksum `sha256:07e87504…`。Binding `ffa96cad-…` 新建。演示下合同仍 1.2.5。
  - 单测 12 通过。`POJS2607170008` 已在待回签。请在 Client 点「立即回签轮询」；认出已回签后会自动排下合同。
  - 轮询上传 SDMS 的 `username`：优先实例创建人工号，没有则固定 `SMC-SZ-HR15563`。该字段不敏感，只要非空。**需重启唯一 Task 4520**。

- **正式演练跳过填交期/签章，实例改到待回签**
  - `POJS2607170008` / `5face9c4-…`：正式站已回签，无交期输入、保存、签章。不编造填写成功。
  - 实例 `SDMS_CREATED` → `SIGN_REQUESTED`（待回签）。回签探测 Binding 已是正式包 1.1.1。
  - Task 默认未开 30 分钟调度。请在 Client 客户订单列表点「立即回签轮询」。
  - 下合同正式包 1.3.0 已绑；轮询认出已回签后会自动排下载上传。

- **正式建单详情没点开（1.2.15 已发布并只绑正式演练）**
  - `failure.png` 仍是订单列表：`POJS2607170008` 已查出，绿色「详情」在冻结操作列。列表没有「导出订单明细」，所以 1.2.14 空等该按钮是因为根本没进详情。
  - 原因：Element UI 冻结列后，主表体「详情」是隐藏副本。`force=True` 点到它会报成功，页面不跳转。
  - 1.2.15 改为按订单号对齐行号，再点 `.el-table__fixed-right` 里可见的「详情」，不用 force。Registry `a6e63298-…`，checksum `sha256:8539bc65…`。Binding `30a451be-…` 1.2.14→1.2.15。演示建单仍 1.2.11。
  - 单测 58 通过。请在 Client 对失败实例 `5face9c4-…` / `POJS2607170008` 点重试。

- **正式建单附件按钮是「导出订单明细」（1.2.14 已发布并只绑正式演练）**
  - 详情已打开后仍等 `下载订单` 15 秒失败。正式站文案是「导出订单明细」，演示站才是「下载订单」。
  - 1.2.14 选择器已改；打开详情确认和下载都认这四个字。Registry `fb5742a1-…`。Binding `30a451be-…` 1.2.13→1.2.14。演示建单仍 1.2.11。
  - `POJS2607170008` 已自动重试。单测 58 通过。

- **正式建单已登录却还在等验证码（Engine 已换新进程）**
  - 会话缓存进了正式站首页（顶栏有「订单」），登录仍 `wait_for` 验证码图 1 秒超时，报 `SRM_LOGIN_PAGE_UNAVAILABLE`。
  - 已登录判断改为：验证码不在时，认 `#/dashboard`/`#/order` 或顶栏「订单」「主页」「个人中心」。不再对已登录页死等验证码。
  - 单测：official login 16、browser 相关一并 16 通过。Engine 已重启。后续建单登录事件为 `reusedSession`。

- **正式建单 1.2.13 已发布并只绑正式演练**
  - 原先卡在「建单中」无子任务、明细为空：正式门户没有 `srm_prepare_erp_order` Binding，扫单 `allow_missing_prepare_binding` 吞掉缺绑定。
  - 正式包 1.2.13：OCR 登录、无 `data-rpa`、点该行「详情」并用「下载订单」确认详情。Registry `fc22a74a-…`。Binding `30a451be-…`。演示芯云test / 国际test 建单仍 1.2.11。
  - `POJS2607170008` 已重试；登录已过，详情点击在 1.2.12 上会空等到 `RUNTIME_TIMEOUT`（列表已搜到该单）。请看本次 1.2.13 重试。

- **正式门户 Flow：演练与上线同一份包（设计已确认，已写 PRD）**
  - 演示/正式因页面不同继续拆包。演练/上线不拆包：Flow 只实现上线操作；样例单号、`treatAsPending`、`dryRun` 进 Binding，上线改配置不换包。
  - 扫单：Binding `searches` 先待签章导出，演练再加一条订单编号；生产只留待签章。不要 Task 空列表造单，不要 `flow.py` 里 `if drill`。
  - 文档：`project-docs/prd/正式门户 Flow 演练与上线.md`。扫单 1.1.2 样例单号仍在源码默认值，尚未收到 Binding。

- **正式扫单改为查询后导出 Excel（1.1.2 已发布并只绑正式演练，4520 已换新进程）**
  - 原先：翻页读页面表格，再在内存里筛「待签章」；空列表时 Task 直接造 `POJS2607170008`。
  - 现流程：回复状态选待签章（不加其它条件）→ 查询 → 导出 Excel → 用 Excel 建客户订单。无待签章时重置，按订单编号 `POJS2607170008` 查询再导出，把该单当成待签章扫入。不改 SRM 状态。
  - Registry 扫单 `09293dee-…` checksum `sha256:2488edca…`。Binding `2f3a6e10-…` 1.1.1→1.1.2。演示芯云test / 国际test 扫单仍 1.0.2。
  - 单测：Flow 16、Task process-instances 33 通过。
  - **待验收**：Client 选正式演练再扫一次。应看到导出制品；无待签章时应出现 `POJS2607170008`。正式演练尚未绑定建 SDMS，实例会停在「建 SDMS」。

- **正式站无待签章时当成 POJS2607170008 走 SOP（已由 1.1.2 导出回退替代，不再在 Task 空列表造单）**
  - 需求：正式演练扫单成功但 `orders=[]` 时，把 `POJS2607170008` 当成待签章，创建客户订单并走后续节点。
  - 处理：已改到扫单 Flow 改搜索条件后导出，不再由 Task 合成订单。

- **托管浏览器起不来 BROWSER_LAUNCH_FAILED（已修，Engine 已换新进程）**
  - 原因：Agent 拉起 Engine 时带了不存在的 `PLAYWRIGHT_BROWSERS_PATH`（TEMP 下 sandbox 缓存），Chromium 找不到可执行文件。独立探测脚本会改回本机 `%LOCALAPPDATA%\ms-playwright`，所以探测能登录、Worker 不能。
  - 处理：启动时若该路径不是目录则丢弃，改用本机 ms-playwright；启动失败打完整异常。Engine 已重启。可再扫一次。

- **正式站登录没勾「我已阅读并同意」（已修，Engine 已换新进程）**
  - 失败截图协议勾选为空。Playwright 报 `label:has-text('用户注册协议') input[type=checkbox]` 的 `is_checked` 空等 30 秒：协议文字在 checkbox **旁边**（`.userAgree` 里兄弟 span），不在 label 内，选择器匹配不到；异常被吞掉，登录未勾协议。
  - 登录改为点 `.userAgree .el-checkbox__inner`。独立探测已进正式站 `#/dashboard`（第 2 次验证码通过）。Engine 已重启加载该逻辑。请再扫一次。

- **运行队列卡死（已解开，Task 4520 已换新进程）**
  - 现象：运行监控三条「排队中」不动。队头是已禁用芯云test 的回签探测，旧 4520（10:34 起）领取仍返回 400「门户未启用」，Worker 整池卡住，正式演练扫单排在后面领不到。
  - 处理：停 PID 59300 后用当前代码重启 4520。领取改为跳过并取消禁用门户任务（连同 Run）；回签轮询只选 ENABLED 门户，启动时候选 0、未再给 test 建探测。芯云test 那条被领取循环取消；国际test 任务已取消但 Run 仍 QUEUED 的孤儿已改 CANCELLED。
  - 正式演练扫单 `5c1642ce-…` 已领到并执行，登录验证码三次未识别，以 `CAPTCHA_OCR_FAILED` 结束（队列本身已通）。刷新运行监控后不应再看到那三条卡死排队。

- **正式门户只读 Flow 切 OCR 1.1.1（已发布并只绑正式演练）**
  - 演示 OCR + 会话缓存已验收；芯云test / 国际test 由用户禁用。正式门户 `天地伟业-国际-正式演练`（`https://supplier.tiandy.com`）保持 ENABLED。
  - 三只读包 1.1.1：扫单 `130ee81f-…`、回签 `2bf6d600-…`、收货 `5061d2a4-…`，均为 `PUBLISHED`。登录走 `login_official_srm`（ddddocr，最多 3 次，失败可重试，不停待人工）。无 `data-rpa`。
  - Binding 只更新正式演练三条：扫单/回签/收货 **1.1.0 → 1.1.1**。禁用的 test 门户绑定仍是 1.0.x，未改。未绑建单/填交期/签章/对账写步骤（正式 SRM 不写）。
  - 单测 12+10+10 通过。取消禁用门户及 phase5 mock 的排队任务 3 条，避免旧 4520 再被队头 400 卡住。
  - **待验收**：Client 选正式演练手动扫单（待签章空列表也算成功）；收货查未提交行；回签探测可用样例 `POJS2607170008`。正式站会话缓存与演示站按 URL 隔离。

- **门户登录会话缓存（Engine，已验收）**
  - 目的：SOP 连续任务不再每个都 OCR 登录。浏览器进程仍 `CLOSE_ON_FINISH`，只把 Playwright `storage_state`（cookies）按「规范化门户 URL + 登录账号」缓存在 `runtime-cache/sessions/`。
  - 同 URL 不同登录（芯云 vs 国际）分开；演示 IP 与正式 `supplier.tiandy.com` 因 URL 不同自然隔离。同一 `(url, login)` 全程文件锁，禁止并发写。
  - 登录失败 `SRM_LOGIN_FAILED` 删除该缓存；验证码失败不覆盖已有文件。密码不进键、不进 `meta.json`。
  - 登录等待改为 success/error 竞速 `wait_for`，减少「其实已登录却整段 Flow 重试」。
  - 单测：session cache / browser / runtime / config 相关 65 项通过。计划：`.cursor/plans/engine_门户会话缓存_2026-08-20.plan.md`。
  - **已验收**：正确重启 Engine 后，芯云test 扫单/建单/填交期连续任务均为 `reusedSession`，扫单约 12.5 秒（此前约 75 秒）。必须先停旧 4610 再起新进程，否则端口占用会导致新代码起不来。

- **禁用国际test 后排队卡住（已解开）**
  - 原因：领取按排队时间取队头。国际test 禁用后仍有回签探测排在最前，Worker 领取返回「门户未启用」400，整条队列（含芯云test）都不走。
  - 处理：取消国际test 那条排队任务；芯云test 回签/填交期/传合同已继续。`lease_task` 改为跳过并取消不可领取任务，避免再堵全队列（需重启 4520 才加载）。国际test 保持禁用。

- **演示门户客户订单+对账单登录全改 OCR（已发布并只绑 test）**
  - 范围：芯云test / 国际test 上所有 ENABLED、需要登录的 Flow。扫单 1.0.2 已是 OCR，其余从当前绑定包升版：回签 1.0.1、填交期 1.0.3、建单 1.2.11、签章 1.0.3、传合同 1.2.5、查收货 1.0.4、生成对账单 1.0.7、上传发票 1.0.6、提交审核 1.0.7。`srm_fetch_po` 仍 DISABLED 未动。
  - 登录一律 `login_official_srm`（本机 ddddocr，最多 3 次，失败可重试，不停待人工）。对账单包从 Registry 下了当时绑定版再改登录，避免丢掉 1.0.3/1.0.5/1.0.6 的业务修补。
  - Binding 只切 URL 含 `192.168.102.247` 的门户。正式演练扫单/回签/收货仍是 **1.1.0**。
  - 单测 118 项通过。无需重启 4520；Engine 需继续用 `rpa-engine` 的 `.venv`（已装 ddddocr）。
  - **待用户验收**：芯云test 或国际test 跑完整客户订单和对账单。

- **天地伟业-芯云test 归属转到张站（已写库）**
  - 原因：门户列表按 `portal_access_grants` 过滤，芯云test 原先只有苏宇威的 USER 授权，张站只能看到自己建的国际test。
  - 处理：`created_by` 苏宇威 → 张站；补张站 USER 授权（与创建人同权）；苏宇威原授权保留。脚本 `service/scripts/transfer_portal_owner.py`。
  - 效果：张站刷新 Client 后应能看到并操作芯云test。无需重启 4520。

- **v4.0 阶段 1：正式门户只读 Flow 1.1.0 已发布并只绑正式演练**
  - 计划：`.cursor/plans/v4.0_正式门户_只读flow_阶段1_2026-08-20.plan.md`。
  - 三包均为正式站专用（无 `data-rpa`）：扫单 `rpa_flow_srm_scan_pending_orders/1.1.0`（`#/order/list`）、回签探测 `rpa_flow_srm_check_reply_status/1.1.0`、收货查询 `rpa_flow_srm_stmt_query_receipts/1.1.0`（`#/order/receivingList`）。未知验证码仍 `HUMAN_VERIFICATION_REQUIRED`。
  - Registry：扫单 `24d05324-…`、回签 `8d24354a-…`、收货 `2a673d87-…`，均为 `PUBLISHED`，`validate-binding valid=true`。
  - Binding 只插「天地伟业-国际-正式演练」（`fbf07b4e-…`，`portalUrl=https://supplier.tiandy.com`，无 `dryRun`）。演示芯云test / 国际test 扫单 1.0.1、回签 1.0.0、收货 1.0.3 **未改**。
  - 单测：扫单 11、回签 10、收货 10，均通过。未提交 Git。
  - **待用户验收**：Client 选该门户手动扫单；收货查未提交行；回签探测 `POJS2607170008`。阶段 2/3（建单、下合同、写闸）未做。

- **建门户门槛改读 `portal_org_role`（已上线，治本）**
  - **背景**：客服反映建不了门户。排查发现建门户门槛 `require_portal_manage_access` 只读 `org_role`（组织维度角色），而后端 `/me` 对客服账号返回 `org_role=null`（兜底成 `role="user"`）、`is_super_admin=false`，但 `portal_org_role=operator/admin`（门户维度角色）——这才是门户维护该看的角色，但门槛没读它。7-8 月能建是因为后端那时返回够格的 `org_role`/`super_admin`，后端改 `/me` 后 bug 暴露。
  - **设计梳理**：本意三层权限——①组织层 `org_role`、②门户角色层 `portal_org_role`、③门户授权层 `portal_access_grants`。第②层一直没接通（门槛没读它，DEPARTMENT 类型授权又没数据），形同虚设。本次只接通"建/管门户门槛"这一处。
  - **改法**：`security.require_portal_manage_access` 改为 `portal_org_role ∈ {admin,operator}` 放行；保留 `org_role ∈ {admin,operator}` 与 `is_super_admin` 兜底，不破坏组织管理员/超管路径。
  - **效果**：`portal_org_role=operator/admin` 的客服能建/管门户，不用当组织管理员。`member` 仍不能建（member 不是门户管理角色）。当前缓存：张站=operator✅、王冬辉=admin✅、苏宇威=member❌（需后端把苏宇威 portal_org_role 改成 operator/admin 才能建）。
  - **未做（留后续权限优化）**：①前端新建按钮改为按 `/me` 角色预判显示（现在默认显示、撞 403 才藏且不恢复，UX 差）；②配 DEPARTMENT 类型 `portal_access_grants`，让 operator/admin 角色对门户有细粒度权限；③门户加可变 `owner_user_id` 字段 + UI + 迁移，归档工号从门户归属人取（删 `_FALLBACK_ARCHIVE_SDMS_USERNAME`）。
  - 单测：新增 `test_require_portal_manage_access_allows_portal_org_role`、`test_require_portal_manage_access_rejects_member` 补 member 用例；15 项通过。Service 已重启加载改动。

### 2026-08-19

- **门户唯一性改为「门户名称」+ 编号放开编辑（已上线）**
  - 原唯一性 `(租户+实体类型+门户地址+登录账号)` → 改为只校验 `(租户+门户名称)`。同一客户可建多个门户（如 `天地伟业-国际` / `天地伟业-国际test`），地址、登录账号、客户编号都允许重复，只要门户名称不重复。
  - 门户「客户/供应商编号」(`erpEntityCode`) 编辑模式下放开可改（原来 disabled）。
  - 代码：`service/app/services/portal_account_service.py` `_check_portal_uniqueness` 改签名只收 `portal_name`；`app/.../portal-account-form-dialog.tsx` 去掉 `disabled`。
  - 迁移 `e2b7c14a3d05`：drop 旧索引 `uq_portal_accounts_tenant_entity_url_login`（库里本就不存在，用 `if_exists`）、create `uq_portal_accounts_tenant_portal_name (tenant_id, portal_name) WHERE deleted_at IS NULL`。**已执行 `alembic upgrade head`**，新索引已生效。
  - 单测：`test_portal_accounts.py` 唯一性冲突用例改按 `portal_name`；`portal-account-form-dialog.test.tsx` 通过。

- **天地伟业-国际test 门户绑定已克隆（已上线）**
  - 新门户 `天地伟业-国际test`（id `91b38832-…`，业务实体 `芯智国际有限公司` / `ou=101`）从 `天地伟业-芯云test` 克隆 11 条 WorkflowBinding，复用同一批流程模板与 Flow 版本（建单 1.2.9、传合同 1.2.3、对账 1.0.x 等）。dispatch 时各带各的 `businessEntity`/`ou`，互不干扰。

- **定时扫单改为「按扫单绑定扇出」（已上线）**
  - **背景**：`ScanScheduler` 原来查「所有启用门户」逐个建扫单任务。扫单 Flow `srm_scan_pending_orders` 是天地伟业定制，未来加别的客户门户时会对没扫单绑定的门户也调一遍、靠 `_find_binding` 报错兜底，每天刷错误日志、语义不对。
  - **改法**：`service/app/services/scan_scheduler.py` 的门户查询从「所有 ENABLED 门户」改为 join `WorkflowBinding` + `WorkflowTemplate`，限定 `template_code = srm_scan_pending_orders` 且 binding `ENABLED`。即只扫「有启用扫单绑定的门户」。
  - **效果**：天地伟业两个门户（有扫单绑定）→ 定时各扫各；未来无扫单绑定的门户 → 不被查到、零噪音。新客户要纳入定时扫单，给它建一条扫单绑定即可，无需改代码。
  - 单测：`test_process_instances.py` 新增 `test_scan_scheduler_only_targets_portals_with_enabled_scan_binding`；全文件 29 项通过。

- **建单 Flow 拆分演示/正式门户专用包（已上线 1.2.10）**
  - **原则**：一个 Flow 版本只服务一种门户环境，不再用「双选择器」让一个版本同时跑演示和正式。**门户环境归属写在各 Flow 的 README 顶部**（演示/正式 + 门户地址），不用 manifest 加字段。同一门户环境内始终用最新版本；**绑定时按门户环境选对应版本的 Flow**。
  - **背景 bug**：1.2.9 的 `order_page`/`lines_table` 用逗号 OR（`.el-table:visible, [data-rpa='order-list-page']`），演示门户里同时匹配「容器 + 容器内表格」两个元素 → Playwright strict mode 报错 → 建单 Flow 在演示门户挂掉。
  - **改法**：新建 **1.2.10（演示门户专用包）**，`selectors.json` 全部改为纯 `data-rpa`（演示门户有这些标记），去掉所有正式门户的文本/`.el-table` 兜底。README 顶部标注「适用门户：演示门户」。单测 58 项通过。扫单 Flow `1.0.1` README 同步标注演示门户。
  - **发布+切绑定**：1.2.10 已发布 Registry（versionId `81c94b03-…`，checksum `14947b6c…`，validate-binding 通过）；两个天地伟业门户的 `srm_prepare_erp_order` 绑定从 1.2.9 切到 1.2.10。
  - **正式门户**：后续从正式站 `https://supplier.tiandy.com` 探测选择器，单独出一个正式门户专用版本（README 标「适用门户：正式门户」），不复用 1.2.10 的 `data-rpa` 选择器。
  - **客户端**：`processes-list.tsx` 手动扫单循环改为按门户容错（有扫单绑定的扫、没绑定的报失败但不中断），避免没扫单绑定的示例门户把整批扫单拦住。

- **客户订单详情「交易主体」改读门户业务实体（已上线）**
  - **问题**：流程实例详情/交期页的「交易主体」原读 `summary.supplierName`（来自 Flow 输出的 Excel 供应商字段）。演示门户里国际和芯云共用地址 `192.168.102.247:3000`，Excel 供应商字段是芯云，导致「天地伟业-国际test」的订单也显示成「深圳市芯云信息科技有限公司」。
  - **改法**：「交易主体」改为读门户账号维护的 `businessEntity`（我方公司）。新增 `usePortalBusinessEntityMap` / `resolvePortalBusinessEntity`（`app/src/features/processes/use-portal-name-map.ts`），`process-detail.tsx` 和 `process-dates.tsx` 两处「交易主体」改用门户 businessEntity，不再读 `summary.supplierName`。
  - **效果**：国际test 显示「芯智国际有限公司」、芯云test 显示「深圳市芯云信息科技有限公司」，各走各的门户维护值，不受共用地址的 Excel 数据影响。`summary.supplierName` 仍保留（审计用），不再用于展示。
  - 单测：`process-instances.test.tsx` mock 门户补 `businessEntity`，断言「交易主体」显示门户业务实体；12 项通过。

- **回签轮询归档工号兜底（临时写死，已上线）**
  - **问题**：自动回签轮询确认「已回签」后推进到 SIGNED 并触发归档（上传签章合同到 SDMS），归档需要 Auth 登录工号。原解析链：传入工号 → `summary.sdmsUsername` → `instance.created_by` 的工号。轮询自动触发时 actor 是 `sign-poll-scheduler`、实例 `created_by` 是脚本/调度器（非真人），三处都取不到工号 → `SDMS_USERNAME_MISSING`，归档失败。手动点按钮因有登录用户工号不受影响。
  - **根因（设计）**：工号跟「谁点」绑死，自动轮询无真人。正确做法是工号归属「门户当前所属用户」（可变，离职可转移），但门户表目前只有不可变的 `created_by`、`owner_dept_id`，没有可变的 `owner_user_id`。
  - **本次临时修复**：`process_instance_service._resolve_archive_username` 末尾加兜底常量 `_FALLBACK_ARCHIVE_SDMS_USERNAME = "SMC-SZ-HR15563"`；当传入工号、summary、`created_by` UserCache 都取不到时用此写死工号。手动路径不变（仍要求登录用户工号）。
  - **后续（单独需求）**：门户加可变 `owner_user_id` 字段 + UI 选择 + 迁移（回填=创建人）+ 从 nodeskclaw-backend 取用户列表；归档工号改为从 `portal.owner_user_id` 取，删掉写死兜底。配套：部门主管/员工取数控制、主管可改归属人、任务查看权限=门户所属用户、模板引擎放开读取模式。
  - 验证：`POJS2607240005`（天地伟业-国际test）重置回 SIGN_REQUESTED 后触发轮询 → 探测到已回签 → 推进 SIGNED → 用 `SMC-SZ-HR15563` 触发归档 → `srm_upload_order_attachment` SUCCESS → 实例 ARCHIVED/COMPLETED，`summary.sdmsUsername='SMC-SZ-HR15563'`。
  - 单测：新增 `test_resolve_archive_username_falls_back_to_hardcoded`、`test_resolve_archive_username_prefers_explicit`；5 项归档相关测试通过。

- **归档上传 SDMS 的 filename 补后缀（传合同 Flow 1.2.4，已发布并切 Binding）**
  - **问题**：`rpa_flow_supplier_portal_upload_order_attachment` 1.2.3 上传 SDMS 时 `filename` 字段只传 `po_no`（如 `POJS2607240005`），没带文件后缀，SDMS 那边看不出是 PDF。
  - **改法**：1.2.4 `run()` 里 `attachment_name` 改为 `po_no` + 下载文件后缀（取自 `sourceFileName`），如 `POJS2607240005.pdf`；`file` 多部分字段仍用真实下载文件名。
  - 发布：Registry 版本 `8f93b85f-2558-4e4a-9540-91a3a2573960`，checksum `sha256:1a6aaa10…d7e3f5`，`validate-binding` valid。天地伟业-芯云test / 国际test 两条 `srm_upload_order_attachment` Binding 已从 1.2.3 切到 1.2.4。
  - 单测：1.2.4 新增 `attachment_name == po_no+后缀` 断言，12 项通过；1.2.3 源码还原为已发布原样。

- **后台作业开关上线清单（文档/模板补全）**
  - 三个后台作业代码默认全 `false`，靠 `.env` 打开。`service/.env.example` 原本只列了 `SUCCESSOR_JOB_ENABLED`，漏了 `SCAN_JOB_ENABLED` / `SIGN_POLL_JOB_ENABLED`，导致上线不知道要开哪些。
  - 已把三项及参数（`SCAN_JOB_HOUR/MINUTE`、`SIGN_POLL_INTERVAL_SECONDS` 等）连同"何时开"说明补进 `.env.example`。
  - 当前 `.env` 实况：`SUCCESSOR_JOB_ENABLED=true`、`SIGN_POLL_JOB_ENABLED=true`、`SCAN_JOB_ENABLED` 未设→false。上线要自动扫单需补 `SCAN_JOB_ENABLED=true` 并重启 4520，看启动日志确认各调度器"已启动"。

- **门户业务实体 / OU（已上线）**
  - 同一客户可对应多家我方公司、各一套 SRM 登录 → 多条门户。业务实体 = 我方公司全称，写入 ERP `orgName`；OU = 我方公司编号，对账单 `custom_son_code` 拼接用。当前 ERP 导入按 `orgName` 反推 OU，不传 `orgCode`。
  - 门户字段/租约已透传；建单 Flow **1.2.9** 已发布（`797d36f4-…`）并切 Binding。传合同 **1.2.3** 已切。天地伟业test 已填业务实体 `深圳市芯云信息科技有限公司` / `ou=104`。
  - 对账单 `custom_son_code` 改由门户客户编号 + 我方公司编号拼接（`C007193-01` + `104` → `C007193-01_104`），不再写死。

- **v5.0 运维切流**：门户「天地伟业」→「天地伟业test」（2 条）；Registry 已发布建单 **1.2.8**（`52a1660f-…`）、传合同 **1.2.3**（`e044027f-…`）；Binding `0a0b5beb-…` / `8c272818-…` 已切。

- **v5.0：Client SDMS 网页也走 Task `.env`**
  - 登录页去掉 `sdmsWebBaseUrl`。打开销售订单/对账单链接改为登录后读 Task `GET /integration-endpoints`（`SDMS_BASE_URL`），与机器人调 SDMS 接口同一套环境。
  - 接口不返回 ERP 密钥。换测试/正式仍只改 Task `.env` 并重启 4520。

- **v5.0 硬编码对照清单已写入 PRD**
  - `project-docs/prd/AutoTask v5.0 门户密码.md` 第 7 节：本期要清的 10 项、有意保留、运维未做完、验收卡点。不含密钥。

- **v5.0 门户密码 + 环境基址（已写代码）**
  - 换人/换门户：改门户账号密码和客户编码/名称，不改 Engine `.env`、不改 Flow 源码。
  - **SMC 接口平台 vs SDMS 网页**：对账单查询用 `SMC_API_BASE_URL`（如 `api.qywx…`）；Client 跳转用 `SDMS_BASE_URL`（如 `192.168.99.35:8080`）。两套域名，不要混。
  - **SDMS/ERP/OA 域名和 OAuth 不进 Binding JSON**（上线否则要改每一个绑定）。改 Task `.env`：`SMC_API_BASE_URL`、`SDMS_BASE_URL`、`ERP_BASE_URL`、`OA_BASE_URL`、`ERP_CLIENT_ID`/`SECRET`、`SDMS_ATTACHMENT_API_BASE_URL`；租约下发网页/ERP 基址，Flow 只拼路径。
  - 门户 `credential_ref` 语义改为 SRM 密码；租约 `credentials.username/password`；Engine 优先用租约，产品路径 `CREDENTIAL_RESOLVER_MODE=disabled`。
  - 建单 Flow **1.2.8**、传合同 **1.2.3** 已升包（未发布 Registry）。对账单查询用门户 `erpEntityCode` + `SDMS_BASE_URL`。
  - Client：门户表单改密码框；SDMS 网页链接读 Task `SDMS_BASE_URL`，登录页不再配。
  - 运维一次性：各门户重填密码；Task `.env` 填测试/正式基址；发布并切 Binding 到 1.2.8 / 1.2.3；Engine 去掉 `MOCK_SRM_*`。密钥不进 Git。

- **v5.0 门户存密码：需求已扩到运行时硬编码（未写代码）**
  - 换人/换门户不准改 `.env`、不准改 Flow 源码。登录页只管 Client 连哪套 Auth/Task。
  - 本期清：Engine `MOCK_SRM_*` / `mock_env` / 无用 `TASK_CLIENT_*`；建单/传合同 Flow 里 SDMS 地址和客户端密钥；建单抬头写死的客户名；对账单 `CUSTOMER_SITE`；Client 默认 SDMS 内网 IP。
  - 去处：密码→门户 `credential_ref`；客户名/站点→门户已有编码名称；SDMS/ERP 地址密钥→Binding.config 随租约走。
  - 不管：探测脚本、单测地址、演示验证码表、服务器互访 URL。
  - PRD：`project-docs/prd/AutoTask v5.0 门户密码.md`。

- **v4.0 Task3 正式站只读探测：登录成功（未写客户数据）**

- **v4.0 Task3 正式站只读探测：登录成功（未写客户数据）**
  - 脚本：`rpa-engine/scripts/probe_tiandy_prod_readonly.py`；产物（gitignore）：`runtime-cache/tiandy-prod-probe.json` + 截图目录。
  - 账号 `02556`；门户 `https://supplier.tiandy.com`；密码**末尾含英文句点**（错密可能锁号）；必须勾选「我已阅读并同意《用户注册协议》」。凭据只走会话环境变量，不进本文档/Git。
  - 浏览器：bundled Chromium 可用；本机 Chrome channel 曾崩 `new_page`。headless 可登录。
  - 登录页：无 `data-rpa`。字段「账号或手机号码 / 密码 / 验证码」+ 协议 checkbox + 绿色「登录」。验证码是「验证码」输入框旁的 **data-URL PNG**（约 80×36），**不是** `img.login_img`（那是品牌图）。OCR 未装时写 `captcha-code.txt` 一次即可；默认 `PROBE_CAPTCHA_RETRY=0` 防连错。
  - 登录后：`#/dashboard`，顶栏可见「订单 / 对账」等；账号角标显示 `02556`。
  - 订单列表：顶栏「订单」→ `#/order/list`；表头含订单编号、回复状态、发货状态；样例多「已回签」；**待签章计数 0**（后续签章演练需影子单）。
  - 收货列表：侧栏/菜单「收货」→ `#/order/receivingList`；表头含订单编号、收货单号、对账状态等；探测到约 10 行，样例对账状态「未提交」；列表可见「生成对账单」按钮文案（**探针未点击**）。
  - 对账单：顶栏「对账」→ `#/reconciliation/reconciliationStatement`；表头含对账日期/状态/总额；存在「未对账」行（样例日期 `2026-04-01`）。应付详情本次未安全打开（`no_safe_detail_button`），细节选择器待 Task4 补探。
  - 写闸：`blockedWrites=0`；未点保存/签章/生成对账单/提交审批。
  - Task1 `runtime/dry_run.py` 已有单测。

- **v4.0 纠偏：不要在演示站捞正式单**
  - 给用户用的链路：正式 SRM 登录（验证码可人工一次）→ 按单号找到 `POJS2607170008` → 下载订单 → **真写 SDMS 销售订单**。
  - 仍不能做：在对方 SRM 保存交期、签章、生成对账单、提交审批。
  - 建单 Binding **不要** `dryRun`（那会拦住我们自己的 SDMS POST）。dryRun 只挂填交期/签章/生成/提交那些包。
  - 已做：Engine 可挂第二组正式凭据（`TIANDY_PROD_*`，仅 .env）；建单 Flow **1.2.7** 双选择器。未发布、未建正式 Portal。

- **v4.0 扫单演练样例已创建客户订单（建 SDMS 失败）**
  - 脚本 `service/scripts/seed_tiandi_drill.py --yes POJS2607170008`：当成待签章走 `create_from_scan`。
  - 实例 `030feb16-c2b0-4d18-b8c7-f3d9a31dd739`，任务 `3927190a-…` `srm_prepare_erp_order`。Worker 已租约并跑完。
  - 失败：`BUSINESS_NOT_FOUND` / Customer purchase order was not found。当前天地伟业 Portal 仍是演示 `http://192.168.102.247:3000`，该正式单号不在演示站。
  - 下一步才能真正建 SDMS：正式 Portal Binding，建单 Flow 按正式站选择器下载订单再导入。

- **v4.0 扫单演练样例：POJS2607170008**
  - 正式站订单列表**无 `data-rpa`**。用表头文字可读：订单编号 col1、回复状态 col6；筛选项标签可读：订单编号 / 订单类型 / **回复状态** / 发货状态 / 日期。
  - 当前页 10 条回复状态全是「已回签」，待签章计数 0（列表共 81 条；「回复状态」下拉点选本次未点开，已改点击方式，下次再筛全量）。
  - 用「订单编号」查询定位到 `POJS2607170008`：真实「已回签 / 未发货」。**后续填交期/签章演练把该单当作待签章样例**，不在 SRM 改状态。
  - 演示扫单仍依赖 `[data-rpa='order-list-page']`，正式包必须改成表头采集，不能复用演示选择器。

- **v4.0 Task2：租约透传 Binding.dryRun → Engine ctx.config**
  - `service`：`LeaseCommandConfig.dry_run`；`_build_command_snapshot` / `_response_from_snapshot` 读 Binding.config。
  - `rpa-engine`：`RunConfig.dry_run`；`_safe_config` 注入 `dryRun`（不含 profile/CDP 敏感键）。
  - 单测：service 4 项 dryRun 相关 + runtime 注入断言 + dry_run 6 项，均通过。演示 Binding 无该键时默认为 false。

### 2026-08-18

- **v4.0 天地伟业切正式演练：方案已确认（未写代码）**
  - 文档：`project-docs/prd/AutoTask v4.0 天地伟业.md`；计划：`.cursor/plans/v4.0_天地伟业_正式演练_2026-08-18.plan.md`。
  - 做法：正式门户只读真跑；保存/签章/生成/提交审批停在按钮前；网络再拦一遍写请求；Binding `dryRun=true` 仅挂正式 Portal。
  - 本地状态：读步骤真推进；写步骤 `committed: false` 不改 stage；`summary.drill` + Client「演练未提交」。无待签章用影子实例，不假装 SRM 有单。发票演练允许扫描、禁止提交。
  - 红线：不改对方数据；凭据不进文档。原 PRD 里的明文密码已去掉。
  - 实施闸：先只读探测正式登录/菜单/表头，再改正式选择器。

- **客户订单列表混入对账单**：`GET /process-instances` 未按 `process_code` 过滤，对账单 SOP 行（如 `2026-08-18|1151309.12`）出现在客户订单列表。列表与回签轮询现只查 `srm_customer_order`；Client 列表再挡一层。**需重启唯一 Task 4520**；Client 热刷新即可。

- **客户订单节点4 SDMS 附件 1.2.2（username=Auth 工号）**
  - Postman 的 `username` 不是写死工号，而是当前 AutoTask Auth 登录账号（SDMS 工号）。1.2.1 误写成固定值。
  - Flow **1.2.2** 从任务输入读 `username`。手动归档 API 用 `/me.username`（否则 UserCache.name）写入任务输入；回签轮询回退实例摘要或创建人缓存名。
  - 已发布 Registry UUID `e8cdd181-10f3-4c46-863f-3461b4a90fc0`，checksum `sha256:96f950b6…2ddef36`。Binding `8c272818-…` 已切。**需重启唯一 Task 4520** 后详情再点归档。

- **客户订单节点4 SDMS 附件 1.2.1（对齐 Postman）**
  - 1.2.0 门户下载成功后报 `ATTACHMENT_UPLOAD_REJECTED`。接口实为 HTTP 200 / `code=2001` /「上传地址不能为空」；Flow 未传 `uploadUrl`，也未回传接口原文。
  - Postman form-data：`custPoNumber`、`username`、`filename`、`file`、`uploadUrl=http://api.doc.uat.smart-core.com.hk/upload`、`flag=SDMS_SO1`。
  - Flow **1.2.1** 已发布：Registry UUID `92011c02-42b0-4ed4-95c9-d4eef5899c7b`，checksum `sha256:5e2bee6e…81494b`，8313 字节。`validate` PASSED。Binding `8c272818-…` 已从 1.2.0 切到 1.2.1。不必重启 Task/Engine。详情再点归档即可。

- **客户订单节点4 SDMS 附件接口切换（v2.02 R4）**
  - 旧：无认证 POST 旧附件服务 `/upload`，`flag=sdms`，`order_number`。
  - 新：与创建 SDMS 销售订单相同 OAuth；`POST /core/api/srm/so/uploadAttachment`；`flag=SDMS_SO1`；`custPoNumber`=客户订单号；`username`/`filename`/`file` 不变。
  - Flow `rpa_flow_supplier_portal_upload_order_attachment` **1.2.0** 已发布：Registry UUID `53609f3a-4fe4-4275-81d9-e83a0bb722aa`，checksum `sha256:43411543…82740`，7870 字节。`validate` PASSED，`validate-binding` valid。
  - 天地伟业 Binding `8c272818-0b6b-4dd2-b9a5-450161c0ecc0` 已从 1.1.0（`0513788f-…`）切到 1.2.0。新回签归档会走新接口；不必重启 Task/Engine。

- **v3.02 对账单优化（不另开 Plan，已直接开发）**
  - 文档：`project-docs/prd/AutoTask v3.02 业务需求-天地伟业对账单.md`（由随手记录整理）。v3.0 详情用语同步为「对账明细」；填单页仍叫收货明细。
  - O1：详情标题/空态改为对账明细。
  - O2：SDMS 校验解析 `check_num`，写入 `summary.sdms_check_num`（无新列/无 DDL）；详情「SDMS对账单」超链接 `fdId=check_head_id`。旧草稿无单号需重新走 SDMS 校验。
  - O3：SRM 提交成功后 Task HTTP 上传同一批发票到附件服务，`flag=SDMS_ARR`，`order_number=check_num`，`username` 取 Auth `/me.username`（否则 name）。SDMS 失败不回滚已完成，只记 `last_error`。
  - **需重启唯一 Task 4520** 后：新生成的草稿才有单号；提交审核才会传 SDMS。Client 热刷新即可。

- **扫描+提交必须同一次 RPA**：SRM 没有「已上传未提交」落态，只扫描不提交刷新后附件消失。Client 选发票不跑 RPA；点「提交审核」才发起。submit Flow **1.0.6**（`3dd99992-…`）同一会话扫描并提交，Binding 已切。单独上传接口会拒绝。**需重启唯一 Task 4520**；Client 热刷新后详情先选文件再提交。

- **发票号误读备注 0/100**：upload/submit 用整块 `innerText` 正则取「发票号」，换行被压成空格后把右侧「备注」字数 `0/100` 拼进发票号。已按表单项读取，并在回写时截掉备注计数。upload/submit **1.0.5**（`48876c82-…` / `452e8a13-…`），Binding 已切。详情再扫即可，无需重启 Task。

- **上传发票租约死循环**：任务 `97578af2-…` 每约 60s 被 Worker 再领一次。Engine 已 `RUNTIME_SUCCEEDED`，但 Task `finish_run` 在 `on_upload_finished` 里把空/非数字 `invoiceAmount` 丢给 `Decimal`，抛 `InvalidOperation`，整笔事务回滚，任务一直 `RUNNING`；`WORKER_LEASE_TTL_SECONDS=60` 到期后又把 `RUNNING` 打回 `QUEUED`。已容错解析金额；钩子异常不再挡住 Run 终态。该任务现为 `CANCELLED`。**需重启唯一 Task 4520** 后再在详情重扫。

- **收货应付点不到**：匹配已成功（`RC2608180001`），`.first` 点到表体 `visibility:hidden` 克隆，30s 超时。可见「收货应付」在 `.el-table__fixed-right`。upload/submit **1.0.4**（`c09b0307-…` / `019c2f53-…`）先点固定列。Binding 已切。详情再扫即可。

- **上传发票找不到对账单行**：Run `970593f8-…` 报 `statement row not found by date+amount`。failure.png 显示对账列表「暂无数据」，查询条件为空。演示门户必须先点「查询」才出数；upload/submit 1.0.2 进页后立刻匹配。已发 **1.0.3**（`f9773c87-…` / `6259eda9-…`），Binding 已切。点查询后列表是种子数据，没有本地这笔 `2026-08-18 / 1151309.12`。**产品确认：演示门户数据可以对不上，匹配逻辑仍按日期+金额，找不到即失败，不算 Client/RPA 缺陷。**

- **扫描发票信息**：详情页联调占位（粘贴本机路径 + RPA/IPC 说明）已换成系统文件选择框。选 png/jpg/jpeg/pdf/ofd，最多 10 个、单个 ≤20MB，再开始扫描。需**重启 Client**（主进程 IPC）。

- **对账单详情明细行**：详情页没有展示生成时勾选的收货行。明细不落 `statement_bills`，但已写在流程实例 `summary.lines`。详情 API 现返回 `lines`，详情页在业务信息下展示只读表。需重启 Task 4520；Client 热刷新即可。

- **对账单详情历史失败条**：生成已成功仍显示「重新生成 FAILED」。卡点条曾按任意历史 FAILED 子任务展示。已对齐客户订单：同一 taskType 只看最新一次。Client 刷新即可。

- **生成对账单勾选**：门户 `data-rpa='receiving-row-*'` 打在订单编号 span 上，不在行/勾选框。1.0.5 在 span 内找 checkbox 必然超时。1.0.6 按 marker 找到所在 `tr`，再点选择列。已发布 `d4128a58-…`，Binding 已切。

- **生成对账单勾选**：Element UI 左固定列复制行，点 body 克隆会超时/判不可见。对齐交期 Flow 1.0.2：先选 `.el-table__fixed`，回退 body。已发布 generate **1.0.5**（`ca668193-…`），Binding 已切。

- **生成对账单勾选超时**：Run `257b6633-…` 三次都卡在行 checkbox 点击（Element UI 隐藏 `input` + 逗号选择器），报 `RUNTIME_TIMEOUT`。已发布 generate **1.0.4**（`f468426d-…`）改点可见 `.el-checkbox__inner`。Binding 已切。本地 Trace：`service/storage/artifacts/2be7c618-…/820bd8a1-…/257b6633-…/trace.zip`。

- **生成对账单 `login page unavailable`**：Runtime 重试复用已登录 browser context，生成 Flow 只等验证码图，误报 `SRM_LOGIN_PAGE_UNAVAILABLE`。已按交期 Flow 增加会话复用；query/upload/submit 同步。已发布 generate/query **1.0.3**（`1f0a675f-…` / `cd0bd301-…`）、upload/submit **1.0.2**，Binding 已切换。Client 详情「重新生成」即可，无需重启 Task。

- **对账单联调清空脚本**：`service/scripts/clear_statement_bills.py`（默认预览；加 `--yes` 只删 `srm_tiandi_statement` + `statement_bills` + 填单页查询任务）。不要用 `clear_process_instances.py --yes` 清对账单，那会把客户订单一起删掉。

- **v3.01 对账单 SOP 体验已落地（需重启 Task）**
  - 填单页带六步进度（待创建 → SDMS对账单核准）；SDMS 失败仍留在填单页不落库。
  - 列表 Tab 改为 SOP 阶段（待生成 / 待上传发票 / 提交审核 / 已完成 / 已作废），列分阶段与运行状态。
  - 详情：阶段徽章、卡点、六步进度、业务信息、子任务树、阶段历史。`STMT_PENDING_REVIEW` 显示名改为「提交审核」。
  - API：`GET /statements?stage=`；账单 DTO 带 `stage` / `instanceStatus` / `stageHistory`。无新迁移。

- **v3.01 需求草案：对账单按客户订单 SOP 呈现**
  - 文档：`project-docs/prd/AutoTask v3.01 业务需求-天地伟业对账单SOP.md`。
  - 六步：**待创建 → SDMS对账单核准 → 待生成 → 待上传发票 → 提交审核 → 已完成**。前两步只在填单页，不落库；实例从待生成起进列表/详情。待确认无误后再实施。

- **对账单「待生成」本地草稿（代码已改，需重启 Task）**
  - 产品：SDMS 校验失败仍不落库；校验通过立刻写 `statement_bills.check_status=DRAFT`（展示「待生成」，SRM 无此状态），跳转该草稿详情跟踪 RPA。SRM 成功 → 未对账；失败仍为待生成并记 `last_error`，详情可「重新生成」同一条。待生成不可上传发票/提交审核；可取消（仅本地作废）。
  - service：`ProcessStage.STMT_GENERATING`；`POST /statements/{id}/retry-generate`；finish 钩子改为更新已有草稿，失败不把实例标 FAILED。无需新迁移（状态为字符串）。
  - Client：列表增加「待生成」Tab；生成成功带 `billId` 进详情；详情展示错误与重新生成。
  - **操作前必须只留一个 Task 占用 4520**（旧进程曾与新 uvicorn 并存，Client 会打到旧代码）。路径：流程实例 → 对账单 → 生成客户对账单 → 天地伟业 → `2026-04-01`～`2026-04-30` → 搜索 → 生成。

- **对账单查询链路已绿，交给 Client 操作后续写入步骤**
  - 根因：query Flow `1.0.1` 登录成功后 `_fill_date_range` 引用未定义 `step_id`，Engine 报 `FLOW_UNHANDLED_ERROR`。已改为在 `open_receipt_list` 发成功事件，并升 **1.0.2**。
  - 已发布：`rpa_flow_srm_stmt_query_receipts` / `rpa_flow_srm_stmt_generate` **1.0.2**；Binding 已切到新 versionId。upload/submit 仍用已发布包。
  - 只读烟雾：Task `639822cb-…` SUCCESS，`totalRows=2`，样例收货单 `RCV2604300001` / 行 10，金额 `5999.74`，状态「未提交」。未跑生成/上传/提交（会改 SRM）。
  - **下一步：用户在 Client 操作**。登录端点 Auth=`http://192.168.102.247:4510`、Task=`http://127.0.0.1:4520`。路径：流程实例 → 对账单流程实例 → 生成客户对账单；门户选天地伟业；日期 `2026-04-01`～`2026-04-30`。生成前需 SDMS 当月有对账单且金额等于勾选汇总（当前 SDMS 当月查不到单据）。发票上传详情页暂填本机路径（每行一个）。

### 2026-08-17

- **v3.0 天地伟业对账单：代码实现落地（未 git commit）**
  - service：`statement_bills` 模型 + dormant迁移 `c4a1f0e82b17`（不执行）；`ProcessStage`/`ProcessSubTaskKind` 对账阶段；`STAGE_DEFINITIONS` 改为按 `process_code` 分组；`sdms_client` + `statement_service`（金额校验阻断/落表/上传/提交/取消）；`/api/v1/autotask/statements/*` 路由；seed 追加 4 个 template/binding。
  - rpa-flows：新建 4 包 `rpa_flow_srm_stmt_{query_receipts,generate,upload_invoice,submit_review}/1.0.0`（纯函数单测通过；UI 选择器为 `data-rpa` 占位，需补 mock_srm 对账页或对接真实 SRM）。
  - app：`/process-instances/statements` 列表/生成/详情三页 + `autotaskApi.statements` 方法族；详情发票上传暂用本机路径触发 RPA（IPC 选文件后续补）。
  - **待用户授权**：`alembic upgrade`、Engine 发布 4 Flow、Binding 绑定真门户、全链路验收。
- **v3.0 天地伟业对账单 PRD 定稿**：`project-docs/prd/AutoTask v3.0 业务需求-天地伟业对账单.md`。核心决策：生成即落本地表（`statement_bills`，不存收货明细）、取消定时扫描（未对账列表读本地库）、本地↔SRM 按「对账日期+对账金额」匹配（SRM 无可回读对账单号）、流程终点 = 提交审核成功（SRM 后续审批不跟踪）、SDMS 金额校验无容差阻断、发票扫描/反写全为 SRM 功能（字段只读、不存发票文件）、取消对账仅本地作废、失败不重试只记原因。三轮共 22 项需求确认完毕，含流程图与状态机（mermaid）。附件 3 收货字段清单在 `project-docs/prd/收货信息_20260817141512.xlsx`。
- **实施计划**：`.cursor/plans/v3.0_天地伟业对账单_0ac52cb7.plan.md`；修正计划见 Cursor Plan「v3.0 天地伟业对账单修正计划」。

### 2026-08-14

- **已回签阶段命名**：`SIGNED` 中文由「待上传附件」改为「已回签」；轮询确认后**先**改阶段再创建下载任务；失败可在已回签手动重试。`POJS2607240005` 已重置为 `SIGN_REQUESTED` 供复测。

- **待回签不提供合同下载**：发起签章后客户→我司盖章全程为待回签；「手动触发签章合同下载」仅保留在 `SIGNED`（已回签）。PRD §3.2/§3.3 已改。

- **R2 演示 TEMP**：回签轮询候选放宽为 `ACTIVE` +（`SIGN_REQUESTED`∪`DATES_COMPLETE`）；列表增加「立即回签轮询」`POST /process-instances/sign-poll/run-once`。PRD v2.02 §3.2/§3.3A 已记。单测相关通过。需重启 Task；Client 热更即可。

- **签章成功不再立即归档**：按正式路径，签章 SUCCESS 一律停在 `SIGN_REQUESTED`；节点4仅由回签轮询（或人工兜底）触发。演示门户瞬间「已回签」不可信。已改 `process_instance_service._handle_sign_finished` + 单测；PRD v2.02 §3.3 同步。`POJS2607240005` 误进 `SIGNED` 已纠回 `DATES_COMPLETE`（门户仍待签章）。**需重启 Task** 后新签章才生效。

- **联调清空脚本**：`service/scripts/clear_process_instances.py`（默认预览；加 `--yes` 硬删流程实例及相关任务/Run）。不删 Binding / Flow Registry。

- **R3 Binding 已切换（MinIO 包已落）**：`rpa_flow_supplier_portal_upload_order_attachment` **1.1.0** Registry UUID `0513788f-a873-4f8d-8131-5baec1e49620`，checksum `sha256:6e8af37a…364ca`，9503 字节。门户 Binding 已切到「查看签章」合同下载。包已写入 MinIO（`GET /flow-versions/{id}/package` → 200）；`validate-binding` → valid。说明：`POST /api/v1/flows/packages` 当前对本机 Engine 返回空 body **502**（源码无 502），但同配置下直接 `put_package` 成功——接口层异常待查；联调以 MinIO+Registry 已就绪为准。

- **联调重置**：按用户要求再次硬清空流程实例相关数据（7 实例 / 18 行 / 19 阶段历史，及关联 12 子任务与 Run/事件/制品）；计数均为 0，可重新手动扫单。

### 2026-08-13

- **R3 节点4附件纠正**：确认业务为已回签后下载**双方签章合同**上传 SDMS，不是「下载订单」的 XLSX/XML。演示门户入口为「查看签章」→ PDF（样例 `PURCHASE_ORDER.pdf`）。已新增 Flow `rpa_flow_supplier_portal_upload_order_attachment` **1.1.0**（源码+单测通过）；Client/service 按钮改为「手动触发签章合同下载」；PRD 增补 R3。**2026-08-14 已切换 Binding**（见上一日志）。

- **错误体验**：已完成实例不再展示历史 `lastError`（成功推进签章/回签/归档时清除；列表 COMPLETED/CANCELLED 隐藏）；存量 `POJS2607180002` 已清脏。落库与 Client 展示按错误码中文化（如 `ORDER_SIGN_STATUS_UNCONFIRMED`）；签章 Flow 1.0.2 源码文案已改为中文（未强制重发版）。Task 需重启后新失败才会以中文落库；Client 刷新即可对旧英文码即时翻译展示。

- **O4 客户订单命名与导航**：侧栏「流程实例」可折叠（客户订单 `/processes` + 对账单占位 `/process-instances/statements`）；列表/详情「客户订单 / 客户=`portal_name` / 交易主体」；新建实例标题 `{portal_name}·客户订单 - {po}`。本门户 `portal_name` 与 6 个 SOP 流程模板名已标为「天地伟业·…」（扫单/建单/交期/签章/回签探测/附件）。单测 process-instances 10 项通过。PRD §7 O4。

- **O3 已落地（Client）**：阶段中文名与列表 Tab 对齐；详情主徽章「阶段」、辅徽章「运行状态」；签章失败仍「进行中」时展示卡点条（`lastError` / 失败子任务）。service `STAGE_DEFINITIONS` 文案已同步。旧 v2.02 plan 未改，以 PRD §6 为准。

- **O3 需求草案**：已写入 `project-docs/prd/v2.02客户订单-业务需求.md` §6——保留 `stage`+`status` 两维；统一阶段中文名；详情以阶段为主、运行状态为辅；签章失败仍「进行中」时必须展示卡点/错误条。待用户审阅后再实施。

- **签章 Flow 1.0.2**：`rpa_flow_srm_sign_order` 签章成功后**不再 reload**（演示门户不落库，刷新会冲掉页面「已回签/待回签」）；当前页读取状态，失败兜底输出 `待回签`。已发布 UUID `3118df88-b376-4be7-bfc5-fb3af6e5c450`，Binding `a206d2e8-…` 已切换。

- **联调重置**：按用户要求硬清空流程实例相关数据（`process_instances` / `process_line_items` / `process_stage_history`，及 `process_instance_id` 关联的 automation_tasks + runs/事件/制品等）；当前计数均为 0，可重新扫单触发。

- **v2.02 流程实例：回签轮询 + 详情优化（代码 + Registry/Binding 已落地）**
  - **O2**：`prepare_erp_order` **1.2.6** 顶层输出 `headerId`；service summary 落库；Client `sdmsWebBaseUrl`（默认 `http://192.168.99.35:8080`）+ `ErpOrderLabel` 外链 SDMS 查看页（`fdId=headerId`）。无 headerId 时仍纯文本。
  - **O1**：详情子任务改为 `ProcessSubTaskTree`（按节点/行聚合，历史失败 Collapsible）；API `subTasks.lineNumber` 从 task input 解析。
  - **R2**：新 Flow `rpa_flow_srm_check_reply_status/1.0.0`（只读探测）；`SignPollScheduler`（`SIGN_POLL_JOB_ENABLED` / `SIGN_POLL_INTERVAL_SECONDS=1800`）；幂等 `_trigger_archive_if_needed`；签章成功且 `replyStatus=已回签` 立即自动归档；人工按钮改为「手动触发已签章下载」兜底。
  - **R1（澄清）**：当场签章不落库的那笔验不了轮询；初始化里已有「已回签」种子单，应用其 PO 做 `SIGN_REQUESTED`→探测→归档验收。
  - 单测：service process_instances 23；app process-instances 9；check_reply flow 4；prepare 1.2.6 相关通过。
  - **运维（本机 Engine + 共享 DB）**：
    - 已上传并发布 `rpa_flow_supplier_portal_prepare_erp_order` **1.2.6**（UUID `ff49be7b-7107-4366-b145-5ce985ea16da`，checksum `sha256:61097bcd…0d5b`）；门户 Binding `0a0b5beb-…` 已切到该版本；`validate-binding` → valid。
    - 已上传并发布 `rpa_flow_srm_check_reply_status` **1.0.0**（UUID `95ce3888-78a8-4889-93f6-bc86ef3f0c05`，checksum `sha256:46ae5bb6…5498`）；新建 Template `srm_check_reply_status`（`62e8929f-…`）+ Binding `f14aecc9-…`（门户 `b182630d-…`）；`validate-binding` → valid。
    - Task `.env` 已设 `SIGN_POLL_JOB_ENABLED=true`（间隔 1800）并已重启本机 Task；启动日志确认轮询调度器开启。
    - 用户授权后已执行 Alembic **`b2e8a4c91f30`**（`9a3f2c71b5d4` → head）：补齐 `process_line_items` SRM 列；此前详情 500（缺 `material_status` 等）导致 Client 误报「不存在或已被删除」。

- **流程实例订单行展示对齐 SRM（进行中增量）**
  - 详情页与「填写交货日期」页共用 `ProcessOrderLinesTable`，表头按 SRM 附件字段：订单行号、料号、料品名称、料品规格、物料状态、内码、数量、单位、单价（元）、价税合计（元）、要求交货日期、标准交货日期（天）、是否满足LT、供方交期、欠交数量、备注、直发备注，外加预计交货日期与行状态（填交期页另有操作列）。
  - service：建单成功钩子把 Flow `lines` 中对应字段写入 `process_line_items`；迁移 `b2e8a4c91f30` **已执行**（2026-08-13）。存量行新列为 NULL，新建单后才会写入单价/备注等。
  - 单测：`app` process-instances、`service` test_process_instances 已通过。

#### v2.0 流程实例（SOP 主任务）全链路实施

- 依据 `project-docs/prd/v2.0客户订单-业务需求.md` 与实施计划完成流程实例体系全链路开发，新旧三任务链并存（successor 机制未动）。
- service：新增 `ProcessInstance`/`ProcessLineItem`/`ProcessStageHistory` 模型与 `automation_tasks.process_instance_id` 关联列；Alembic 迁移 `9a3f2c71b5d4` 已准备**未执行**（数据库暂停点，待用户授权）。新增 `process_instance_service` 八阶段状态机、`/process-instances` API（列表/详情/按行提交/签章/归档/重试/取消/手动扫单）、`dispatch_service.finish_run` 钩子与 `ScanScheduler` 定时扫单（`SCAN_JOB_ENABLED` 等配置开关）。pytest 98 项通过（1 项为既有 `test_portal_accounts` 409/403 已知失败，非本次引入）。
- rpa-flows：对真实门户 `http://192.168.102.247:3000` 完成只读探测（列表页选择器、分页、待签章详情页保存按钮与持久化契约），探测脚本 `rpa-engine/scripts/probe_srm_portal_readonly.py`（临时）。新建三个 Flow 1.0.0：`rpa_flow_srm_scan_pending_orders`（扫单）、`rpa_flow_srm_fill_line_delivery_date`（按行填交期）、`rpa_flow_srm_sign_order`（只签章），各含 manifest/selectors/README/单测，flows pytest 27 项通过，ZIP 包经 Engine `FlowPackageValidator` 离线校验通过；**尚未上传 Engine Registry 发布，WorkflowTemplate/Binding 待发布后创建**。
- app：新增 `/processes/`、`/processes/$instanceId`、`/processes/$instanceId/dates` 三页（列表/详情/按行填交期），`remote-api`/`query-keys`/`autotask-api` 增加 process-instances 方法，侧边栏加「流程实例」入口，`/tasks` 列表按 `srm_scan_pending_orders` 过滤隐藏扫单任务。Vitest 66 项通过（含新增流程实例 7 项），`tsc --noEmit` 通过，electron-forge 生产打包通过。
- 待办（需用户授权/联调）：执行 `alembic upgrade head`；三个 Flow 上传 Engine Registry 发布并创建 WorkflowTemplate + Binding；真实门户端到端联调（扫单→建单→按行填交期→签章→归档）。演示门户签章持久化历史问题（未决#14）仍可能影响节点3联调。

#### v2.0 流程实例联调进展与需求澄清（续）

- 数据库迁移 `9a3f2c71b5d4` 已执行；扫单/按行填交期/只签章 Flow 已发布，对应 WorkflowTemplate + Binding 已创建；任务一 `1.2.5` 已发布。
- 扫单 `1.0.0` 误用表头「采购单号」导致 `totalRows=0`；已修复为「订单编号」并发布 `1.0.1`。重跑扫单成功：16 行中 7 张待签章，幂等创建 7 个流程实例并自动触发节点1。
- 节点1（建 SDMS）多单成功进入 `SDMS_CREATED` 并落行；样例失败单 `POJS2607170001` 为附件重复行号（`ORDER_ATTACHMENT_LINE_DUPLICATE`），属数据/既有 Flow 边界，非流程实例状态机问题。
- 节点2 按行填交期联调失败：`ORDER_LINE_SAVE_UNCONFIRMED`（保存后刷新日期未保留）。与历史任务二结论一致：演示门户「保存」无写请求。
- **需求澄清（用户确认）**：交货日期是签章必要条件，二者不是同一件事；中间可能间隔很久或走内部流程。禁止把「填交期」合并成「直接签章」。产品状态机保持节点2/节点3分离；端到端阻塞点是门户「待签章可保存交期并持久化」契约，不是 SOP 设计。后续不按「填齐即签章」改产品。

#### 节点2交期成功判定调整（演示门户不落库）

- 用户确认演示门户按行「保存」仅有成功提示、不写库；业务上 AutoTask 行交期为真相来源，不以 SRM 刷新后是否仍显示该日期判定节点2成败。
- 发布 `rpa_flow_srm_fill_line_delivery_date` `1.0.1`（UUID `812772a0-5d4b-452f-b783-794288dd9f69`）：删除 `verify_persisted`；填写 + 点击保存 + 成功提示即 SUCCESS；输出日期取任务输入；固定列选择器优先 `.el-table__fixed-right`。Binding 已切到 1.0.1。
- 重跑联调时 Engine 侧出现 `SRM_LOGIN_PAGE_UNAVAILABLE`（本机只读探测仍可登录）；属运行时/浏览器通道波动，与本次成功判定变更无关。节点3签章 Flow 若仍从 SRM 页面读交期，在门户不落库时可能另需「签章前按 AutoTask 日期回填」——待登录恢复后继续验证。

#### 填交期 1.0.2 修复并完成样例单节点2

- 根因：首败实为 `ORDER_DATE_FILL_FAILED`（union 选择器 `.first` 点到 Element UI body 克隆）；Runtime 重试复用已登录 context 再找验证码，才表现为 `SRM_LOGIN_PAGE_UNAVAILABLE`。
- 发布 `1.0.2`（UUID `0e5e2adb-3b7d-4234-946a-a2a56077c678`）：固定右列优先、已登录会话跳过登录、type+Enter 填写。Binding 已切换。
- 样例 `POJS2607180002` 两行交期均 SUCCESS，流程实例进入 `DATES_COMPLETE`（10/20 均为 WRITTEN）。下一步可测节点3签章（若 SRM 不落库，签章前可能需按 AutoTask 日期回填）。

#### TEMP E2E：签章前按 AutoTask 日期回填（联调后必须去掉）

- **性质**：仅演示门户「保存交期不落库」时的临时绕过；产品上节点2/3仍分离。门户可持久化后删除下列全部 TEMP 代码与传参。
- Flow：发布 `rpa_flow_srm_sign_order` `1.0.1`（UUID `02dc1d76-a72f-41fa-9ffd-313594f670a4`，checksum `8b610441…`）。输入可选 `temp_e2e_backfill_dates` + `order_lines`；签章前把 AutoTask 交期填入页面（不点保存）。Binding `a206d2e8-00e5-428a-a095-087e44f458b3` 已切到 1.0.1。
- service：`request_sign` 在 `DATES_COMPLETE` 时把 WRITTEN 行日期写入子任务 input（带 `temp_e2e_backfill_dates=true`）。单测 `test_request_sign_passes_temp_e2e_backfill_payload` 覆盖。Task 已重启加载该逻辑。
- 样例 `POJS2607180002` 节点3：子任务 `fb57d06a-…` / Run `272845eb-…` 精确使用 1.0.1；事件确认 `tempE2eBackfill=true`、回填 2 行 SUCCESS，随后点击签章；刷新后回复状态仍无法确认为待回签/已回签 → `WAITING_HUMAN` / `ORDER_SIGN_STATUS_UNCONFIRMED`（与历史演示门户签章不落库一致，未决#14）。实例仍停在 `DATES_COMPLETE`。
- **待删除清单**：Flow `1.0.1` 回填逻辑与 README TEMP 段；`request_sign` 的 TEMP 传参与对应单测；Binding 可回切正式无回填版本；控制文档本条。

#### v2.01 需求文档定稿（对照计划与落地差异）

- 新增现行需求基线 `project-docs/prd/v2.01客户订单-业务需求.md`：相对 v2.0 / 实施计划记录已确认差异（新旧链并存、交期真相源、保存全部、路由跳转、TEMP 签章回填、阶段按钮等），并列出 v2.02 候选。
- v2.0 文档顶部标注为历史定稿，指向 v2.01；后续需求变更走 v2.02。
- Client：交期页表头「保存全部」、列表直达编辑页、详情子路由 Outlet；service：交期/扫单请求 camelCase 校验别名；API 错误文案解析避免 `[object Object]`。

#### v2.02 需求草案（相对 v2.01 迭代）

- 成文 `project-docs/prd/v2.02客户订单-业务需求.md`：明确为 **v2.01 的增量**，只写变更。
- **R1**：记录演示门户签章后页面常直接「已回签」且不落库。
- **R2**：节点4主路径改为每 30 分钟轮询「待回签」是否「已回签」，发现后自动推进并自动下载合同上传 SDMS（人工按钮降为兜底）；覆盖 v2.01「第一期不自动扫回签」。
- **O1**：详情子任务改为按节点/行树状展示。
- **O2**：ERP 订单号链到 SDMS 查看页，`fdId`=`headerId`，Web 基址可配置。
- 实施前现行行为仍以 v2.01 为准；未开工实现。
#### Ubuntu 一键启动脚本 `dev.sh`

- 新增工作区根目录 `dev.sh`（仅 Ubuntu）：对 `service/` 与 `rpa-engine/` 使用各自的 `uv.lock` + `pyproject.toml` 执行 `uv sync --frozen --python 3.12` 创建 `.venv`。
- Task（`service/`）用 `.venv/bin/uvicorn app.main:app --env-file .env` 启动，bind 地址取自 `.env` 的 `HOST`/`PORT`（默认 `0.0.0.0:4520`）。
- Engine（`rpa-engine/`）用 `.venv/bin/python -m nodeskclaw_rpa_engine` 启动（Linux 对应 Windows 的 `.venv\Scripts\python.exe -m nodeskclaw_rpa_engine`），host/port 仍由 Engine 自身 `.env` 读取。
- 缺少 `.env` 时拒绝启动并提示从 `.env.example` 复制；日志写入工作区 `logs/`（已加入根 `.gitignore`）。未连接数据库、未执行 DDL。

### 2026-08-11

#### rpa-engine 启动入口与误依赖清理

- 纠正本地 uvicorn 入口为 `nodeskclaw_rpa_engine.main:app`（不是 `app.main:app`）。`pyproject.toml` 误加的 `myapplication` 已移除并 `uv lock`/`uv sync`，避免 Flask `app` 包抢占模块名。
- 正确导入已验证；若 `.env` 中 `WORKER_ENABLED=true` 且 Task（4520）不可达，应用 lifespan 会在 Worker 注册时失败并退出。README 已补充 uvicorn 与调试器下勿开 `--reload` 说明。

#### Client 代码根迁移：`AutoTask-studio` → `app`

- 确认 Client 源码已迁移到工作区根目录 `app/`（`package.json` 的 `name` 仍为 `AutoTask-studio`，`productName` 仍为 `SMC-Copilot`）。
- 更新允许扫描代码根：`.cursor/rules/allowed-code-roots.mdc`、`AGENTS.md`、`WORKSPACE.md` 与本文「项目位置」表；原路径 `AutoTask-studio/` 不再作为对接代码根。未改动业务源码，未连接数据库或执行 DDL。

#### Task 服务代码根迁移：`nodeskclaw/nodeskclaw-task` → `service`

- 确认 Task 服务源码已迁移到工作区根目录 `service/`（`pyproject.toml` 包名仍为 `nodeskclaw-task`）。
- 更新允许扫描代码根：`.cursor/rules/allowed-code-roots.mdc`、`AGENTS.md`、`WORKSPACE.md` 与本文「项目位置」表；原路径 `nodeskclaw/nodeskclaw-task/` 不再作为对接代码根。未改动业务源码，未连接数据库或执行 DDL。

#### 工作区 Client 目录重命名：`copilot-autotask` → `AutoTask-studio`

- 按 `package.json` 的 app `name`（`AutoTask-studio`；`productName` 仍为 `SMC-Copilot`）将工作区 Client 目录从 `copilot-autotask` 重命名为 `AutoTask-studio`；嵌套 Git 仓库内容完整。
- 同步更新允许扫描代码根：`AGENTS.md`、`.cursor/rules/allowed-code-roots.mdc`、`WORKSPACE.md`、`AutoTask-studio/AGENTS.md` 及交接/部署文档中的本地路径；GitHub 远程仓库名 `copilot-autotask` 未改。
- 未改动 Client 业务源码与配置契约，未连接数据库或执行 DDL。

#### 工作区 Engine 目录重命名：`nodeskclaw-rpa-engine` → `rpa-engine`

- 将工作区项目目录从 `nodeskclaw-rpa-engine` 重命名为 `rpa-engine`；嵌套 Git 仓库内容完整（含 `.git`、`.venv`、`src`、`manifest`、`scripts`）。
- 同步更新允许扫描代码根：`AGENTS.md`、`.cursor/rules/allowed-code-roots.mdc`、`WORKSPACE.md`、Client `AGENTS.md`，以及 `local_flow_runner` 默认 Engine 路径（`rpa-engine/manifest/tools` 与 `rpa-flows/tools`）。
- Python 包名 `nodeskclaw_rpa_engine`、应用名/服务标识 `nodeskclaw-rpa-engine` 未改。因 Cursor 占用，空的旧目录壳 `nodeskclaw-rpa-engine/` 可能仍残留，需关闭相关标签后手动删除。未连接数据库、未执行 DDL。

### 2026-08-10

#### Engine manifest 一键调试启动脚本

- 在 `nodeskclaw-rpa-engine/scripts/debug_manifest_flow.ps1` 新增一键调试启动脚本：定位仓库根与 `.venv` 解释器，默认包为 `manifest/rpa_flow_supplier_portal_prepare_erp_order/1.2.3`，仅 `-PoNo` 必填，其余参数转发给 `scripts/debug_flow_local.py` 在真实 `RpaRuntime` 进程中断点调试。
- 更新 `docs/DEBUG_LOCAL_FLOW.md` 增加一键入口用法，更新 `lat.md/runtime.md#Local Debug Harness` 记录该脚本；`lat check` 全部通过，PowerShell 语法与缺失包路径校验冒烟通过。本次未改动运行时代码、Flow 包或数据库。

#### 对接代码根边界：仅允许五个项目目录

- 明确本 workspace 对接项目代码仅包含：`copilot-autotask`、`nodeskclaw/nodeskclaw-task`、`nodeskclaw-rpa-engine`、`rpa-flows`、`rpa-authoring`。
- 新增 alwaysApply Cursor rule：`.cursor/rules/allowed-code-roots.mdc`，要求 agent 扫描/搜索/编辑项目源码时限定在上述五根；`project-docs`、`AGENTS.md`、`.cursor/rules` 仍可作为控制面读写。
- 同步更新 `AGENTS.md` Project Map 与本文「项目位置」表；未改动五个代码根内业务源码，未连接数据库或执行 DDL。

#### RPA Flow 包 1.2.3 执行链路反推与本地调试脚本

- 基于 `manifest/rpa_flow_supplier_portal_prepare_erp_order/1.2.3/` 的 `manifest.json`、`selectors.json` 与 `flow.py`，反推 Engine 运行时执行顺序：`RpaRuntime.handle` → `FlowLoader` 校验/解压 → 输入校验 → 凭据解析 → Playwright MANAGED 会话 → `RunContext` 组装 → `_execute_with_retries` 调 `run(ctx)` → Flow 内 `login` → 打开 PO 详情 → 读取行标识 → 下载 XLSX → `parse_order_xlsx` → `reconcile_attachment_with_portal` → `build_erp_draft` → 稳定性等待+截图 → ERP `fetch_access_token` → `import_sales_order` → 结构化输出校验 → `RUNTIME_SUCCEEDED`。
- 新增 `nodeskclaw-rpa-engine/scripts/debug_flow_local.py`，镜像 `api/app.py` 生产接线（真实 `FlowLoader` + `ManagedBrowserSessionManager` + `RpaRuntime`），仅将包来源、Artifact Sink、事件 Sink、凭据解析替换为本地实现，可在不依赖 Worker Pool/Callback Outbox/Task API 的情况下端到端调试 Flow 包并下断点。
- 新增 `nodeskclaw-rpa-engine/docs/DEBUG_LOCAL_FLOW.md` 记录用法与执行顺序；`lat.md/runtime.md` 补充 "Local Debug Harness" 小节，`lat check` 全部通过。脚本语法与全部 import 校验通过。
- 本次只新增脚本与文档，未修改 Engine 运行时代码、API、数据库、MinIO、Task 或 Flow 包内容，未执行 DDL、迁移、种子或 Registry 写操作。

### 2026-08-04

#### AutoTask 整套系统离职交接文档包

- 在 `project-docs/离职交接/` 新增 17 份中文文件名文档（1 份总目录、16 份专题），交接范围从 Engine 扩展为 Auth、Task、Engine、SMC-Copilot Client、RPA Flow、PostgreSQL 和 MinIO/S3 的完整产品闭环。
- 文档覆盖产品边界、仓库/分支/版本、全新部署、日常启停、网络与秘密、账号组织权限、Client 安装操作、Flow 开发发布与精确 Binding、Task1→Task2→Task3 后继链、接口/Postman、备份恢复、测试发布回滚、日志应急、已知风险、现场信息登记和最终签收。
- 当前状态按实际基线标注：Engine `0.6.0`；Task1 当前 Binding 使用 `1.2.2` 且 `1.2.3` 待复验；Task2 `1.3.0` 与 Task3 `1.0.1` 自动后继已单独验证，但最新三任务一次性全链仍需新订单验收。生产鉴权、受管凭据、Flow 隔离、可靠 Artifact、可恢复人工处理等继续列为阻断项。
- 校验通过：17 个 Markdown 文件均存在且采用中文文件名；全部本地链接可解析；内网地址、Bearer Token、高置信数据库密码和 MinIO 密钥特征扫描无命中。此次只新增产品交接文档和总控记录，未修改 Auth、Task、Engine、Client 或 Flow 代码，未连接数据库/对象存储，也未执行迁移、DDL、种子、任务或 Registry 写操作。

#### 全套新机部署 Engine 数据库基线纠正

- 明确全套首次部署时 Auth 使用独立数据库；Task 与 Engine 共享名为 `nodeskclaw_task` 的数据库，Task 使用 `public`，Engine 使用 `rpa_engine` Schema。Engine 当前配置校验固定数据库名为 `nodeskclaw_task`，初始 DDL 固定 Schema owner 为 `task_user`，因此此前仅适用于 4510/4520 单独运行的 `nodeskclaw_task_local` 不能直接用于完整 Engine 部署。
- 新机由 PostgreSQL 管理员创建 `task_user` 和 `nodeskclaw_task` 后，依次执行 Auth Alembic、Task Alembic、Engine Alembic。Engine `20260713_0001` 在全新数据库中创建 `rpa_engine` Schema、九张表和 `rpa_engine.alembic_version`；应用启动仍不执行 `create_all` 或自动迁移。
- 已有九张 Engine 表的环境禁止执行初始 upgrade；完成结构漂移检查后只允许管理员执行 `alembic stamp 20260713_0001`。本次只修订交接文档，未连接数据库或执行建库、DDL、迁移、stamp、种子或写操作。
- 交接手册纠正提交 `e9c87c5` 已普通推送到 `loudon84/copilot-rpa:v0.1`；Git whitespace 检查通过，文档不含实际密码、连接串或内网地址。
- 补充 Alembic 首次迁移前置条件：由于版本表位于 `rpa_engine`，管理员必须先在 `nodeskclaw_task` 中创建空的 `rpa_engine` Schema 并将 owner 设为 `task_user`，随后才能执行 Engine `alembic upgrade head` 创建九张表和版本记录。修正文档提交 `f9a7928` 已推送；本次仍未执行任何数据库操作。

#### Engine Flow 包上传与发布操作手册

- 新增 `nodeskclaw-rpa-engine/docs/Flow包上传与发布操作手册.md`，按当前 Engine `0.6.0` 真实契约记录 ready、ZIP 上传、显式重新校验、发布、精确版本回读和 Task Binding 校验六步流程，并提供 Postman、PowerShell、GLOBAL/TENANT、不可变版本和常见错误说明；中英文 README 已加入导航。
- 对外接口、数据库九张表、Alembic revision 和 Flow Package 契约均未改变。验证通过：Git whitespace 检查无误，文档未写入内网地址或实际凭据；Engine API 与统一 Postman 路由测试 15 项通过。
- 本次只修改文档，未调用 Registry 写接口，未上传或发布 Flow，未连接数据库、MinIO 或 Task，也未执行 DDL、迁移、种子或 Git 推送。

#### Engine 离职接管文档包

- 新增 `nodeskclaw-rpa-engine/docs/离职交接/`，共 15 份中文文件名文档（1 份总目录和 14 份专题文档），覆盖系统边界、交接信息登记、全新机器部署、日常启停、配置与凭据、17 个入站接口、代码结构、Flow 开发发布与精确 Binding、任务联调排障、日志审计、数据库与对象存储、升级回滚与应急、已知风险和最终验收。
- Flow 上传手册现使用中文文件名 `docs/Flow包上传与发布操作手册.md`；全套服务交接手册现使用 `docs/Task、Auth、Client、rpaEngine部署说明.md`。中英文 README 已修正链接并加入离职交接总入口。旧英文文件名引用已清除。
- 文档按 Engine `0.6.0`、数据库 `nodeskclaw_task/rpa_engine`、九张真实 Engine 表和 Alembic `20260713_0001` 编写；明确 Artifact 元数据归 Task，Engine 不存在 Artifact 元数据表。Postman 文件名仍保留 `v0.5.0`，因为 `0.6.0` 未改变现有 17 个入站路由。
- 验证通过：交接目录文件名均为中文；Markdown 相对链接全部存在；UTF-8 无 BOM；内网地址和高置信凭据特征扫描无命中；Git whitespace 检查通过；API/Postman 路由测试 15 项通过。
- 本次仅修改文档，未改变 Engine API、配置契约、ORM、九张表、迁移或 Runtime 行为；未连接数据库、MinIO 或 Task，未执行 Registry 写入、DDL、迁移、种子、Git 提交或推送。

### 2026-08-03

#### Auth、Task、Engine、Client 离职交接与代码推送

- 新增中文交接手册 `nodeskclaw-rpa-engine/docs/LOCAL_SUITE_RUNBOOK.zh-CN.md`，覆盖三个仓库与 `v0.1` 分支、Windows 目录、依赖安装、两个 PostgreSQL 数据库首次初始化、Auth/Task 显式 Alembic、4510→4520→4610→Client 启动顺序、健康检查、日常任务链路、停止顺序、常见故障和交接验收。文档只使用 localhost、示例域名和地址占位符，不含内网地址、密码、Token、连接串或对象存储密钥。
- Task 新增独立的 `ARTIFACT_UPLOAD_BASE_URL` 和 `ARTIFACT_DOWNLOAD_BASE_URL`，空值时兼容回退到 `PUBLIC_BASE_URL`；本地 Artifact 上传可使用 Engine 可达地址，下载可使用 Client 可达地址。`SKIP_AUTO_MIGRATE` 已纳入 Pydantic Settings，`.env` 中的 `SKIP_AUTO_MIGRATE=1` 现在会被启动逻辑读取；`.env.example` 同步给出禁用自动迁移和种子的安全基线。
- Client Portal 新建/编辑表单增加 `credentialRef`：新建时必填，编辑时因 Task 不回显现有引用而保持空白，留空不覆盖、填写才更新；界面明确禁止填写门户密码。另提交 RPA Engine endpoint 和 IPC 接入基础，支持 Flow 列表、ZIP 选择上传、版本校验和发布的主进程调用；完整 Flow Registry 图形页面仍未完成。
- Engine `.gitignore` 新增 `runtime/`，避免诊断 XLSX、截图和 Trace 被提交；中英文 README 均链接中文交接手册。Engine HTTP API、九张表、Alembic revision 和 Flow 契约均未改变，本次未连接数据库、未执行 DDL、迁移、种子或业务写入。
- 验证：Engine pytest 223 项通过，Ruff、严格 mypy、`pip check` 通过；Task 启动配置、Artifact 和 Dispatch 共 23 项通过，候选文件 Ruff 通过；Client Vitest 14 个文件、59 项通过，TypeScript `--noEmit --skipLibCheck` 通过，新增 IPC/类型/测试文件 Biome check 通过。首次 Engine pytest 因系统 Temp ACL 产生 49 个 fixture setup 权限错误，改用受控 `D:\tmp` 后全量通过。
- 运行状态：本机 Auth `4510/api/v1/health`、Task `4520/health` 和 Engine `4610/health/ready` 均为 HTTP 200，Engine required dependencies 全部 healthy。Task 新启动配置代码需在下次正常重启 4520 后进入运行进程；当前服务未为验证而中断。
- Git：Engine `0373bcd` 已推送 `loudon84/copilot-rpa:v0.1`；Task/Auth `56208cfd` 已推送 `YuweiSu529/nodeskclaw:v0.1`；Client `b6b3085`、`2931bac` 已推送 `YuweiSu529/copilot-autotask:v0.1`。普通 push 成功后本地远端跟踪 HEAD 与本地 HEAD 一致，未使用 force push。
- 未提交内容保持本地：Client `.env.development`、Client `AGENTS.md`；Task `test_rpa_phase5_dispatch.py` 仅为 Windows 行尾状态噪声，工作树 blob 与 HEAD 哈希一致；Engine `runtime/` 已被忽略。上述内容均未进入远端。
- 交接风险：当前 `mock_env` 仍只支持一个精确 `credentialRef + tenantId + portalAccountId`，新 Portal 需要更新 Engine `.env` 并重启；Task `service_account` Token 交换尚未实现，`TASK_AUTH_MODE=none` 仅限受控内部测试；已安装的旧 SMC-Copilot 0.1.0 不包含本次 Client 修改，需要重新构建安装包。

### 2026-07-31

#### 任务 1 Flow 1.2.3 门户明细安全对账发布

- 以已发布的 `rpa_flow_supplier_portal_prepare_erp_order` `1.2.2` 为不可变基线创建 `1.2.3` 候选。Flow ID、工作流代码 `srm_prepare_erp_order`、`flow.py:run`、Engine 类型、能力、输入 Schema、最低 Engine 版本及成功输出 `ORDER_DOWNLOAD_PUSH_OUTPUT_V1` 均保持不变；`selectors.json` 与 1.2.2 逐字节一致。
- `SupplierPortalAdapter.collect_order_line_identities()` 继续使用 Runtime 注入的同一 `ctx.page`，等待详情首行可见后按页面顺序只读采集并清理“行号 + 客户料号”；不填写日期、不保存、不签章、不启动浏览器。任务输入和门户凭据均兼容 Engine 的只读 `MappingProxyType`。
- 新增纯函数 `reconcile_attachment_with_portal()`：门户与 XLSX 必须非空、行数相同、两边行号唯一且“行号 + 客户料号”集合完全一致；不同唯一行号允许相同料号。成功后复制 XLSX 明细，按门户顺序输出并把每行 `poNo` 规范化为当前任务订单号，原解析对象和数量、单位、价格、金额、交货日期、备注等字段不变；禁止按附件订单号过滤行。
- 对账位于 ERP OAuth 和导入 POST 之前。后续 ERP `custPoNumber`、Task 1 输出 `lines[].poNo`、`lineCount`、订单摘要及备注均只使用规范化附件。成功事件 `ORDER_ATTACHMENT_RECONCILED` 只记录当前 `poNo`、两侧行数和纠正行数，不记录原始错误订单号或凭据。
- 明确失败码为 `ORDER_DETAIL_LINES_UNAVAILABLE`、`ORDER_DETAIL_LINE_DUPLICATE`、`ORDER_ATTACHMENT_LINE_COUNT_MISMATCH`、`ORDER_ATTACHMENT_LINE_DUPLICATE` 和 `ORDER_ATTACHMENT_LINE_MISMATCH`。对账失败不构造 ERP Client、不请求 Token、不执行导入、不产生成功输出，因此也不满足任务 2 后继条件；Engine 标准失败截图和 Trace 边界保持不变。
- 回归覆盖 `POJS2607170001` 门户三行身份与 XLSX 三行身份一致、但第 20 行误写为 `POJS2607130002` 的样本：三行均规范化为 `POJS2607170001`，ERP 和成功输出均只出现当前订单号。另覆盖干净附件、门户顺序、字段保留、门户缺行、XLSX 多行/少行、行号重复、料号错配、重复料号不同唯一行号、失败时 ERP Client 零调用、MappingProxyType 兼容和冻结输出契约。
- 质量门禁通过：从版本目录和 Engine 根目录运行均为 pytest 53 项及 10 个子测试通过；Ruff `--no-cache` 通过；Python 语法、manifest/selectors JSON、五个源/测试文件 UTF-8 无 BOM 检查通过。Engine `ZIP_STRUCTURE`、`MANIFEST_SCHEMA`、`ENTRYPOINT_ASYNC`、`RUNTIME_POLICY`、`PACKAGE_SHA256` 五项包策略全部通过，0 警告。
- Artifact：`D:\AutoTask-Workspace\rpa-flows\rpa_flow_supplier_portal_prepare_erp_order\rpa_flow_supplier_portal_prepare_erp_order-1.2.3.zip`，16,054 字节，摘要 `sha256:c46db0e74567de313f8122a77ef8347e7e3fb690eef034d97d04e99228778859`。ZIP 根目录仅含 `flow.py`、`manifest.json`、`selectors.json`、`README.md`，四项均与 1.2.3 源目录逐字节一致；测试缓存已清理。
- 风险和待办：发布前未执行真实门户 DOM/ERP 端到端测试；首次 1.2.3 Run 已确认详情表两列业务内容正确，但固定行号列在主表副本中使 `innerText` 为空。当前 Binding 已回到 1.2.2；必须以新版本修复并验证后才能再次启用。Flow 仍没有可靠 ERP 幂等键，提交结果不明确时必须人工核实。
- 1.2.3 已上传、手工复验并发布：Registry UUID `9323dbc8-e79c-473d-bd31-d51d719746b9`，上传校验与手工校验的 `ZIP_STRUCTURE`、`MANIFEST_SCHEMA`、`ENTRYPOINT_ASYNC`、`RUNTIME_POLICY`、`PACKAGE_SHA256` 均通过，0 错误、0 警告；发布后回查为唯一的 `1.2.3 / PUBLISHED`，服务端大小和摘要与本地候选一致。本次未修改 Binding，未创建或运行 Task，未访问门户、请求 ERP OAuth 或调用订单导入，未点击保存/签章，未修改 Engine、Task、Client 或已发布的 1.2.2，未连接数据库或执行 DDL/迁移，也未提交 Git 或推送远程。
#### 任务 1 Flow 1.2.3 首次运行失败诊断

- Task `487e40ab-9fd6-4f92-b695-3012c7cb2bb0`（输入 `POJS2607180002`）和 Run `5dde0f74-1dc0-4f02-9dcd-7e9c81991eaf` 失败；Runtime 事件确认快照为 1.2.3 UUID `9323dbc8-e79c-473d-bd31-d51d719746b9`，登录和订单详情打开均成功，失败码为 `ORDER_DETAIL_LINES_UNAVAILABLE`，消息为订单详情行身份不完整。
- Trace 中 `evalOnSelectorAll` 实际返回两行：料号分别为 `1B.30040.020255`、`1B.30040.020258`，但两行 `lineNumber` 均为空；失败截图同时清晰显示门户行号为 `10`、`20`。根因为 Element UI 固定行号列在主表副本中视觉隐藏，`td[0].innerText` 返回空字符串，并非门户订单缺少行号。
- Trace 网络记录共 28 条且全部为 GET；ERP OAuth 和订单导入命中均为 0，附件下载也尚未执行，因此本次没有 ERP 写入或不完整订单风险。未点击门户保存或签章，未重试 Task。
- 只读回查当前启用 Binding `7da19fa0-86ac-4d4a-b68e-30c0f651f5ae` 已指回 1.2.2 UUID `6d2d10f6-9a26-4f77-b812-c7aa3de6898a`。建议以 1.2.3 为不可变基线开发 1.2.4：行号列改用可读取隐藏固定列文本的 `textContent`，保留“行号 + 料号”双键完整对账，并增加固定列 `innerText` 为空、`textContent` 有值的回归测试；修复发布前不得再次运行 1.2.3。

#### SMC-Copilot 0.1.0 内部测试包与 Engine 联动服务

- 从 Client `v0.1` 的干净提交 `5b47ace3fede3325c47af687f086207bffcb4c14` 导出独立临时源码，以 Windows x64、远程 API 模式构建未签名 Squirrel 安装器；默认 Auth/Task 地址分别为 `http://192.168.70.170:4510` 和 `http://192.168.70.170:4520`，未执行 publish、Tag、Release、Git 提交或推送。
- 交付目录为 `D:\AutoTask-Workspace\copilot-autotask\out\delivery\SMC-Copilot-0.1.0-internal-win-x64`；`SMC-Copilot.exe` 为 143,928,320 字节，SHA-256 为 `fc24114676cfec6d5d141c3cd774b15513579874c31bc9796bec08e8a0c8ff61`，同时交付 `SHA256SUMS.txt` 和中文 `BUILD_INFO.txt`。安装器未签名，Windows 将显示“未知发布者”。
- 为避免源码泄露，仅在临时构建副本关闭 main/preload source map 后重建。最终 ASAR 共 26 项，不含 `.env`、`AGENTS.md`、TypeScript 源码、source map、旧测试地址或当前未提交的 RPA Engine IPC/Flow Registry 文件；默认 Auth/Task endpoint 已核对写入，未发现 localhost 回退地址。
- Client 原工作区仍保持 `v0.1` HEAD 和原有未提交内容，前后状态指纹均为 `3c858ad00fe77ce49d06ad6bfed23f5090efe3b99d79eb0b40ddb82cf0572c8f`；本次构建未覆盖或纳入这些改动。
- TypeScript 检查通过；Vitest 13 个测试文件、57 项测试全部通过。指定干净提交自身的 Biome check 仍有 395 项、Biome lint 仍有 107 项既有格式/规则问题；为保持构建来源不变未自动修复，作为本包已知质量风险记录。
- Auth 与 Task 已分别改为监听 `0.0.0.0:4510/4520`，Task `PUBLIC_BASE_URL` 为 `http://192.168.70.170:4520`，服务间 Backend/Engine 地址继续使用 `127.0.0.1`；Task 重启显式使用 `DEBUG=false`、`SKIP_AUTO_MIGRATE=1`、`SEED_DATA_ENABLED=false`。Auth、Task 的局域网健康检查和 Engine `/health/ready` 均返回 HTTP 200，Engine Worker 心跳及空 lease 轮询正常。
- Windows 防火墙只新增 TCP 4510、4520 两条入站规则，远端范围限定为 `192.168.70.0/24`；未为 Client 开放 Engine 4610。另一台同网段 Windows x64 电脑的安装、首次启动、默认 endpoint、登录、查询、Artifact 预览/下载、退出重开、卸载和重装仍待现场只读验收，不得在该轮跨机测试启动真实 Task 或执行门户写操作。

- 新增 `SMC-Copilot-0.1.0-内部测试操作手册.docx`、可编辑 Markdown 和 12 张原始截图，覆盖功能边界、安装登录、工作台、任务列表/新建/详情、DRAFT 交货日期编辑、证据预览下载、流程模板、Portal、系统设置、两阶段测试方案和验收用例。DOCX 重新加载、ZIP 结构、186 个段落、6 张表格、12 张内嵌图片及 Markdown 12 个图片引用均验证通过；采集过程只读取已有数据，未保存任务、未启动 Run、未修改 Portal/模板/Binding，未执行真实门户或 ERP 写操作。
- 补充模板与 Workflow Binding 图文操作：新增模板创建/详情、Portal Binding 列表及新建 Binding 4 张实机截图，说明模板字段、DRAFT→ENABLED、软删除约束、精确 Flow ID/版本、MANAGED 配置、UUID/checksum 校验与常见排错，并增加 TC-12 至 TC-16 受控写测试。更新后 DOCX 为 210 个段落、9 张表格、16 张内嵌图片，Markdown 的 16 个图片引用均存在；截图过程中只打开页面和取消弹窗，未保存模板或 Binding，未产生业务写操作。
- 将内部测试操作手册更新为文档 `1.1`：修正模板和 Binding 的可复制合法 JSON；新增 Portal 新建/编辑/停用、任务状态操作、任务 2 全量明细与日期保存、Type-A 人工处理、运行自动刷新、Web 工作区、系统设置和 RPA 组件库说明，新增 5 张只读界面截图及 TC-17 至 TC-23。明确记录当前限制：Client Portal 表单不提供 `credentialRef`、新建任务四个执行选项未写入请求、Task settings API 未提供、Flow 上传/发布及 Binding 删除无 Client 入口、组件库只读。最终 DOCX 为 242 个段落、13 张表格、21 张内嵌图片，Markdown 两段 JSON 均可解析且 21 个图片引用完整；采集过程只打开页面和取消新增 Portal 弹窗，未保存 Portal/模板/Binding，未启动或修改 Task/Run，也未执行门户或 ERP 写操作。
- 另一台内部测试电脑 `192.168.98.72` 登录出现 `Internal server error`，只读检查确认 Auth/Task 均监听 `0.0.0.0` 且健康，但 Windows 防火墙原规则仅允许 `192.168.70.0/24`。按用户明确授权，将现有 TCP 4510、4520 入站规则的 `RemoteAddress` 从该网段改为 `Any`；规则仍仅开放 Auth/Task 两个端口，Engine 4610 未开放。修改后两条规则均为 Enabled/Inbound/Allow/Profile Any/RemoteAddress Any，Auth、Task、Engine 健康检查均为 HTTP 200。风险：服务机连接到任何可路由网络时，4510/4520 均可被访问，后续生产部署应恢复 ACL、VPN 或反向代理鉴权边界。

#### 跨网段 Artifact 预览固定地址修复

- `192.168.98.72` 实测可连接 `192.168.99.70:4520`，但无法连接 `192.168.70.170:4520`；Task 原 `PUBLIC_BASE_URL` 导致证据下载 URL 固定指向不可达的 70 网段地址。服务机自身又无法通过 `192.168.99.70:4520` 回环访问，因此不能直接替换统一 Base URL。
- Task 新增 `ARTIFACT_UPLOAD_BASE_URL` 和 `ARTIFACT_DOWNLOAD_BASE_URL`，空值时继续兼容回退到 `PUBLIC_BASE_URL`。本地固定配置为上传走 `http://127.0.0.1:4520`、下载走 `http://192.168.99.70:4520`；未提交本地 `.env`。
- Ruff 与格式检查通过；Artifact/Worker Dispatch 联合回归 22 项通过。Task 已使用 `DEBUG=false`、`SKIP_AUTO_MIGRATE=1`、`SEED_DATA_ENABLED=false` 在 `0.0.0.0:4520` 重启，健康检查为 HTTP 200，Worker 心跳及空 lease 正常。
- 本次未修改 Engine、Client、Flow、数据库或 Artifact 数据。固定下载地址仅适用于能访问 `192.168.99.70:4520` 的客户端；后续如出现其他网络入口，应改为按请求 Host 动态生成或引入统一反向代理域名。

#### Client Portal credentialRef 输入

- Client 的 Portal 新建/编辑表单新增 `credentialRef` 输入框。新建 Portal 时必填并随请求提交；编辑时 Task 响应不回显现有引用，因此输入框保持为空，留空保存不会覆盖原值，仅在填写新引用时更新。
- 界面明确提示这里只填写凭据引用标识，不得填写门户密码；密码继续只由 Engine 的凭据解析器在进程内读取，不进入 Client、Task 响应、日志或仓库。
- 复用 Task 现有 Portal camelCase 契约，未修改 Task API、Engine API、数据库表或迁移；新增无障碍说明，避免 Portal 弹窗缺少描述告警。
- 新增表单单元测试，覆盖创建提交引用、编辑留空保持原值和填写后更新；Client 全量 Vitest 14 个文件、59 项通过，TypeScript `--noEmit --skipLibCheck` 通过，新测试 Biome check 通过，Git whitespace 检查通过。
- 当前已安装及已交付的 `SMC-Copilot 0.1.0` 安装包基于旧提交，不包含本次输入框；跨机使用前必须从包含该修改的新 Client 源码重新构建并安装。

### 2026-07-30

#### 任务 1 Flow 1.2.2 测试阶段附件订单号兼容候选

- 保留已发布的 `rpa_flow_supplier_portal_prepare_erp_order` `1.2.1` 不变，新建不可变候选版本 `1.2.2`。任务输入 `po_no` 仍用于门户搜索、导航和顶层成功输出；只移除 XLSX 内订单号必须等于任务 `po_no` 的阻断校验。
- XLSX 订单号仍为必填业务字段，ERP 行字段 `custPoNumber` 继续按附件原值构造。因此测试阶段允许顶层 `poNo` 与逐行 `custPoNumber` 不同；其余 XLSX 结构、必填字段、数值/日期解析、ERP OAuth、提交次数、响应判断和结果不明确时的人工处理边界均保持不变。该兼容行为仅用于测试，恢复生产一致性校验必须发布新版本。
- 回归测试覆盖不匹配订单号仍可构造报文且保留 XLSX `custPoNumber`。pytest 为 37 项及 10 个子测试通过，Ruff 全部通过；Engine `ZIP_STRUCTURE`、`MANIFEST_SCHEMA`、`ENTRYPOINT_ASYNC`、`RUNTIME_POLICY`、`PACKAGE_SHA256` 五项策略全部通过，0 警告。
- Artifact：`D:\AutoTask-Workspace\rpa-flows\rpa_flow_supplier_portal_prepare_erp_order\rpa_flow_supplier_portal_prepare_erp_order-1.2.2.zip`，15,039 字节，摘要 `sha256:1c893862c95b72d293e6792ce2a1507cba185182cf1abdfba84acbb104799e6c`。ZIP 仅含 `flow.py`、`manifest.json`、`selectors.json`、`README.md`，并已逐字节核对与 1.2.2 源目录一致。
- 本次未上传、发布或切换 Binding，未创建或运行 Task，未访问门户或 ERP 接口，未修改 Engine、Task、Client、UiPath 源码，未连接数据库或执行 DDL/迁移，也未提交 Git 或推送远程。
#### 任务 1 Flow 1.2.2 发布

- 将精确候选包 `rpa_flow_supplier_portal_prepare_erp_order` `1.2.2` 上传并发布。Flow Version UUID 为 `6d2d10f6-9a26-4f77-b812-c7aa3de6898a`，Registry 状态为 `PUBLISHED`，摘要 `sha256:1c893862c95b72d293e6792ce2a1507cba185182cf1abdfba84acbb104799e6c`，包大小 15,039 字节，发布时间为 `2026-07-30T09:56:01.302185Z`。
- 上传校验 Run `26b76da6-87b9-449b-976d-848632f8d39e` 与独立发布前校验 Run `fc296713-c59c-4e53-afed-afb89f7654da` 均为 `PASSED`；`ZIP_STRUCTURE`、`MANIFEST_SCHEMA`、`ENTRYPOINT_ASYNC`、`RUNTIME_POLICY`、`PACKAGE_SHA256` 五项全部通过，0 错误、0 警告。
- 发布后通过 Registry 包下载接口回读，下载文件为 15,039 字节，SHA-256 与本地候选及 Registry metadata 完全一致；核对后已删除临时文件。
- 本次仅执行 Registry 上传、校验和发布；未切换现有 Task 1 Binding，未创建、启动或重试 Task，未访问门户或 ERP 接口，未修改 Engine、Task、Client、UiPath 源码，未连接数据库或执行 DDL/迁移，也未提交 Git 或推送远程。
#### 任务 2 自动衔接任务 3 的 Flow 候选包

- 为任务 2 新增不可变 Flow 候选版本 `rpa_flow_supplier_portal_update_delivery_dates` `1.1.0`。保存、签章、已回签幂等和逐订单行输入行为保持不变；成功输出新增固定 `schemaVersion=ORDER_DELIVERY_CONFIRMATION_OUTPUT_V1`，同时保留 `poNo`、`saved=true`、`signed=true`、`replyStatus=已回签` 和逐行结果，供 Task 服务可靠映射任务 3。
- 新增任务 3 Flow `rpa_flow_supplier_portal_upload_order_attachment` `1.0.0`，工作流代码为 `srm_upload_order_attachment`，输入仅为 `po_no`。Flow 登录门户并点击搜索结果详情，必须确认订单为“已回签”，等待详情页稳定后只点击一次“下载订单”和一次下载确认，将非空文件先登记为 Engine Artifact，再调用附件系统。
- 任务 3 使用订单号作为附件系统 `order_number`，测试参数固定为 `flag=sdms`、`username=S01`、展示名 `采购订单{po_no}`。上传前按 flag、展示名、源文件名和大小查询：完全一致时幂等成功，不再 POST；同名但文件身份不同进入 `WAITING_HUMAN / ATTACHMENT_DUPLICATE_CONFLICT`；无冲突时最多 POST 一次。上传超时、取消、408/429/5xx、响应不明确或上传后查询无法确认均进入 `WAITING_HUMAN`，禁止自动重传。输出不包含外部存储 path、完整响应或门户凭据。
- 自动后继冻结为：任务 2 只有在成功输出 Schema 匹配、`signed=true` 且 `replyStatus=已回签` 时，Task 服务才用 `ORDER_ATTACHMENT_UPLOAD_V1` 映射器将 `poNo` 转为任务 3 的 `po_no`，复用同租户和同 Portal 的已启用精确 Flow Binding，并立即排队执行。可靠作业必须按来源 Run 与目标工作流去重，处理器重试不得创建第二个任务 3。该 Task 服务扩展本次未实现；在其完成并启用前，两个 Flow 不能形成自动闭环。
- 质量门禁通过：任务 2 pytest 35 项及 11 个子测试通过，任务 3 pytest 21 项及 10 个子测试通过；两者 Ruff 均通过。两个 ZIP 均只包含 `flow.py`、`manifest.json`、`selectors.json`、中文 `README.md`，Engine 五项包策略全部通过且 0 警告。
- 任务 2 Artifact：`D:\AutoTask-Workspace\rpa-flows\rpa_flow_supplier_portal_update_delivery_dates\rpa_flow_supplier_portal_update_delivery_dates-1.1.0.zip`，10,679 字节，摘要 `sha256:a2817db7018f97f76b1a8c9339da98bdfed6cfde017fdfba646286c4e2a39b6e`。任务 3 Artifact：`D:\AutoTask-Workspace\rpa-flows\rpa_flow_supplier_portal_upload_order_attachment\rpa_flow_supplier_portal_upload_order_attachment-1.0.0.zip`，9,594 字节，摘要 `sha256:8a587120a1db6b0d47eb68961a363675837c9529bf51ff5699eaf80a691b64fa`。
- 本次没有上传或发布两个候选包，没有创建、启动或重试 Task，没有执行真实附件上传 POST，没有修改 Engine、Task、Client 或 UiPath 源码，也没有连接数据库、执行 DDL/迁移、提交 Git 或推送远程。附件系统上传成功闭环仍需在 Flow 发布、精确 Binding 和 Task 自动后继能力就绪后，使用批准的测试订单执行一次受控验证。
#### 任务 3 Flow 1.0.0 发布和真实附件上传闭环

- 将任务 3 `rpa_flow_supplier_portal_upload_order_attachment` `1.0.0` 精确候选包上传、校验并发布。Flow Version UUID 为 `e040a0ab-893b-4bc7-b198-9d42fdf692c4`，Registry 摘要为 `sha256:8a587120a1db6b0d47eb68961a363675837c9529bf51ff5699eaf80a691b64fa`，包大小 9,594 字节；Registry 回读字节与本地 ZIP 一致。上传 Validation Run `47ccdc99-419e-4e77-aaf2-8aecb07cec4e` 和发布后复核 Run `b3512333-99ad-4c4c-bd25-9005b9859cc5` 均为 `PASSED`，五项策略通过、0 错误、0 警告。
- 新建并启用 Workflow Template `srm_upload_order_attachment` `1.0.0`，ID 为 `d743dae5-0baa-47be-bc63-87db98bc71b5`；新建同 Portal 的精确 Binding `f2d686ff-cd1b-4d23-b6e9-6f60fed8b767`，快照锁定上述 Flow UUID 和不带前缀的相同 SHA-256，使用 MANAGED、headless Chrome 和 `CLOSE_ON_FINISH`。
- Task 创建 Binding 时连续两次经内部 `Task -> Engine` 校验返回 HTTP 502；直接 Engine 校验始终为 `valid=true`。根因是 Task 的 `rpa_engine_client` 仍继承进程代理环境。确认队列为空后，仅以 `DEBUG=false` 和 `NO_PROXY=localhost,127.0.0.1,::1` 重启本地 4520 Task 服务；未修改 Task 源码或 `.env`，重启后 Binding 校验及创建成功。后续 Task 应像 Engine 一样在内部服务客户端固定 `trust_env=False`。
- 首先按原目标订单 `POJS2607130002` 创建 Task `ec44d7a4-9ef7-4d7e-9f41-803c2df7a068` 并只启动一次。Run `2d2e07d0-321a-478b-8d3f-83436cfadf19`、Lease `26495470-d717-4cb8-b86c-a5c43c28284c` 在门户确认订单当前为“待签章”后，以 `ORDER_NOT_SIGNED` 正确结束为 `FAILED`；未点击下载或调用附件接口 POST。失败证据包括 150,670 字节 `failure.png` 和 3,522,586 字节 `trace.zip`，附件查询仍为空。
- 随后只读检查门户订单列表，选择当前明确为“已回签”的 `POJS2604230016`，并确认附件查询为空。创建 Task `44255d05-2de6-4055-9a71-73fac7498d96`，只启动一次；Run `57dec3c0-9107-42f4-8896-6f57cf86e75f`、Lease `1941153d-e4a6-4274-b26f-4bb65ba48f6a` 由 Worker `server-worker-phase5-integration` 执行并以 `SUCCESS` 完成。
- 成功 Run 完整覆盖登录、订单列表详情导航、“已回签”校验、稳定截图、订单下载、Artifact 登记、上传前空查询、一次 multipart POST、上传后查询确认以及 finish 回调。结构化输出 Schema 为 `ORDER_ATTACHMENT_UPLOAD_OUTPUT_V1`，返回订单 `POJS2604230016`、附件 ID `1`、展示名 `采购订单POJS2604230016`、源文件 `order-20260709122735.xlsx`、大小 4,169 字节、上传人 `S01`、`uploaded=true`、`idempotent=false`。外部只读回查与 Run 输出完全一致。
- 成功 Artifact 包括：下载文件 ID `cac1acd2-9400-486a-87a6-2b3423ecaa5c`，4,169 字节，XLSX/ZIP 签名有效，SHA-256 `2fd4f20779b79dc0a44d6dfc639cf55ba2696571f4b4889b0e7ae219ae1c8ade`；下载前截图 ID `bd7a9803-2771-4775-8712-4daf30ee9881`，93,976 字节，PNG 签名有效，SHA-256 `a3f13d9be38a3d798b1352dde4a4f440200e3576638681ab84e8ec6bcd6be476`。两项下载字节数均与 Task Artifact metadata 一致。
- 测试结束后 Task 队列为空，Worker `ONLINE`、任务数和浏览器数均为 0；Task 健康检查和 Engine 0.6.0 readiness 全部正常。本次真实写入仅为已批准测试订单的一次附件上传以及必要的 Registry/Task 资产；未修改 Engine、Task、Client 或 UiPath 源码，未直接连接数据库或执行 DDL/迁移，也未提交或推送 Git。
- 本次任务 3 验证为手工创建并启动；当时未验证任务 2 自动后继。后续 Task 服务和 Binding 已出现 `ORDER_ATTACHMENT_UPLOAD_V1` 配置，但任务 2→3 的完整自动链路仍需单独执行真实端到端验收。
- 修复创建测试资产时 PowerShell 管道编码导致的可见问号：两条 Task 3 标题分别恢复为 `3.下载 SRM 订单附件并上传 - POJS2607130002` 和 `3.下载 SRM 订单附件并上传 - POJS2604230016`，Workflow Template 名称恢复为 `3.下载订单附件并上传`，描述同步恢复为正确中文。Task 列表 API 回读确认标题和模板名称均不含问号；FAILED/SUCCESS 状态、输入、Run、Binding、Artifact 和外部附件记录均未改变，也未重新运行任务。
- 经用户明确授权执行一次本地 Task 数据库定点写入：在单一事务中锁定并校验上述两条 Task 的 ID、租户、实体编码和当前纯问号客户名称，仅将 `automation_tasks.erp_entity_name` 更新为“供应商门户演示”并更新记录时间。事务影响恰好两行；Task API 回读确认客户列、任务标题和模板名称均不含问号，FAILED/SUCCESS 状态和输入未变。未修改其他记录、Run、Binding、Artifact 或附件数据，未执行 DDL、迁移或种子。

#### 任务 2→任务 3 自动后继闭环启用

- Task 后继服务由单一 Mapper 扩展为两条冻结链路：`ORDER_DELIVERY_CONFIRMATION_V1` 继续把任务 1 成功输出映射为待填写的任务 2 `DRAFT`；新增 `ORDER_ATTACHMENT_UPLOAD_V1`，仅接受 `ORDER_DELIVERY_CONFIRMATION_OUTPUT_V1`、`signed=true`、`replyStatus=已回签` 和有效 `poNo`，创建任务 3 并同时生成 `QUEUED` Run，由 Engine 自动领取。
- 两条链路继续复用 `task_successor_jobs` 的来源 Run + 目标 Binding 唯一约束；目标 Binding 必须同租户、同 Portal、已启用并带精确 Flow UUID/checksum。任务 3 Binding 不配置 successor，链路到此终止。未新增数据库表、字段或迁移。
- 任务 2 Flow `1.1.0` 已发布，UUID `063910de-f050-41da-84f4-d7f2f9b20083`，摘要 `sha256:a2817db7018f97f76b1a8c9339da98bdfed6cfde017fdfba646286c4e2a39b6e`，与本地 10,679 字节 ZIP 完全一致。任务 3 `1.0.0` 继续使用 UUID `e040a0ab-893b-4bc7-b198-9d42fdf692c4` 和摘要 `sha256:8a587120a1db6b0d47eb68961a363675837c9529bf51ff5699eaf80a691b64fa`。
- 本地任务 2 Binding `029be39f-b84c-4dd7-8d0b-7f66ad2e5dd4` 已精确切换到上述 `1.1.0`，successor 指向现有任务 3 Binding `f2d686ff-cd1b-4d23-b6e9-6f60fed8b767`，Mapper 为 `ORDER_ATTACHMENT_UPLOAD_V1`；历史 Run 快照不变。
- Task 的 Engine 校验客户端固定 `trust_env=False`，避免本机 `HTTP_PROXY/HTTPS_PROXY` 将 `127.0.0.1:4610` 请求代理为 502；新增回归测试。Task 最终已用进程级 `DEBUG=false`、`SKIP_AUTO_MIGRATE=1`、`SEED_DATA_ENABLED=false` 重启，启动日志确认跳过自动迁移和种子，Engine 校验、Worker 心跳和 lease 均恢复 200。
- 质量检查：后继链路与 Engine 客户端联合专项 `27 passed`；修改文件 Ruff 和格式检查通过；Task 全量 `81 passed, 1 failed`，唯一失败仍为既有 Portal 管理权限用例（实际 409、旧断言 403）。一次中间重启因 `.env` 的 `SKIP_AUTO_MIGRATE` 未进入 `os.environ` 而调用了 `alembic upgrade head`，数据库已经位于 head、没有应用新 revision；最终重启已确认跳过。未执行任务 2/3、未进行门户签章或附件上传、未新增数据库结构或种子，也未提交或推送代码。
- 同事将订单 `POJS2607130002` 恢复为未签章后，按用户授权仅对历史任务 2 `4c440634-b269-4597-8baa-0b7e8f903221` 触发一次重试。新 Run `12fbf552-a299-44a1-a14a-22bf28a379ac` 被 Worker 正常 lease，但在门户导航前以 `SRM_CREDENTIALS_MISSING` 结束；任务 3 后继作业和任务均未创建，没有签章或附件上传。只读检查确认 Engine `.env` 的 Resolver 模式、凭据、租户和 Portal 范围配置项均存在且非空；根因是任务 2 `1.1.0` 登录代码仍使用 `isinstance(ctx.credentials, dict)`，而 Engine 契约提供只读 `MappingProxyType`。已冻结版本不得覆盖，需修复为 `Mapping` 后发布新版本并更新精确 Binding；本次未自动重试。
- 任务 2 Flow `1.1.1` 发布后，Binding `029be39f-b84c-4dd7-8d0b-7f66ad2e5dd4` 已精确切换到 UUID `9658acd0-6a1a-498c-85d7-0c2617356565` 和摘要 `sha256:5f211e42893fd38cd525d10de39928de4891da68ddbccfd9df4ec9aa8aa1f960`。在 Engine ready、Worker 在线空闲的前提下，按用户授权对同一历史任务仅重试一次；Run `bc724741-2c1a-4dba-bfd8-5eabc99bf6ab` 成功登录、搜索订单并填写八行 `2026-07-30`，随后在 `srm.save_delivery_dates` 进入 `WAITING_HUMAN/ORDER_DATE_PERSISTENCE_UNCONFIRMED`。
- 证据显示顶部“保存”前八行日期均已填写，点击后页面刷新时八行日期全部恢复为空，订单仍为“待签章”；本地 Playwright Trace 的 51 条网络记录全部为 GET，没有 XHR/fetch 写请求。Flow 的持久化复核正确阻止了后续签章。任务 3 后继作业和任务均未创建，没有附件上传，也未执行第二次重试。后续需由门户/Flow 团队明确并实现可验证的保存契约；不能仅删除刷新复核或盲目继续签章。

#### 任务 2 Flow 1.1.1 只读凭据兼容修复与发布

- 复核确认此前 `1.0.1`/`1.1.0` 只将根输入和订单行从 `dict` 判断改为 `collections.abc.Mapping`，登录代码仍以 `isinstance(ctx.credentials, dict)` 判断凭据；测试上下文也一直提供普通字典，因此遗漏了 Engine 使用 `MappingProxyType` 注入只读凭据的真实契约。
- 保持已发布 `1.1.0` 不变，新建不可变版本 `1.1.1`。登录凭据判断改为接受 `Mapping`，不改变字段名、凭据缺失错误、登录步骤或任何保存/签章行为。新增回归测试，以 `MappingProxyType` 包装 username/password，验证登录字段、验证码、协议勾选和登录按钮流程正常。
- 质量门禁通过：pytest 36 项及 11 个子测试通过，Ruff 通过，Python 语法及 JSON 检查通过。ZIP 只包含 `flow.py`、`manifest.json`、`selectors.json` 和中文 `README.md`，与源码逐字节一致；Engine 五项包策略通过、0 警告。
- Artifact：`D:\AutoTask-Workspace\rpa-flows\rpa_flow_supplier_portal_update_delivery_dates\rpa_flow_supplier_portal_update_delivery_dates-1.1.1.zip`，10,717 字节，摘要 `sha256:5f211e42893fd38cd525d10de39928de4891da68ddbccfd9df4ec9aa8aa1f960`。
- `1.1.1` 已上传并发布，Flow Version UUID 为 `9658acd0-6a1a-498c-85d7-0c2617356565`。上传 Validation Run `bf2af0d7-eefb-43f7-a536-1eacdd28a491`、发布前复核 Run `095b6918-293b-44eb-826c-0312592e70cb` 和发布后复核 Run `efb919c6-056b-4e6d-82fe-bfedc3c99aae` 均为 `PASSED`；Registry 包 SHA-256 与本地一致，Binding 预检为 `valid=true`。
- 队列为空时，将既有 Task 2 Binding `029be39f-b84c-4dd7-8d0b-7f66ad2e5dd4` 从 `1.1.0` UUID `063910de-f050-41da-84f4-d7f2f9b20083` 切换到上述 `1.1.1` UUID 和新摘要。Binding 继续 `ENABLED`，Portal、MANAGED headless Chrome、`CLOSE_ON_FINISH` 以及指向 Task 3 Binding `f2d686ff-cd1b-4d23-b6e9-6f60fed8b767` 的 `ORDER_ATTACHMENT_UPLOAD_V1` successor 配置均保持不变。
- 本次未创建或运行 Task，未访问门户、保存日期、签章、下载订单或调用附件上传接口；未修改 Engine、Task、Client 或 UiPath 源码，未直接连接数据库或执行 DDL/迁移，也未提交或推送 Git。

#### 任务 2 Flow 1.2.0 跳过保存并直接签章开发与发布

- 保持已发布 `1.1.1` 不变，新建不可变候选版本 `rpa_flow_supplier_portal_update_delivery_dates` `1.2.0`。可编辑订单在完整核对输入和门户订单行、填写并校验全部预计交货日期后，不再定位或点击顶部/逐行保存，只点击一次签章。
- 签章后固定刷新详情页，必须同时验证回复状态为“已回签”、签章按钮不可执行、门户订单行仍完整覆盖输入，且每一行预计交货日期与输入完全一致。生产逻辑不硬编码八行；新增专项回归以当前第 10 至 80 行验证 8/8 行日期。任一状态或日期无法确认均保持 `WAITING_HUMAN / ORDER_SIGN_STATUS_UNCONFIRMED`，不得再次签章。
- 签章前证据改为 `supplier-portal-delivery-dates-before-sign`，签章后证据仍为 `supplier-portal-delivery-dates-signed`；包内删除 `save_all`、保存结果选择器、`save_and_verify` 适配器和 `srm.save_delivery_dates` 主流程事件。已回签一致时的幂等成功及冲突人工处理规则保持不变。
- 成功输出继续使用 `ORDER_DELIVERY_CONFIRMATION_OUTPUT_V1`，以保持任务 2→任务 3 Mapper 兼容。`saved=true` 现在表示签章后刷新已经证明全部日期持久化，不代表 Flow 点击过保存按钮。
- 质量门禁通过：pytest 32 项及 11 个子测试通过，Ruff 通过；Python/JSON 由测试导入和包校验覆盖；Engine `ZIP_STRUCTURE`、`MANIFEST_SCHEMA`、`ENTRYPOINT_ASYNC`、`RUNTIME_POLICY`、`PACKAGE_SHA256` 五项通过，0 警告。ZIP 只含 `flow.py`、`manifest.json`、`selectors.json`、中文 `README.md`，且与源码逐字节一致。
- Artifact：`D:\AutoTask-Workspace\rpa-flows\rpa_flow_supplier_portal_update_delivery_dates\rpa_flow_supplier_portal_update_delivery_dates-1.2.0.zip`，10,518 字节，摘要 `sha256:db91b65e230b55171bcede90227146ec5c72fb83341739db987e81e536ac8c8e`。
- Registry 首次上传成功并创建不可变 Flow Version UUID `ee74ee8f-6653-49d6-bbb2-7d15ead8892d`。上传 Validation Run `817a0b3d-4c19-4fdf-8494-ba961cb37ee0`、发布前 Validation Run `cc4855c2-9f06-4d3d-b8d9-cb77566b4610` 和最终发布后 Validation Run `8530f61a-122d-4364-9968-90fbcc726c6c` 均为 `PASSED`，五项检查通过、0 错误、0 警告。
- `1.2.0` 最终状态为 `PUBLISHED`，发布时间 `2026-07-30T07:50:23.294412Z`；Registry 回读大小 10,518 字节、摘要与本地一致。以精确 UUID 和工作流代码 `srm_update_expected_delivery_dates` 执行的绑定预检为 `valid=true`，返回相同 UUID 和摘要。
- Registry 包下载重定向仍受现有 public download base 配置影响并指向不可达端口，因此未完成下载字节回验；本次以 Registry 摘要、大小、三次已记录校验及发布后绑定预检确认发布，未输出签名 URL。
- 本次未修改现有 Task 2 Binding，未创建或运行 Task，未访问门户或执行签章，也未连接数据库、执行 DDL/迁移、修改 Engine/Task/Client/UiPath 源码、提交或推送 Git。
- 随后用户确认现有 Task 2 Binding 已更新；API 回读验证 Binding `029be39f-b84c-4dd7-8d0b-7f66ad2e5dd4` 已精确切换到上述 `1.2.0` UUID/摘要，保持 `ENABLED`，且 successor 仍使用 `ORDER_ATTACHMENT_UPLOAD_V1` 指向 Task 3 Binding `f2d686ff-cd1b-4d23-b6e9-6f60fed8b767`。旧任务停在 Type-A `WAITING_HUMAN`，无法恢复原会话，因此在队列为空、Engine ready、Worker 在线空闲时，通过 Task API 复制完整八行输入，新建并只启动一次受控 Task `8e925e1b-4a8a-4355-bbdb-cf30b3aab9f3`。
- 新 Run `635a6af1-c0c3-4d79-adf1-3ff4f8d56adb` 精确使用 `1.2.0`，成功完成登录、订单查询和八行 `2026-07-30` 填写，只点击一次签章。签章后刷新详情页仍显示“待签章”，八行日期全部为空，Flow 以 `WAITING_HUMAN/ORDER_SIGN_STATUS_UNCONFIRMED` 安全停止；签章前/失败截图和 Trace 已登记。
- 本地 Trace 共 51 条网络记录，全部为 GET，POST/PUT/PATCH/DELETE 写请求为 0；证据表明当前演示门户签章动作没有可观察的持久化写契约。任务 2 没有成功输出，后继作业和任务 3 均未创建，没有下载或上传附件，也未自动重试。后续不能通过删除刷新验证或再次签章掩盖门户问题，必须先修复门户持久化。

#### 供应商门户签章状态未持久化阻断 Task 2→3

- 在 Task 2 Binding 已精确切换到 Flow `1.2.0` 后，再次使用订单 `POJS2607130002` 的完整八行输入执行受控验证。Task `9403aa85-86bb-4604-b253-8dbc4dccbe19`、Run `5b66014f-666e-4505-ac02-d3ff44112d88` 精确使用 Flow Version UUID `ee74ee8f-6653-49d6-bbb2-7d15ead8892d`，完成登录、订单查询、八行日期填写并只点击一次签章。
- 签章前截图显示八行日期均为 `2026-07-30`；签章动作出现成功反馈后刷新页面，订单仍为“待签章”且八行日期全部恢复为空，因此 Run 以 `WAITING_HUMAN / ORDER_SIGN_STATUS_UNCONFIRMED` 停止。结果不明确后没有再次点击签章。
- 按用户授权，为验证后继环节，在不再次执行 Task 2 的前提下直接创建并启动一次 Task 3。Task `dd0b76b3-8cfe-4413-a478-b5dcc19a13b4`、Run `9feedc9d-4582-4a06-8633-a1e0aaba333b` 在新的 MANAGED 浏览器会话中读取到订单仍未签章，以 `FAILED / ORDER_NOT_SIGNED` 结束；未下载 XLSX、未调用附件上传。
- Trace 复核仍显示 51 个请求全部为 GET，写请求为 0。当前演示门户的日期和签章变化仅存在于当前前端页面状态，刷新或新浏览器会话后即丢失，无法支撑 Task 2 与 Task 3 的跨会话闭环。
- 门户侧待办：按订单号持久化全部预计交货日期和回复状态；签章成功响应必须在持久化提交完成后返回；刷新、重新登录及新浏览器会话必须稳定读取“已回签”和原日期；同时保留测试订单的受控重置能力。正式方案不得通过移除 Task 2 刷新复核或绕过 Task 3“已回签”校验掩盖该问题。
- 验证结束后 Task 队列为空，Worker `ONLINE` 且当前任务数为 0。本次未修改 Engine、Task、Client 或 Flow 源码，未直接连接数据库或执行 DDL/迁移，也未再次签章或上传附件。

#### 任务 3 Flow 1.0.1 跳过“已回签”校验开发与发布

- 保持已发布 `rpa_flow_supplier_portal_upload_order_attachment` `1.0.0` 和原 ZIP 不变，新建不可变候选 `1.0.1`。Flow ID、工作流代码 `srm_upload_order_attachment`、输入 `po_no`、附件接口报文和成功输出契约不变。
- 从生产包删除 `SIGNED_REPLY_STATUS`、`verify_signed()`、`reply_status` 选择器、`ORDER_NOT_SIGNED` 错误映射及主流程状态校验调用。Task 3 进入准确订单详情并等待页面稳定后直接下载订单，不读取或要求门户回复状态为“已回签”；待签章详情和正式详情均可继续。
- 订单号、详情页、明细行和下载按钮可见性，下载按钮/确认按钮各最多一次，非空文件与安全文件名，Artifact 先登记，附件查询幂等、冲突人工处理、上传最多一次及上传后查询确认边界均保持不变。独立运行 Task 3 时即使订单尚未回签也可能上传附件，调度方负责决定执行时机。
- 新增回归测试，以一个调用即抛错的 `verify_signed` 测试替身证明主流程不会读取回复状态且仍会继续下载和上传。质量门禁：pytest 21 项及 10 个子测试通过，Ruff 通过；Engine 五项包策略全部通过、0 警告。
- Artifact：`D:\AutoTask-Workspace\rpa-flows\rpa_flow_supplier_portal_upload_order_attachment\rpa_flow_supplier_portal_upload_order_attachment-1.0.1.zip`，9,667 字节，摘要 `sha256:8284930376c590b8138f2ef74495414b6217db3d582464595e6588ca02714f37`。ZIP 只含 `flow.py`、`manifest.json`、`selectors.json` 和中文 `README.md`，与源码逐字节一致。历史 `1.0.0` ZIP 摘要继续为 `sha256:8a587120a1db6b0d47eb68961a363675837c9529bf51ff5699eaf80a691b64fa`。
- Registry 首次上传创建不可变 Flow Version UUID `85a896c4-f2df-4683-b41a-073872cded46`。上传 Validation Run `8a668fd0-a8b1-4e6e-b596-8267d6b28c7a`、发布前 Validation Run `2aceff1f-345f-4788-bd22-ee88ef9ea7aa` 和发布后 Validation Run `8857f372-1bf2-40c9-b4eb-2d7635481670` 均为 `PASSED`，五项检查通过、0 错误、0 警告。
- `1.0.1` 最终状态为 `PUBLISHED`，发布时间 `2026-07-30T08:41:25.437235Z`；Registry 回读大小 9,667 字节、摘要与本地一致。以精确 UUID 和工作流代码 `srm_upload_order_attachment` 执行的绑定预检为 `valid=true`，返回相同 UUID 和摘要。
- 本次未修改现有 Task 3 Binding，未创建或运行 Task，未访问门户、下载订单或调用附件接口，也未连接数据库、执行 DDL/迁移、修改 Engine/Task/Client/UiPath 源码、提交或推送 Git。

#### 任务 3 Flow 1.0.1 待签章订单下载上传验证

- API 回读确认 Task 3 Binding `f2d686ff-cd1b-4d23-b6e9-6f60fed8b767` 已精确切换到 Flow `1.0.1` UUID `85a896c4-f2df-4683-b41a-073872cded46` 和摘要 `sha256:8284930376c590b8138f2ef74495414b6217db3d582464595e6588ca02714f37`，保持 `ENABLED`。队列为空且 Worker 在线空闲时，仅重试一次此前因 `ORDER_NOT_SIGNED` 失败的 Task `dd0b76b3-8cfe-4413-a478-b5dcc19a13b4`，未再次执行 Task 2 或点击签章。
- 新 Run `d789060d-dca3-4f99-92d8-65fbbb1c5bd8` 精确使用上述 `1.0.1` UUID，以 `SUCCESS` 完成登录、准确订单详情导航、稳定截图、订单下载、Engine Artifact 登记、附件上传前幂等查询、一次上传及上传后确认。
- 输出 Schema 为 `ORDER_ATTACHMENT_UPLOAD_OUTPUT_V1`：订单 `POJS2607130002`，源文件 `order_POJS2607130002.xlsx`，大小 4,931 字节，附件 ID `1`，上传人 `S01`，`uploaded=true`、`idempotent=false`。上传前匹配附件数为 0，事件确认只执行一次上传并完成结果回查。
- 下载 Artifact ID 为 `21faf9c1-b9dc-46ef-b1af-cbd5f51d4cf1`。本地只读下载验证文件为有效 XLSX，包含 `[Content_Types].xml` 和 `xl/workbook.xml`，共 9 个 ZIP 条目，SHA-256 为 `ec7d5869937a79e5a0525af5c771abbe46f0abb68cad7779b9e80f44b9634f36`。
- 本次证明 Task 3 可在待签章订单上独立完成下载和附件上传，但不代表 Task 2→Task 3 自动链已闭环：Task 2 仍因门户签章状态不持久化而无法产生符合 Mapper 要求的成功输出。本版本主动移除了 Task 3 的“已回签”业务门禁，正式调度必须由上游保证执行时机；门户持久化问题仍是待办。
- 验证结束后 Task 队列为空，Worker `ONLINE` 且当前任务数为 0。本次未修改 Engine、Task、Client 或 Flow 源码，未直接连接数据库或执行 DDL/迁移，也未重复签章或执行第二次附件上传。

#### Workflow Template 安全软删除

- Task 新增 `DELETE /api/v1/autotask/workflow-templates/{template_id}`，使用现有 `deleted_at` 执行软删除，不物理删除模板或历史版本。
- 仅允许删除未被引用的 `DRAFT` 或 `DISABLED` 模板；`ENABLED` 模板必须先禁用。存在当前 Binding 引用时返回 `409` 和“模板已被 Binding 引用，只能禁用”；存在历史任务引用时同样禁止删除。
- 删除操作写入 Workflow Template 审计事件；数据库结构和迁移保持不变，本次未连接数据库执行 DDL，也未删除任何真实模板。
- Client Workflow 详情页新增“删除模板”按钮和二次确认；启用中的模板按钮不可用，Task 返回 Binding、历史任务或状态冲突时显示明确中文原因。Mock API 同步实现相同约束。
- Task 专项删除测试 `7 passed`，本次修改文件 Ruff 和格式检查通过；全量测试 `73 passed, 1 failed`，唯一失败为既有 Portal 权限测试（接口当前返回 409、旧测试仍期望 403），全量 Ruff 另有 7 个既有问题。
- Client 全量单元测试 `57 passed`，TypeScript 与 Biome 检查通过。Task 已重启并验证健康检查为 HTTP 200、OpenAPI 已暴露 DELETE；仅以不存在的 ID 验证 404，不产生数据变更。
- Task 安全软删除改动已作为中文提交 `3288b94001ff23977d013c8c1e177d8618f4d548` 推送到 `YuweiSu529/nodeskclaw:v0.1`；Client 交互改动已作为中文提交 `5b47ace3fede3325c47af687f086207bffcb4c14` 推送到 `YuweiSu529/copilot-autotask:v0.1`。Client 本地 `.env.development` 和未跟踪 `AGENTS.md` 未修改、未纳入交付范围。

#### Task 与 Client Fork 分支交付

- 当前 GitHub 账号 `YuweiSu529` 对 `loudon84/nodeskclaw` 和 `loudon84/copilot-autotask` 只有 READ 权限，无法在原仓库创建或推送任何分支；新增原仓库分支不能绕过仓库级写权限。
- 已创建公开 Fork `YuweiSu529/nodeskclaw` 和 `YuweiSu529/copilot-autotask`，GitHub 回读确认它们的 parent 分别是对应的 `loudon84` 原仓库。
- Task/Backend `v0.1` 在原中文基线提交 `ace9b2a8970e708606ddfc6f69c4fd52a3ae1989` 之上新增并推送三个独立中文提交：`b49b355a`（任务 3 自动后继执行）、`d6ff8647`（本地 Engine 校验忽略系统代理）和 `3288b940`（流程模板安全软删除）。GitHub 远端最终 HEAD 已核对为 `3288b94001ff23977d013c8c1e177d8618f4d548`。
- Client `v0.1` 在原中文基线提交 `3c9c1de4ee0c3c9e3a51a2493a81833cef27adec` 之上新增并推送两个独立中文提交：`bd23f1b`（任务状态、近实时刷新和北京时间展示）和 `5b47ace`（流程模板安全删除）。GitHub 远端最终 HEAD 已核对为 `5b47ace3fede3325c47af687f086207bffcb4c14`。本地 `.env.development` 和未跟踪 `AGENTS.md` 未进入分支或推送。
- 推送前公开提交扫描未发现 `.env`、内网 IP、Token、私钥或运行产物。Task 候选文件 Ruff 和格式检查通过，专项 `47 passed`，全量 `81 passed, 1 failed`；唯一失败仍是既有 Portal 管理权限用例实际返回 409、旧断言期望 403。Client 本次 26 个候选文件 Ultracite 通过，忽略第三方声明后 TypeScript 通过，Vitest `57 passed`；全仓库仍有既有格式问题和第三方声明缺依赖问题。
- 原仓库尚未创建 PR、没有发生写入。`loudon84` 维护者可以公开查看两个 Fork 的 `v0.1`、添加 Fork remote 后 fetch/merge/cherry-pick，或通过跨 Fork PR 合并。

#### Client 北京时间与任务状态近实时刷新

- Client 新增统一的 `Asia/Shanghai` 展示格式，任务、审计日志、流程模板、Portal、运行记录、运行日志和 Artifact 的创建、更新、开始及结束时间均按北京时间显示；API/数据库时间原值和 DTO 契约不变。
- 远程模式下任务列表、任务详情、运行列表、任务运行记录和看板改为约 2 秒轮询，运行详情与事件日志保持约 1 秒轮询，并允许窗口位于后台时继续刷新；Mock 模式不启动轮询。
- 状态文案统一为“排队中”和“运行中”；当前执行队列同时包含 `QUEUED`、`LEASED`、`RUNNING`，避免领取租约后在界面短暂消失。
- 当前 Task/Client 没有 SSE 或 WebSocket 状态推送，因此这是最长约 2 秒延迟的近实时显示，不是服务端主动推送。后续若任务量增大，需要评估轮询负载并决定是否新增事件推送接口。
- 验证结果：本次候选文件 Ultracite 检查通过，忽略第三方声明后 TypeScript 类型检查通过，Vitest 13 个测试文件、57 项测试全部通过。未修改数据库、Task/Engine HTTP 接口或本地 endpoint 配置；相关改动已包含在中文提交 `bd23f1b` 并推送至 `YuweiSu529/copilot-autotask:v0.1`。

#### Client 后继任务“待填写”可见性

- 自动生成的交货日期任务继续保持正确的 `DRAFT` 状态；任务列表新增“待填写”页签并按 `DRAFT` 筛选，使任务 2 无需从“全部”中查找。
- 仅 `srm_update_expected_delivery_dates` 类型的 `DRAFT` 徽标显示为“待填写”，普通任务的 `DRAFT` 徽标仍显示“草稿”；任务列表和任务详情保持一致。
- 本次只修改 Client 展示，不改变 Task 状态机、后继任务处理器、数据库结构或 HTTP 接口。候选文件 Ultracite、TypeScript 检查及 Vitest 13 个测试文件、57 项测试通过；改动已包含在中文提交 `bd23f1b` 并推送至 `YuweiSu529/copilot-autotask:v0.1`。

#### 任务 2 首次运行失败诊断

- 自动创建的任务 2 已完整保存订单号、8 行订单明细和 8 个预计交货日期；最新 Run 在进入门户登录前以 `FLOW_INPUT_INVALID / Customer purchase order number is missing or invalid` 结束，未执行订单保存或签章。
- 根因位于 Flow `rpa_flow_supplier_portal_update_delivery_dates` `1.0.0`：`validate_input` 只接受原生 `dict`，而 Engine 按安全基线通过只读 `MappingProxyType` 提供 `ctx.input`。同一输入使用普通 `dict` 校验成功，使用 `MappingProxyType` 可稳定复现该错误。
- 修复应发布不可变新版本（建议 `1.0.1`），输入根对象改为接受 `collections.abc.Mapping`，并增加 Engine 真实 `RunContext`/只读 Mapping 回归测试；不得覆盖已经发布的 `1.0.0`。
- 当前订单已由人工填写日期并签章。新版本只有在门户已回签页面仍可读取、且门户八行日期与任务输入的 `2026-07-30` 全部一致时，才可走现有幂等成功路径而不再次保存或签章；日期不一致应保持 `WAITING_HUMAN / ORDER_ALREADY_CONFIRMED_CONFLICT`。正式重试前还需只读确认已回签订单详情路由仍可访问。
- 本次仅调用只读 Task API、读取 Run 事件/Artifact 元数据并执行本地输入复现；未重试 Task、未访问或修改门户订单、未修改 Flow/Engine/Task/Client 源码，未执行数据库操作。

#### 任务 2 Flow 1.0.1 兼容修复与发布

- 以已发布 `1.0.0` 为不可变基线新增 `1.0.1`；根输入和订单行输入均改为接受 `collections.abc.Mapping`，兼容 Engine 的 `MappingProxyType`，未放宽必填、行号唯一、物料匹配和日期格式校验。
- 订单搜索后改为点击结果“详情”，不再硬编码待签章详情路由；页面、订单号、明细表、回复状态和稳定检测同时兼容 `order-detail-*` 与 `pend-order-detail-*`。无法读取回复状态时在任何保存或签章前停止；已回签日期一致仍幂等成功，日期不同仍为 `WAITING_HUMAN / ORDER_ALREADY_CONFIRMED_CONFLICT`。
- 只读 DOM 复核发现 `POJS2607130002` 当前已被同事调整为“待签章”，有 8 行且预计交货日期为空；另选真实“已回签”订单验证正式详情页，其页面不显示预计交货日期列且没有保存或签章按钮。因此当正式详情页无法提供日期证据时，Flow 会安全返回人工处理，不会重复签章。本次未对任何订单执行保存、签章或其他门户写操作。
- 质量门禁通过：pytest 35 项及 11 个子测试通过；Ruff `E/F/I/B/UP/ASYNC` 与格式检查通过；Python 语法、JSON 和 UTF-8 检查通过；Engine 本地包校验通过。上传 Validation Run `84bb3e9c-7105-4daf-bcaf-80d4a54e9925` 与发布前手动 Validation Run `2d12b31a-eb19-4f38-a701-28b39f9b6e0a` 均为 `PASSED`，五项策略检查通过、0 错误、0 警告。
- Artifact：`D:\AutoTask-Workspace\rpa-flows\rpa_flow_supplier_portal_update_delivery_dates\rpa_flow_supplier_portal_update_delivery_dates-1.0.1.zip`，大小 10,432 字节，摘要 `sha256:3f851fae62424d100cfe40248ece795d3047a1f23ef8d5fb84d9ad6e7320a735`；Registry 回读包字节与本地一致，只包含 `flow.py`、`manifest.json`、`selectors.json` 和中文 `README.md`。
- `1.0.1` 已发布，Flow Version UUID 为 `c903b202-eb71-4036-82ee-33dc72ca8823`，状态 `PUBLISHED`；原 `1.0.0` UUID `6f40900b-b037-4abf-8010-81849478bbe7` 与摘要保持不变，未覆盖。复用既有健康 Engine；未修改 Task Binding、创建或运行 Task、连接数据库、执行 DDL/迁移，也未修改 Engine、Task、Client 或 UiPath 源码。

#### 任务 2 Flow 1.3.0 演示兼容版与任务 2→3 自动闭环验证

- 根据用户对演示联调的明确授权，保持严格持久化复核版本 `1.2.0` 不变，新建不可变演示兼容版本 `rpa_flow_supplier_portal_update_delivery_dates` `1.3.0`。日期完整覆盖、料号匹配、页面填值校验、签章只点击一次、拒绝/超时/未知结果停止等边界保持不变；只有门户提示同时包含“签章成功”和“已回签”时才返回成功。
- `1.3.0` 不再在签章成功提示后刷新页面验证状态和日期持久化。成功输出继续兼容 `ORDER_DELIVERY_CONFIRMATION_OUTPUT_V1`，并新增 `verificationMode=ACTION_CONFIRMATION_ONLY`、`persistenceVerified=false` 明确标识。该版本仅用于当前演示链路，不得作为门户已完成持久化或生产可靠性的证据；严格场景继续使用 `1.2.0`，门户持久化缺陷仍是待办。
- 质量门禁通过：pytest 32 项及 11 个子测试通过，Ruff 通过，Engine 本地包策略校验通过。ZIP 为 `D:\AutoTask-Workspace\rpa-flows\rpa_flow_supplier_portal_update_delivery_dates\rpa_flow_supplier_portal_update_delivery_dates-1.3.0.zip`，8,060 字节，摘要 `sha256:e214be3277e3330b93fae8e4fccefe8729ee70254fedda691950538e072ec986`。
- `1.3.0` 已上传、复核并发布，Flow Version UUID 为 `72a076d1-2f6e-4558-9c10-56ad9d506d78`，Registry 摘要与本地一致。Task 2 Binding `029be39f-b84c-4dd7-8d0b-7f66ad2e5dd4` 已精确切换到该 UUID/摘要，继续 `ENABLED`，原 `ORDER_ATTACHMENT_UPLOAD_V1` successor 和目标 Task 3 Binding `f2d686ff-cd1b-4d23-b6e9-6f60fed8b767` 保持不变。
- 队列为空时只创建并启动一次 Task 2：Task `d8b16802-42ef-48b5-adca-48b6bdfe7baf`、Run `7acfb795-4c07-4dce-a228-084a764601ab` 完成八行日期填写、单次签章和演示确认，以 `SUCCESS` 结束。输出明确保留 `persistenceVerified=false`；登记签章前和动作接受后两张 PNG Artifact。
- successor job `bdbd33ad-1f82-4aa2-8dff-e6fe2919e8dc` 首次处理即 `SUCCEEDED`，自动创建并排队 Task 3 `397fd19a-7fbc-432c-a623-49b9b42315a0`，来源 Task/Run 关联正确，输入映射为 `{"po_no":"POJS2607130002"}`。Task 3 Run `6b571ccb-3637-4404-94e9-9a4853ed928e` 精确使用 Flow Version UUID `85a896c4-f2df-4683-b41a-073872cded46`，完成登录、订单定位、XLSX 下载和附件预检后以 `SUCCESS` 结束。
- Task 3 登记 4,931 字节 `order_POJS2607130002.xlsx` 和下载前截图。门户附件查询发现相同附件 ID `1` 已存在，因此按设计返回 `uploaded=false`、`idempotent=true`，没有重复执行附件上传 POST；本次证明自动后继、自动 lease、下载与幂等收口链路可运行，不代表新附件上传分支再次写入成功。
- 验证结束后 Task `QUEUED=0`、`RUNNING=0`，Worker `server-worker-phase5-integration` 为 `ONLINE` 且无当前 Run，Engine readiness 的数据库、对象存储、Task API 和 Runtime 文件系统均为 healthy。本次未直接连接数据库，未执行 DDL、迁移或种子，未自动重试门户写操作，也未提交或推送源码。

#### 任务 1 POJS2607170001 失败诊断

- 任务 `31c87ec6-b88e-4ac7-9947-065666ffec66`、Run `3eaea786-19f9-4e9f-bd74-8250b85cc1f0` 精确使用已发布的任务 1 Flow `1.2.1`（UUID `e08059db-f55b-48e8-bbab-e33909f33b7d`）。登录、订单详情定位、XLSX 下载和 3 行解析均成功，随后以 `FAILED / ORDER_ATTACHMENT_PO_MISMATCH` 停止，没有进入 ERP 调用。
- 使用同一版本 Flow 的解析器只读复核 9,840 字节 Artifact `order_POJS2607170001.xlsx`：第 10 行和一个第 30 行属于 `POJS2607170001`，另一个第 30 行却属于 `POJS2607130002`。因此文件内订单号集合不是请求订单的单一集合，Flow 的防串单校验正确拒绝继续。
- 根因属于供应商门户下载文件的数据生成/隔离问题，而非 Engine lease、Binding 版本或 ERP 映射问题。修复前不得移除订单号一致性校验或重试该任务；应先让门户针对 `POJS2607170001` 生成只包含该订单明细且行号唯一的 XLSX，再创建新任务验证。本次仅执行只读 API、Artifact 和 Flow 解析检查，未重试任务、修改门户或调用 ERP。

#### 待签章未发货订单附件只读盘点与演示兼容建议

- 只读登录供应商门户并盘点当前首页全部 6 张“待签章 + 未发货”订单；逐张进入详情、下载浏览器临时附件并用任务 1 解析器比对门户详情的“行号 + 料号”。全程未填写日期、未点击签章、未启动 Task、未调用 ERP 或附件上传接口。
- `POJS2607130002`（8 行）、`POJS2607180002`（2 行）、`POJS2607190003`（3 行）、`POJS2607200004`（2 行）和 `POJS2607240005`（3 行）的当前附件均只包含目标订单，且与门户详情逐行完全一致、行号唯一，可作为演示候选；其中 `POJS2607180002` 和 `POJS2607200004` 行数最少，更适合短时演示。
- `POJS2607170001` 的当前门户详情为 3 行；附件同样有 3 行，其中第 20 行的料号与门户详情一致，但附件订单号误写为 `POJS2607130002`。这不是重复行，而是单字段串单。历史 Artifact 与当前门户重新下载内容并不一致，说明测试门户附件内容曾发生变化，演示前必须重新预检。
- 额外检查的 `POJS2606030010` 当前为“待回签 + 未发货”，附件只有 1 行且料号与门户详情的 2 行均不匹配，不适合任务 1→任务 2 演示。
- 建议不要取消全部数据校验，也不要简单按附件订单号过滤。任务 1 应发布新的演示兼容版本：先读取当前详情行，以唯一的“行号 + 料号”与 XLSX 做双向一一匹配；集合完全一致后才将各行 `poNo` 规范化为任务输入 `po_no`，并只把规范化结果传给 ERP 和 Task 后继输出。缺行、多行、重复行或料号不一致仍必须失败。这样可安全兼容 `POJS2607170001`，同时避免把其他订单行推送到 ERP。
- 新版本发布并精确切换 Binding 后，应选择一张尚未执行的两行干净订单做一次完整任务 1→待填写任务 2 预演；旧 `1.2.2` 成功 Run 已可能把错误订单号传给 ERP，不应通过重跑或放宽 Task 后继映射继续使用，应按测试数据单独核实或废弃。

### 2026-07-30#### Task 1 剩余 ERP 映射就绪

- 业务侧确认第 60 行客户料号 `1B.30040.020259` 和第 70 行客户料号 `1B.30040.020256` 的 ERP 测试环境映射已经建立。
- 当前状态为“业务侧已确认、尚待完整八行 Task 验证”；本次没有启动 Task、请求 ERP OAuth 或调用 ERP 导入接口，也未修改 Flow、Binding、Engine、Task、Client 或 UiPath 源码。
- 下一步在用户明确授权后，只执行一次完整八行 Task 1 受控复测，并继续沿用测试环境允许重复订单、单次调用且结果不明时停止的边界。
### 2026-07-29

#### 供应商门户 ERP 订单推送 Flow（任务 1）1.2.0

- 以 `rpa_flow_supplier_portal_prepare_erp_order` `1.1.1` 为基线新增不可变版本 `1.2.0`；Flow ID、工作流代码 `srm_prepare_erp_order`、输入 `po_no`、Playwright/XLSX/ERP 写入步骤和行级业务成功判定均保持不变，任务 2 的预计交货日期 Flow 未修改。
- ERP 业务成功后只返回冻结契约 `ORDER_DOWNLOAD_PUSH_OUTPUT_V1`：`schemaVersion`、`poNo`、ERP `orderNumber`、`supplierCode`、`supplierName`、`lineCount` 和 `lines`。`lines` 按 XLSX 原顺序返回完整解析业务记录以及已计算的 `taxRate`、`unTaxPrice`；成功返回明确禁止 `draft`、`draftOnly`、`transmitted`、`orderDetail`、`erpPayload`、`erpResponse` 和任何凭据字段。
- 同一订单摘要也写入 `ERP_ORDER_IMPORT_SUCCEEDED` 成功事件。原因是当前 Engine Runtime 只使用 Flow 抛出的异常判断状态，不传播 Python 返回值；现阶段 Task/Run 通过事件查看订单号、供应商和逐行明细。
- ERP 响应仍必须满足顶层成功、至少一个结果行、每行 `processStatusCode=COMPLETE` 且订单号非空；成功摘要还要求所有结果行解析为同一个 ERP 订单号。多个不同订单号映射为 `WAITING_HUMAN / ERP_ORDER_IMPORT_OUTCOME_UNKNOWN`，不得静默选择或自动重推。
- `supplier-portal-erp-draft-prepared` 截图新增稳定门禁：下载确认弹窗消失、详情页和明细可见、加载遮罩消失、字体和可见图片加载完成、布局连续两次一致，最后再等待约 300ms。单元测试同时验证各门禁顺序以及 `_prepare_erp_order` 必须先稳定再截图。
- 测试改用 `importlib` 根据 `tests/test_flow.py` 的绝对父路径加载 Flow，不再依赖当前工作目录。从 Flow 版本目录和 Engine 根目录验证均通过：pytest 34 项及 10 个子测试通过；Ruff `E/F/I/B/UP/ASYNC` 与格式检查通过；Python 编译检查通过；Engine 包校验 5 项通过、0 警告。README 已改为中文且不重复具体内网 ERP 地址；凭据值未写入日志或本文档。
- Artifact：`D:\AutoTask-Workspace\rpa-flows\rpa_flow_supplier_portal_prepare_erp_order\rpa_flow_supplier_portal_prepare_erp_order-1.2.0.zip`，大小 14,265 字节，摘要 `sha256:49b3a6f010e1a7f5b7ddcf64daa10544a22f5f1d383ae6a289ac86de50ed81cd`。ZIP 与当前四个源文件逐字节一致，只包含 `flow.py`、`manifest.json`、`selectors.json` 和中文 `README.md`；Engine 根目录 Ruff 自动排序前的摘要 `sha256:507ef8818bfe9a4cfc2882c3f6e7ebdb2a9d7d1665730154d4b9caa3e03405d0` 以及更早候选摘要均已废止。
- 本次仅通过无界面 Chrome 只读打开门户并确认订单详情、明细表、弹窗和加载遮罩选择器；未下载附件、未请求 OAuth Token、未调用 ERP 导入接口，未上传、未校验 Registry、未发布、未创建或运行 Task，也未连接数据库或修改 Engine、Task、Client、UiPath 源码。
- 后续行动：先修正或确认 ERP 测试客户料号与物料编码映射及已有订单状态；再上传、校验、发布准确的 `1.2.0` 包，以返回的 UUID 和摘要更新 Task 1 Binding，并执行一次不自动重试的受控闭环测试。

#### Engine 0.6.0 结构化输出与 Task 后继任务契约

- Engine 已升级至 `0.6.0`：Runtime 接收 Flow `run(ctx)` 返回的 `dict | None`，执行严格 JSON、非字符串键、敏感字段名和默认 1 MiB 上限校验；非法输出分别以 `FLOW_OUTPUT_INVALID` 或 `FLOW_OUTPUT_TOO_LARGE` 终止且不重试。成功输出通过 Worker finish 与现有 Callback Outbox 可靠传递，不写日志。
- Task 伴随改造代码已准备：`rpa_runs.output` 保存成功输出，`automation_tasks` 增加来源 Task/Run 链接，并新增 `task_successor_jobs` 可靠作业表。来源 Binding 通过 `successor` 配置指定同租户、同 Portal、已启用且带精确版本快照的任务 2 Binding；任务 1 成功后持久化后继作业，处理器将 `ORDER_DOWNLOAD_PUSH_OUTPUT_V1` 映射为任务 2 的 DRAFT 输入，预计交货日期保持空值，由用户填写后才能启动。
- Task 新增 `GET /api/v1/autotask/tasks/{task_id}/successors` 和 `POST /api/v1/autotask/tasks/{task_id}/successors/{job_id}/retry`；任务输入只允许在 DRAFT/READY 修改，进入队列后不可变，任务 2 启动前校验每行唯一行号、物料号及合法 `YYYY-MM-DD` 日期。
- dormant Alembic revision 为 `7c1f4d8e2a90`，当前是唯一 Head；本次未连接数据库、未执行迁移/DDL/种子、未启用后继处理器，也未上传或发布任务 1/任务 2 Flow。上线前必须先备份并执行/验证迁移，再发布两个精确 Flow 版本、更新 Binding，并设置 `SUCCESSOR_JOB_ENABLED=true`。
- 验证结果：Engine pytest 223 项、Ruff、mypy（58 个源码文件）和 `pip check` 全部通过；Task 非数据库 pytest 64 项通过、1 项既有 Portal 权限测试排除，本次变更文件 Ruff 通过，迁移链验证通过。数据库集成测试须在迁移获授权并应用后补跑；Task 仓库现有 Portal 创建权限断言仍需 Task 团队处理。

#### Task 1 与 Task 2 Flow Registry 发布

- 发布前重新校验两个本地 ZIP：Task 2 `rpa_flow_supplier_portal_update_delivery_dates` `1.0.0` 摘要为 `sha256:2744644f41a02b51095fc0fc91768ffbb6e7ad0171da2a474b27ada5b56bc657`，Task 1 `rpa_flow_supplier_portal_prepare_erp_order` `1.2.0` 摘要为 `sha256:49b3a6f010e1a7f5b7ddcf64daa10544a22f5f1d383ae6a289ac86de50ed81cd`；两包均为 Engine 5 项策略检查通过、0 警告。
- Task 2 Flow 首次上传后重新校验并发布。不可变 Flow Version UUID 为 `6f40900b-b037-4abf-8010-81849478bbe7`，上传校验 Run 为 `4a59661c-59a8-4873-8818-166f90394701`，发布前复核 Run 为 `7d8bd2d5-63a6-4d71-8058-41c24a5a3e30`，最终状态为 `PUBLISHED`。
- Task 1 Flow `1.2.0` 首次上传后重新校验并发布。不可变 Flow Version UUID 为 `04bf1c98-2971-4ad1-a48a-d2554a4e1df0`，上传校验 Run 为 `33b1f750-e61e-4c53-99a7-94e52a6cc8c0`，发布前复核 Run 为 `bb4a5d83-d4c9-4ba5-99d0-76be83f5090e`，最终状态为 `PUBLISHED`。
- 发布后通过 Flow Version API 逐项回读，确认两个版本的 Flow ID、版本号、`PUBLISHED` 状态、包大小、工作流代码、能力及 Registry 摘要均与本地包一致。
- 最终交付复验再次对两个已发布版本执行手动校验：Task 2 Validation Run `45591dd0-82d5-47a5-8854-678bdb789e91`、Task 1 Validation Run `6755e769-e161-4707-a201-89d103207ccb` 均为 `PASSED`；回读状态继续为 `PUBLISHED`，摘要未变化。
- 发布服务复用发布前已运行且 readiness 健康的 Engine。最终核对时曾启动一个关闭 Worker/Runtime 的 Registry-only 候选进程，但端口已由既有 Engine 占用，候选进程随即停止；既有 Engine 未被停止或替换。未修改 Task 1 现有 Binding，未为 Task 2 创建 Binding，也未创建或运行 Task、调用门户、OAuth 或 ERP。未执行直接 SQL、DDL、迁移、Git 提交或 Git 推送。

#### 本地 Task 后继任务闭环启用验证

- 本地 Task1 Binding `7da19fa0-86ac-4d4a-b68e-30c0f651f5ae` 已配置 `ORDER_DELIVERY_CONFIRMATION_V1`，精确指向同 Portal 的 Task2 Binding `029be39f-b84c-4dd7-8d0b-7f66ad2e5dd4`；两者均为 `ENABLED` 且 Flow UUID/checksum 快照完整。
- 仅对本机 `127.0.0.1:5432/nodeskclaw_task_local` 执行 Alembic `00a7cf21c89d -> 7c1f4d8e2a90`。迁移前备份为 `D:\tmp\nodeskclaw_task_local-pre-successor-20260729-113516.dump`，SHA-256 `70791650CCF2CF5DE73114F05DD602918A7114460D87F1FDDE4366671E0279BD`；未访问测试数据库。
- 本地 Task `.env` 已设置 `SUCCESSOR_JOB_ENABLED=true` 并重启，启动日志确认后继作业处理器运行；OpenAPI 已暴露后继作业列表/人工重试接口，Run finish 与 Run response 均包含结构化 `output`。
- Engine 已重启为 `0.6.0`，readiness 全部健康；`server-worker-phase5-integration` 为 `ONLINE`，版本 `0.6.0`，lease 正常轮询。Task1 `1.2.0` 与 Task2 `1.0.0` 的精确 Binding 校验均为 `valid=true` 且 UUID 与已发布版本一致。
- 当前没有 `QUEUED/LEASED/RUNNING` Run，`task_successor_jobs` 为空；本次未创建或启动真实 Task，未触发供应商门户、ERP 导入、预计交期保存或签章写操作。下一步须由业务方确认用于受控测试的 `po_no` 后，再执行完整端到端闭环。

#### Client 任务 2 交货日期明细编辑表格

- Client 对工作流代码 `srm_update_expected_delivery_dates` 增加专用任务详情编辑器。任务 1 生成的 `order_lines` 以明细表展示行号、物料号、物料名称/规格、数量、需求日期、标准交期，并为每行提供日期控件维护 `expected_delivery_date`；同时展示采购订单、ERP 订单和供应商摘要。
- 编辑器仅在任务状态为 `DRAFT` 或 `READY` 时允许修改，进入 `QUEUED` 及后续状态后只读。允许分次保存未填完的草稿；每次更新都保留任务输入的其他顶层字段和每条明细原始字段，只替换预计交货日期。任务启动前的完整性和合法日期校验仍由 Task 服务执行，未绕过服务端门禁。
- 轮询返回相同服务端输入时不会覆盖用户尚未保存的本地日期；服务端输入实际变化后才重新装载。保存成功后刷新 Task 缓存，失败通过现有通知组件反馈。
- 变更文件为 `src/features/tasks/delivery-date-task-model.ts`、`src/features/tasks/delivery-date-task-editor.tsx`、`src/features/tasks/task-detail.tsx` 和 `src/tests/unit/delivery-date-task-editor.test.tsx`。相关文件 Biome 检查 0 错误，新增 5 项测试通过，Client 全量 Vitest 30 项通过，应用源码 `tsc --noEmit --skipLibCheck` 通过，Electron Forge Windows x64 生产打包成功。
- 仓库级 `ultracite check` 仍被 385 条既有诊断阻断，主要是历史文件 CRLF/格式差异；裸 `tsc --noEmit` 仍被 Electron Forge、Radix 等第三方声明缺失或冲突阻断。本次相关文件定向检查和生产构建均已通过，没有批量改写无关文件。
- 本地 Task `/health` 与 Engine `/health/ready` 均返回 200，桌面端开发进程已重新启动。本次未创建、更新或运行真实 Task，未写数据库、门户、ERP 或对象存储。

#### Client 任务 2 手工创建输入修复

- 定位到旧的新建任务表单忽略 WorkflowTemplate 字段类型，把 `order_lines` 数组字段渲染为普通文本框。用户输入行号 `10` 后，Task 实际保存为字符串 `"order_lines":"10"`，因此任务详情无法生成明细表；Engine、Task 后继作业和 Flow 契约没有参与该错误。
- 新版表单对 `srm_update_expected_delivery_dates` 提供可增删的订单明细输入，每条要求精确填写订单行号和物料号，创建时序列化为 `order_lines` 对象数组并将 `expected_delivery_date` 初始化为空；空列表、缺字段和重复行号会在提交前被阻止。正常生产路径仍推荐先运行任务 1，由后继机制自动生成全部订单行。
- 已经以字符串创建的错误任务不会被静默猜测或自动修复，详情页会提示取消后重新创建，或通过任务 1 自动生成。原因是只凭行号无法恢复完整物料号和订单明细，自动补值可能导致任务 2 对错误订单行执行门户写入。
- 相关文件定向 Biome 和应用源码类型检查通过；Client 全量 Vitest 32 项通过，Electron Forge Windows x64 生产打包成功。打包期间开发版 Vite 监听到 `out` 目录并因 Windows 文件锁退出，完成后已重新启动桌面端，最终 Electron/Node 进程运行正常。
- 本次只用只读事务确认本地错误任务的输入形态，没有更新 Task、执行 Run、写数据库或访问供应商门户。
- 后续复测确认新版表单创建的任务已在数据库中正确保存 `order_lines` 数组，但 Client 通用 DTO 映射仍递归地把业务载荷键改成 `orderLines/lineNumber/materialNumber`，导致详情编辑器按冻结 Flow 契约读取 snake_case 时再次误判为空。现已调整 DTO 映射：API 外层字段继续转换为 Client camelCase，`input` 内的 Flow 业务载荷原样保留。
- 新增业务输入键保留回归测试；DTO、任务 2 编辑器和新建表单相关定向检查及应用源码类型检查通过，Client 全量 Vitest 更新为 33 项全部通过。Vite 已热更新任务详情和新建任务页面，不需要再次创建当前格式正确的 DRAFT 任务。

#### Task 1 待签章订单详情兼容性失败诊断

- 本地 Task `mock任务1` 对订单 `POJS2607130002` 的 Run 已结束为 `FAILED`。登录成功、订单列表搜索成功且详情按钮点击成功；Trace 证明页面进入 `/#/supplier/pend-orders/{po_no}`，目标订单存在并包含 8 条明细。
- Flow `rpa_flow_supplier_portal_prepare_erp_order` `1.2.0` 只等待普通详情页 `order-detail-*` 选择器，而待签章详情页使用 `pend-order-detail-*`。因此首次执行在正确页面等待错误选择器 15 秒，抛出 `ORDER_DETAIL_UNAVAILABLE`。
- Engine 默认对可重试错误重新执行整个 Flow 两次，但复用同一个已登录浏览器页面。后续重试仍从登录步骤开始，在 Dashboard 等待登录页验证码元素并分别超时，最终 Run 表面错误被覆盖为 `RUNTIME_TIMEOUT`。对会执行 ERP 外部写入的 Flow，整段自动重试还存在重复提交风险，受控环境应将 Runtime 自动重试设为 0，重试由新 Run 和明确业务幂等策略控制。
- 本次 Run 只保存 `failure.png` 和 `trace.zip`，没有订单 XLSX、ERP 成功事件、结构化输出或后继作业，未创建任务 2。修复前不得直接重试。
- 后续需发布不可变的新 Task 1 Flow 版本：同时兼容普通详情页和待签章详情页的页面、订单号、明细表及下载按钮选择器；登录步骤须兼容已登录状态或明确从干净会话重试。更新精确 Binding 后，再以关闭 Runtime 自动重试的方式执行一次新 Run。

#### 供应商门户 ERP 订单推送 Flow（任务 1）1.2.1

- 以已发布 `rpa_flow_supplier_portal_prepare_erp_order` `1.2.0` 创建新的不可变补丁版本 `1.2.1`；Flow ID、工作流代码、`po_no` 输入、XLSX 映射、ERP 请求、业务结果判定和冻结成功输出契约均未改变。
- 详情页选择器现同时覆盖普通订单详情和待签章订单详情的页面标识、订单号、明细表及下载按钮。订单列表进入 `/#/supplier/pend-orders/{po_no}` 时会使用 `pend-order-detail-download-btn`，仍经过同一下载确认、XLSX 安全解析、订单号一致性和 Artifact 流程。
- 登录步骤新增统一就绪门禁；Runtime 复用已登录浏览器时可识别 Dashboard 并继续，不再错误等待验证码元素。该兼容不改变 ERP 幂等边界，受控运行仍必须关闭整段自动重试。
- 真实 Mock 门户只读验证通过：订单 `POJS2607130002` 正确进入待签章详情路由，下载 `order_POJS2607130002.xlsx` 并解析出 8 行，行号为 10 至 80，全部订单号一致。本次未点击预计交期保存、逐行保存或签章，也未请求 OAuth Token、调用 ERP 或产生业务写入。
- 质量验证通过：从 Engine 根目录运行 pytest 37 项及 10 个子测试通过；Ruff `E/F/I/B/UP/ASYNC`、Ruff 格式检查和 Python 编译检查通过；Engine 包校验 5 项通过、0 警告。
- Artifact：`D:\AutoTask-Workspace\rpa-flows\rpa_flow_supplier_portal_prepare_erp_order\rpa_flow_supplier_portal_prepare_erp_order-1.2.1.zip`，大小 14,732 字节，摘要 `sha256:09d80f200d7164d4088a3e0c9eeacada322190379cd788bd40d90aca87353d51`。ZIP 与当前源文件逐字节一致，只包含 `flow.py`、`manifest.json`、`selectors.json` 和中文 `README.md`；Ruff 根目录分类修正前的候选摘要 `sha256:c19d91c763cdd508b144e5afbfa95fa24b601c75113a051158600fd072f17b91` 已废止。
- `1.2.1` 已上传、重新校验并发布。不可变 Flow Version UUID 为 `e08059db-f55b-48e8-bbab-e33909f33b7d`；上传 Validation Run `95c2c969-aeb0-47c8-9997-39633f6fcb23` 与发布前手动 Validation Run `97d2899c-a9ee-4324-acbe-3f87ed50ac32` 均为 `PASSED`，最终状态为 `PUBLISHED`，发布时间 `2026-07-29T06:13:09.682524Z`。以 UUID 和工作流代码 `srm_prepare_erp_order` 执行的 Binding 预检为 `valid=true`。
- 本次未修改 Task Binding、创建或运行 Task、连接数据库、执行 DDL/迁移，也未修改 Engine、Task、Client、UiPath 源码或提交 Git。下一步为精确更新 Binding，并在确认 ERP 测试数据后执行一次关闭自动重试的受控新 Run。
- 后续联调中，用户通过 Postman 仅提交订单 `POJS2607130002` 第 10 行并成功生成 ERP 订单 `10408260700003`。该请求只包含客户料号 `1B.30040.020262`，且数量、单价和需求日期来自旧 Mock 数据；它不是 Flow 从当前订单专属 XLSX 生成的完整请求。
- 当前订单专属 XLSX 实际包含 8 行。除第 10 行外，Flow 还会提交第 20 至 80 行客户料号 `1B.30040.020255`、`1B.30040.020257`、`1B.30040.020260`、`1B.30040.020258`、`1B.30040.020259`、`1B.30040.020256`、`1B.30040.020261`。Task 重试仍返回“系统中查找客户料号与物料编码出错”，说明至少一个其余料号尚未建立有效映射，或映射未在该客户/业务实体组合下生效。
- 因 Postman 已创建一张仅含第 10 行的 `BOOKED` ERP 订单，继续重试完整 Flow 之前必须先由 ERP 侧核实或清理该订单，并通过主数据查询逐项确认全部 8 个料号映射；不得用逐行导入试探映射，以免继续创建不完整 ERP 订单。本次 Codex 只读下载并解析 XLSX，没有调用 OAuth 或 ERP 导入接口。

#### Task 1 Flow 1.2.1 受控运行：ERP 行级业务失败

- Task `935782a4-0f8d-411e-9514-275eff7e2a40`、Run `8ea19f8e-77a9-4e1c-8186-fb681171e759` 的 Trace 快照精确使用 Flow `1.2.1` 和摘要 `09d80f200d7164d4088a3e0c9eeacada322190379cd788bd40d90aca87353d51`。
- 登录、待签章详情、订单专属 XLSX 下载、8 行解析、稳定截图、ERP OAuth 与导入请求均完成；Artifact 包含非空 XLSX、准备截图、失败截图和 Trace，租约、事件与 finish 回调闭环。
- ERP 返回行级 `processStatusCode=ERROR`，消息为客户料号与物料编码匹配失败；Flow 按 `ERP_ORDER_IMPORT_ROW_FAILED` 将 Task/Run 标记为 `FAILED`。这是 ERP 测试主数据业务失败，不是 Portal、XLSX、OAuth、网络或 Flow 执行器故障。
- XLSX 包含供应商编号 `02556` 的 8 行客户料号，行号 10 至 80。ERP 响应未指出具体失败行；需由 ERP 管理员逐项核对映射。修复并确认未生成订单前不得重复运行。
- 本次诊断未重跑 Task、未修改 Flow/Binding/Engine/Task/Client/UiPath 源码，未连接数据库或执行 DDL；Engine 保持运行。

#### Task 1 Flow 1.2.1 单次重试：ERP 映射仍失败

- 经用户确认重新尝试后，使用本地 Backend 账号登录取得短时 JWT，对现有 Task `935782a4-0f8d-411e-9514-275eff7e2a40` 只调用一次 `/retry`；调用前确认没有 `QUEUED`、`LEASED`、`RUNNING` 或 `WAITING_RETRY` 任务，Engine `0.6.0` readiness 健康且 Worker 空闲。
- Binding `7da19fa0-86ac-4d4a-b68e-30c0f651f5ae` 仍精确指向已发布 Flow `1.2.1`、UUID `e08059db-f55b-48e8-bbab-e33909f33b7d` 和摘要 `09d80f200d7164d4088a3e0c9eeacada322190379cd788bd40d90aca87353d51`；Engine 绑定预检为 `valid=true`。
- 新 Run `8496dbf3-f5a5-42cd-bb68-9c3a62ff8b88`、Lease `16ba201a-2d93-4c3d-a88f-ac859ee13021` 由 Worker `server-worker-phase5-integration` 执行。登录、待签章详情、8 行 XLSX 下载与解析、稳定截图、ERP OAuth 和一次 ERP 导入请求均完成。
- ERP 返回 `processStatusCode=ERROR`、`processGroupId=1785316055390`，业务消息仍为客户料号与物料编码匹配失败；Flow 以 `ERP_ORDER_IMPORT_ROW_FAILED` 结束，Task 和 Run 均为 `FAILED`，没有结构化成功输出，也没有创建任务 2 后继作业。
- 本次 Run 的 Artifact 已登记：`order_POJS2607130002.xlsx` 4,931 字节、`supplier-portal-erp-draft-prepared.png` 148,506 字节、`failure.png` 148,506 字节、`trace.zip` 4,894,263 字节。结束后 Worker 继续 `ONLINE` 且任务数、浏览器数均为 0，队列为空。
- 未自动执行第二次重试，未修改 Flow、Binding、Engine、Task、Client 或 UiPath 源码，未连接数据库或执行 DDL；在 ERP 能指出具体失败行并确认全部 8 个客户料号对当前客户/业务实体有效前，继续重试仍可能得到相同结果。
#### Task 1 ERP 逐行映射诊断

- 经用户明确允许产生一张重复的不完整 ERP 订单，直接复用 Task 1 Run `8496dbf3-f5a5-42cd-bb68-9c3a62ff8b88` 的 4,931 字节 XLSX Artifact，并使用 Flow `1.2.1` 原解析与报文构造逻辑，对订单 `POJS2607130002` 的八行进行单行请求诊断；未重新运行 Task。
- 已知第 10 行此前通过 Postman 成功，因此先对第 20 至 80 行各调用一次 ERP 导入接口。七行全部明确返回 `ERP_ORDER_IMPORT_ROW_FAILED`，且 `orderNumber`、`headerId` 为空：第 20 行 `1B.30040.020255`，processGroupId `1785316620781`；第 30 行 `1B.30040.020257`，`1785316620929`；第 40 行 `1B.30040.020260`，`1785316621091`；第 50 行 `1B.30040.020258`，`1785316621243`；第 60 行 `1B.30040.020259`，`1785316621396`；第 70 行 `1B.30040.020256`，`1785316621548`；第 80 行 `1B.30040.020261`，`1785316621696`。
- 随后按用户授权，以当前 XLSX 的真实第 10 行数据提交一次：客户料号 `1B.30040.020262`、数量 `48640`、含税单价 `96.9727`、需求日期 `2026-07-20`。ERP 返回 `COMPLETE` 并生成 `BOOKED` 订单 `10408260700006`、headerId `1097964`、processGroupId `1785316660797`。
- 诊断结论：第 10 行客户料号映射有效；第 20 至 80 行七个客户料号映射全部无效或未在当前客户/业务实体组合下生效。完整八行 Task 失败不是 Flow 报文结构、OAuth 或第 10 行数据导致。
- 本次共执行八次单行 ERP 导入请求，无超时或结果不明确；七次明确业务失败、一次明确成功。未重试任何单行请求，未修改 Flow、Binding、Engine、Task、Client 或 UiPath 源码，未连接数据库或执行 DDL。ERP 侧需处理本次及此前 Postman 生成的两张第 10 行不完整订单。

#### 2026-07-30

#### Task 1 剩余 ERP 映射就绪

- 业务侧确认第 60 行客户料号 `1B.30040.020259` 和第 70 行客户料号 `1B.30040.020256` 的 ERP 测试环境映射已经建立。
- 当前状态为“业务侧已确认、尚待完整八行 Task 验证”；本次没有启动 Task、请求 ERP OAuth 或调用 ERP 导入接口，也未修改 Flow、Binding、Engine、Task、Client 或 UiPath 源码。
- 下一步在用户明确授权后，只执行一次完整八行 Task 1 受控复测，并继续沿用测试环境允许重复订单、单次调用且结果不明时停止的边界。
### 2026-07-29 每日代码提交整理

- Engine `v0.1` 已形成中文本地提交 `3ea8b1220a2161ee1bbfe98f2a7d4163f7618bfd`（`feat(engine): 支持 Flow 结构化输出回传`），相对 `origin/v0.1` 领先 1 个提交。验证结果为 Ruff、58 个源码文件 mypy、pytest 223 项及 `pip check` 全部通过。
- Task/Backend `main` 已形成中文本地提交 `ace9b2a8970e708606ddfc6f69c4fd52a3ae1989`（`feat(task): 增加 RPA 后继任务可靠生成机制`），相对 `origin/main` 领先 1 个提交。Task 相关 Ruff 通过，pytest 66 项通过、1 项既有 Portal 权限断言按已知问题排除；Backend Ruff 与设置测试 9 项通过，Alembic 保持唯一 Head `7c1f4d8e2a90`。
- Client `master` 先获取并兼容合并 `origin/master` 的 v0.6 Portal/Auth 改造，再形成中文本地提交 `3c9c1de4ee0c3c9e3a51a2493a81833cef27adec`（`feat(client): 接入本地 Task 并完善任务操作页面`），相对 `origin/master` 领先 1 个提交。核心新增及冲突文件 Biome、TypeScript 类型检查及 Vitest 44 项全部通过。
- 三个提交均包含简体中文标题和分项说明；本地 `.env`、凭据、缓存、运行 Artifact、构建产物和内部地址均未纳入提交。Client 的 `.env.development` 与未跟踪 `AGENTS.md` 继续保留为本地文件，未暂存。
- 当前仅完成本地提交准备，没有向 GitHub 推送、创建 Tag、PR 或 Release。`rpa-flows` 与 `project-docs` 当前不是独立 Git 工作树，因此 Flow ZIP 和本总控文档不包含在上述三个代码提交中。
- 本次提交整理未连接数据库、未执行 DDL/迁移/种子、未创建或运行 Task，也未访问门户、ERP 或对象存储。后续每日提交继续遵守“一天至少一个中文说明提交；提交前检查敏感信息、测试结果和仓库边界”的规则。

#### 2026-07-30

#### Task 1 剩余 ERP 映射就绪

- 业务侧确认第 60 行客户料号 `1B.30040.020259` 和第 70 行客户料号 `1B.30040.020256` 的 ERP 测试环境映射已经建立。
- 当前状态为“业务侧已确认、尚待完整八行 Task 验证”；本次没有启动 Task、请求 ERP OAuth 或调用 ERP 导入接口，也未修改 Flow、Binding、Engine、Task、Client 或 UiPath 源码。
- 下一步在用户明确授权后，只执行一次完整八行 Task 1 受控复测，并继续沿用测试环境允许重复订单、单次调用且结果不明时停止的边界。
### 2026-07-29 GitHub 推送结果

- Engine 提交 `3ea8b1220a2161ee1bbfe98f2a7d4163f7618bfd` 已成功推送到 `loudon84/copilot-rpa` 的 `v0.1` 分支；本地与远端差异为 0/0。
- Task/Backend 提交 `ace9b2a8970e708606ddfc6f69c4fd52a3ae1989` 推送到 `loudon84/nodeskclaw` 的 `main` 时被 GitHub 以 HTTP 403 拒绝；Client 提交 `3c9c1de4ee0c3c9e3a51a2493a81833cef27adec` 推送到 `loudon84/copilot-autotask` 的 `master` 时同样被 HTTP 403 拒绝。当前 GitHub 登录账号对这两个仓库没有写权限，两个提交均安全保留在本地且各领先远端 1 个提交。
- 后续需由仓库所有者为当前开发账号授予两个仓库的写权限，或在 GitHub CLI 中由具备权限的账号通过浏览器重新授权；不得在聊天、日志或本文档中传递账号密码或访问令牌。权限就绪后只需分别重新执行当前分支的普通 push，不需要重新提交或强制推送。

#### Task 1 映射建立后完整八行复测仍失败

- ERP 同事反馈剩余映射已建立后，经用户授权对现有 Task `935782a4-0f8d-411e-9514-275eff7e2a40` 只调用一次 `/retry`。预检确认队列为空、Worker `server-worker-phase5-integration` 在线且空闲，Binding `7da19fa0-86ac-4d4a-b68e-30c0f651f5ae` 仍精确指向已发布 Flow `1.2.1`、UUID `e08059db-f55b-48e8-bbab-e33909f33b7d` 和摘要 `09d80f200d7164d4088a3e0c9eeacada322190379cd788bd40d90aca87353d51`，Engine 绑定预检为 `valid=true`。
- 新 Run `f057b40d-62f0-448e-8284-dcff3a40bbae`、Lease `af971718-a1d1-4c45-b753-37af3dfa2f8a` 完成门户登录、详情导航、8 行 XLSX 下载与解析、稳定截图、ERP OAuth 和一次完整八行导入请求。
- ERP 仍返回 `processStatusCode=ERROR`、`processGroupId=1785322089078` 和客户料号与物料编码匹配失败；`orderNumber`、`headerId` 均为空。Task 与 Run 以 `ERP_ORDER_IMPORT_ROW_FAILED` 结束为 `FAILED`，没有结构化输出或任务 2 后继作业。
- 本次 Run Artifact：`order_POJS2607130002.xlsx` 4,931 字节、`supplier-portal-erp-draft-prepared.png` 148,506 字节、`failure.png` 148,506 字节、`trace.zip` 4,772,833 字节。结束后 Worker 在线且空闲，队列为空。
- 本次没有自动再次逐行提交。若新映射已部分生效，逐行诊断可能创建多张不完整 ERP 订单，因此必须获得明确授权后再执行。未修改 Flow、Binding、Engine、Task、Client 或 UiPath 源码，未连接数据库或执行 DDL。
#### Task 1 新映射逐行复测

- 经用户明确授权，使用最新完整复测 Run `f057b40d-62f0-448e-8284-dcff3a40bbae` 的 XLSX Artifact 和 Flow `1.2.1` 原报文构造逻辑，对第 20 至 80 行按顺序各提交一次；共七次请求，无重试、超时、断连或未知结果。
- 第 20 行 `1B.30040.020255` 成功：ERP 订单 `10408260700008`、headerId `1097966`、processGroupId `1785322411677`；第 30 行 `1B.30040.020257` 成功：订单 `10408260700009`、headerId `1097967`、processGroupId `1785322413169`。
- 第 40 行 `1B.30040.020260` 成功：ERP 订单 `10408260700010`、headerId `1097968`、processGroupId `1785322414115`；第 50 行 `1B.30040.020258` 成功：订单 `10408260700011`、headerId `1097969`、processGroupId `1785322414776`。
- 第 80 行 `1B.30040.020261` 成功：ERP 订单 `10408260700012`、headerId `1097970`、processGroupId `1785322415830`。上述五张单行订单均为 `BOOKED / NEW / COMPLETE`。
- 第 60 行 `1B.30040.020259` 仍失败，processGroupId `1785322415503`；第 70 行 `1B.30040.020256` 仍失败，processGroupId `1785322415671`。两者均为 `ERP_ORDER_IMPORT_ROW_FAILED`，且未生成 orderNumber 或 headerId。
- 诊断结论：新映射已对第 20、30、40、50、80 行生效，完整八行失败仅剩第 60 和 70 行映射问题。本次没有重新运行 Task 或继续提交完整订单；未修改 Flow、Binding、Engine、Task、Client 或 UiPath 源码，未连接数据库或执行 DDL。连同此前两张第 10 行订单，ERP 侧现需核实或清理七张单行不完整订单。
#### ERP 测试环境重复订单处置决定

- 用户确认当前 ERP 测试环境允许相同字段反复创建订单，Postman 和受控逐行诊断产生的七张单行 `BOOKED` 测试订单暂时不需要 ERP 侧核实或清理。
- 后续联调无需以清理这些测试订单作为 Task 1 复测前置条件；当前唯一业务前置条件是修复并确认第 60 行 `1B.30040.020259` 和第 70 行 `1B.30040.020256` 的客户料号与物料编码映射已生效。
- 该决定仅适用于当前 ERP 测试环境，不改变生产环境的幂等、重复提交防护和提交后结果查询需求。
### 2026-07-28

#### 供应商门户按订单行维护预计交货日期并签章 Flow 1.0.0

- 修正 Flow `rpa_flow_supplier_portal_update_delivery_dates` `1.0.0`，工作流代码保持 `srm_update_expected_delivery_dates`。输入接口现为必填字符串 `po_no` 和必填数组 `order_lines`；每项包含唯一 `line_number`、用于防错的 `material_number` 和合法 `YYYY-MM-DD` `expected_delivery_date`。不同订单行允许使用相同料号和不同日期。
- Flow 从门户读取每行 `lineNo`、`materialNo` 和当前预计交货日期，并以行号为主键、料号为校验字段。输入必须完整覆盖门户全部订单行；缺行、多行、重复行号、门户行号歧义或料号错配都会在任何保存/签章操作前失败，不再因料号重复判定页面数据歧义。
- 登录并在订单列表确认订单存在后，统一进入 `/#/supplier/pend-orders/{po_no}` 详情路由。该处理兼容列表对已回签订单默认跳转普通详情页的行为，使非编辑状态仍可读取只读预计交期。
- 正常写入顺序固定为：填写全部日期并复核、稳定截图、只点击一次顶部保存、重载回读持久化、稳定截图、只点击一次签章、重载验证回复状态“已回签”、签章按钮不可执行且日期保持一致，最后记录签章后稳定截图。Flow 不点击逐行保存。
- 保存成功消息必须包含“已按明细行保存预计交货日期”；签章成功消息必须包含“签章成功”及“已回签”。保存或签章点击后的超时、断连、取消、未知结果或后续状态无法确认均映射为 `WAITING_HUMAN`，不得自动重复点击；明确拒绝保留业务失败。
- 已回签幂等分支会先按行核对全部料号和日期：完全一致时不再保存或签章并直接成功；任意日期冲突时返回 `WAITING_HUMAN / ORDER_ALREADY_CONFIRMED_CONFLICT`。
- 三张正常证据截图均经过统一页面稳定门禁：加载遮罩消失、行数和日期渲染正确、可见图片加载完成、`document.fonts.ready` 完成、布局连续两次一致，最后再等待约 300ms。失败现场截图立即执行，不等待稳定。
- Flow 继续使用 Engine 托管 Playwright 会话、`ctx.portal_url` 和由 Portal `credentialRef` 注入的 `ctx.credentials`。包内没有门户凭据、内部地址、浏览器启动代码或直接 CDP 连接代码。
- 验证通过：pytest 30 项及 8 个子测试通过；Ruff 默认规则及 `py311 + I + ASYNC109` 定点检查均通过，测试替身的 Playwright 兼容 `wait_for(..., timeout)` 仅在定义处使用 `# noqa: ASYNC109`；Python 编译检查通过；Engine 包校验 5 项通过、0 警告。真实门户无持久化测试确认目标订单 8 行按行号读取、临时填值、稳定门禁和刷新撤销正常，`saveClicked=false` 且服务器值未改变；另一个已回签订单能读取 1 条只读行，回复状态为“已回签”，签章按钮不可执行。
- 修正版 Artifact：`D:\AutoTask-Workspace\rpa-flows\rpa_flow_supplier_portal_update_delivery_dates\rpa_flow_supplier_portal_update_delivery_dates-1.0.0.zip`，大小 10,103 字节，摘要 `sha256:2744644f41a02b51095fc0fc91768ffbb6e7ad0171da2a474b27ada5b56bc657`。ZIP 与当前四个源文件逐字节一致，根目录只包含 `flow.py`、`manifest.json`、`selectors.json` 和中文 `README.md`。
- 初始摘要 `sha256:36aeaf438d6bb0b6530381930a21340a8dfff45c1276623ca61714001b6bafa1` 及上一次候选摘要 `sha256:7730e0b5694c817d0f18b9fe897c16849ec28572f601dad4917023f41afb9f21` 均已被本次修正版替换，不再是发布候选。本次未上传、未发布、未连接数据库，未修改 Engine、Task、Client 或 UiPath 源码，也未执行 Registry、MinIO、Git 提交或 Git 推送操作。
- 后续行动：由业务方提供目标订单全部订单行的真实预计交货日期；再上传、校验、发布修正版，创建精确 Flow UUID/校验和 Binding，并执行一次保存和签章均不自动重试的受控 Task 闭环测试。

### 2026-07-27

#### RPA Engine 本地 Task 代理隔离修复

- 修复 Engine 完整模式启动时，Task Worker 注册偶发返回 HTTP 502 并导致 FastAPI lifespan 退出的问题。Task 本地访问日志证明失败请求未到达 Task；同一注册请求直接调用及连续二十次复测均为 HTTP 200，根因是 Engine 的 `httpx.AsyncClient` 继承了系统代理环境。
- `TaskWorkerApiClient` 现在固定使用 `trust_env=False`，使 Task 注册、心跳、lease、事件、Artifact 和 finish 回调按显式 `TASK_API_BASE_URL` 直连，不再读取进程级 HTTP/HTTPS/ALL proxy。Task 源码、数据库结构和迁移均未修改。
- 新增代理隔离回归测试。验证通过：Engine 全量 217 项 pytest、Ruff、58 个源码文件的严格 mypy 和 `pip check`。
- 使用正常系统代理环境重新启动 Engine 完整模式。`GET /health/ready` 返回 200，数据库、对象存储、Task API 和 Runtime 文件系统均为必需且健康；Worker `server-worker-phase5-integration` 为 `ONLINE`，15 秒心跳与 5 秒 lease 轮询持续返回 HTTP 200，空队列未领取任务。
- 诊断期间通过本地 Task Worker API upsert 了专用诊断 Worker `diagnostic-worker-local`；未创建或启动新的 Task/Run，未执行 DDL、迁移、种子或直接 SQL。Task 后续应提供显式下线或离线阈值投影，以避免停止心跳的诊断 Worker 长时间显示为在线。

#### 决策和后续行动

1. Engine 到 Task 的内部服务调用默认不得继承桌面用户的系统代理；需要代理的部署应后续增加显式、受控的服务代理配置。
2. 当前完整模式可用于本地 Task 驱动演示。创建新的本地 Portal 后，仍需将 Engine 的 Mock 凭据作用域更新为本地 tenantId 和 Portal ID。
3. 后续为 Task Worker 增加显式 drain/offline 管理或按心跳阈值计算展示状态，并清理专用诊断 Worker。

#### AutoTask Client 本地闭环与证据中心改造

- Client 的远程 DTO 适配已覆盖本地 Task 的 Portal、WorkflowTemplate、精确 WorkflowBinding、Task、Run 和 Artifact 数据；桌面端支持创建 Portal/模板/Binding，并在新建任务时选择精确 Binding。未修改 Task 数据库结构或迁移。
- 本地 Auth、Task 和 Engine 健康检查均返回 HTTP 200。回读确认一条 `rpa_flow_mock_srm_fetch_po` Task 及其 Run 均为 `SUCCESS`，Worker 为 `server-worker-phase5-integration`，产生三张 PNG 截图和一个非空 XLSX Artifact。
- 证据中心不再使用截图占位图：打开截图时按需调用 Artifact 下载地址接口，使用临时签名 URL 展示接近全屏的原图；普通任务和 Run 列表不会批量申请签名 URL。链接获取失败或过期时可重新加载。
- 截图和 `download` 类型 Artifact（当前包括 XLSX）均提供下载按钮。Renderer 只获取临时地址，实际下载由 Electron 主进程 `webContents.downloadURL` 发起，文件进入用户系统下载目录；存储凭据、Token 和签名 URL 均不写入 Client 日志或本文档。
- 首次点击下载出现 `not found` 并非 Artifact 文件缺失。只读复测确认四个真实下载地址均返回 HTTP 200，响应字节数与本地落盘文件一致；根因是开发模式仅热更新 Renderer，而旧 Electron 主进程尚未加载新增的 ORPC 下载过程。完整重启桌面端后，新主进程已加载该处理器。
- Client 验证通过：25 项 Vitest 单元测试、相关文件 Biome 检查和完整 TypeScript 类型检查。新增回归覆盖真实截图渲染、普通列表不预取截图地址以及 XLSX 经 Electron 下载处理器发起下载。
- 开发约束：涉及 `src/ipc` 或 Electron 主进程的变更必须完整重启桌面端，不能只依赖 Renderer HMR。测试环境部署仍需修正或确认 Task Artifact public/download base URL；本地下载闭环已经验证。

### 2026-07-23

#### 目标

1. 构建供应商门户 Flow：下载订单 XLSX，并且仅使用 XLSX 内容构造 ERP 销售订单请求。
2. 增加已批准的 OAuth 和 ERP 导入步骤，打包 `1.1.0`，并验证一次由 Task 驱动的端到端运行。
3. 修正 ERP 响应分类，使行级导入错误即使在顶层响应成功时也被判定为业务失败。

#### 已完成工作

Flow 接口及 Playwright/CDP 行为：

- 新增 Flow `rpa_flow_supplier_portal_prepare_erp_order`：入口为 `flow.py:run(ctx)`，工作流代码为 `srm_prepare_erp_order`，必填字符串输入为 `po_no`，最低 Engine 版本为 `0.5.0`，能力包括 `PLAYWRIGHT_CDP`、`BROWSER_SESSION_MANAGED`、`SCREENSHOT` 和 `DOWNLOAD`。
- Flow 仅使用 `ctx` 提供的 Engine 托管浏览器；不会自行启动浏览器或连接 CDP。Portal URL 由 Task 的 `config.portalUrl` 通过 `ctx.portal_url` 提供。
- 浏览器流程依次执行登录、搜索指定 PO、打开可见详情行、确认下载、校验 XLSX 签名、记录附件和截图 Artifact，并按 `CLOSE_ON_FINISH` 关闭。未知 CAPTCHA 继续映射为 `WAITING_HUMAN`。
- `1.0.0` 生成并返回 ERP 草稿，不调用 ERP；`1.1.0` 获取 OAuth Token 并提交 ERP 销售订单数组。HTTP 请求体就是该数组本身，不包含 Runtime 元数据外层包装。

XLSX 到 ERP 的契约：

- 页面字段仅用于导航和下载。ERP 请求中所有非空字段均来自 XLSX 或已批准的默认值；详情页展示的物料行不进入请求体。
- 头字段映射使用 XLSX 的供应商名称填充 `orgName`，使用 XLSX 的备注填充 `comments`。已批准的默认值包括客户名称、常规订单类型、中国业务日期和 `isAttachment=Y`；由接口/EBS 自动匹配的字段保持为空。
- 行字段映射使用 XLSX 的订单行号、订单编号、料号、数量、单价和要求交货日期。`taxRate` 默认为 `0.13`，未税价根据含税单价计算。由于 XLSX 不提供稳定的源记录 ID，`sourceHeaderId` 和 `sourceLineId` 保持为空。
- 该包对 ERP OAuth 凭据采用已明确接受的私有部署策略。凭据值不记录在本文档、日志、事件或 Artifact 中；源码包必须受限并置于 Git 之外。

Registry、Task Binding 和端到端运行：

- 将不可变 Flow `1.1.0` 发布为 Flow Version `89ca0ffe-cd87-4f00-9f6f-c16974aa437f`，校验和为 `sha256:ae0b4a5a7ef585cc4986ed74580e69576b87aed38ed97f3ca9897583a01dd47b`。
- 复用 Portal `b182630d-5023-45c3-ac9c-6b022765b7e1`；创建模板 `63db75da-0c26-4f68-ad17-7f4a836ffa45` 和 Binding `0a0b5beb-a2cd-449b-9003-b723b3e65bfd`，以 MANAGED Chrome 和 `CLOSE_ON_FINISH` 精确绑定 Flow UUID 及校验和。
- 为 `POJS2606030010` 创建 Task `8193cea4-6b57-4ed2-ac3e-187797e7bf4a`；Run `c72fcdd5-21a0-44ca-bf94-8d5511332a68` 由 Worker `server-worker-phase5-integration` 租用并完成一次已授权执行，没有自动重试。
- 登录、PO 详情导航、非空 XLSX 下载、`erp.oauth`、`erp.import`、租约续期、事件回调、Artifact 上传/元数据登记和完成回调均已完成。上传的 Artifact 为 `order-20260709122735.xlsx`（4,169 字节）和 `supplier-portal-erp-draft-prepared.png`。
- ERP HTTP 响应顶层为 `code=2000`、`success=true`，但结果行中的订单标识均为空，且 `processStatusCode=ERROR`，具体为客户料号与物料编码匹配错误。因此 `1.1.0` 将 Task/Run 结束为 `SUCCESS`；这验证了传输和回调闭环，但不代表 ERP 订单导入成功。
- 测试启动的 Engine 进程已优雅停止，恢复为没有 Engine 监听器运行的初始状态。

ERP 结果分类版本 `1.1.1`：

- 创建不可变源码版本 `1.1.1`，未修改已发布的 `1.1.0`。
- 成功条件改为：`rows` 数组非空，并且每一行均具有 `processStatusCode=COMPLETE` 和非空 `orderNumber`。
- 任一行出现 `processStatusCode=ERROR` 时，抛出代码为 `ERP_ORDER_IMPORT_ROW_FAILED` 的 `RpaBusinessError`。因此 Task/Run 以业务 `FAILED` 结束：Flow 和 ERP 请求在技术上已执行，但订单导入被拒绝。安全失败详情保留空标识、`processGroupId`、状态，以及去除首尾空白且最长 500 个字符的 `processMessage`。
- 空 `rows`、未知状态，或 `COMPLETE` 但没有订单号的行均映射为 `WAITING_HUMAN`。提交后的超时、断连、限流、服务端错误或矛盾结果也继续作为不可重试的 `WAITING_HUMAN`，等待人工核实 ERP。
- ERP 明确拒绝映射为业务失败；认证错误和端点配置错误仍属于致命错误。不会输出 Token、Authorization 请求头、OAuth 查询字符串、凭据或原始认证响应。

#### 验证结果

| 检查项 | 结果 |
| --- | --- |
| Flow `1.1.1` 单元测试 | 30 项通过 |
| Ruff 检查和格式检查 | 通过 |
| Flow `1.1.0` 回归测试 | 26 项通过 |
| Flow `1.0.0` 回归测试 | 8 项通过 |
| Engine 本地验证运行器 | Manifest/导入校验通过；按计划跳过实际执行 |
| Engine ZIP 策略校验器 | ZIP 结构、manifest schema、异步入口、Runtime 策略和包校验和均通过 |
| `1.1.1` 包 | 11,998 字节；SHA-256 `d513c24763fa4dcfb07bd9b35f4e705643f2669db287787d668f9f7996b2ca6e` |
| `1.1.1` 的真实 ERP/Task 运行 | 未执行 |

#### 变更文件和 Artifact

- `D:\AutoTask-Workspace\rpa-flows\rpa_flow_supplier_portal_prepare_erp_order\1.0.0\*`
- `D:\AutoTask-Workspace\rpa-flows\rpa_flow_supplier_portal_prepare_erp_order\1.1.0\*`
- `D:\AutoTask-Workspace\rpa-flows\rpa_flow_supplier_portal_prepare_erp_order\1.1.1\*`
- `D:\AutoTask-Workspace\rpa-flows\rpa_flow_supplier_portal_prepare_erp_order\rpa_flow_supplier_portal_prepare_erp_order-1.1.1.zip`
- `D:\AutoTask-Workspace\project-docs\PROJECT_CONTROL.md`

#### 决策

1. ERP 请求以 XLSX 内容为准；详情页业务字段不作为补充来源。
2. ERP 顶层成功不能覆盖行级状态。任一行级 `ERROR` 都是确定的业务失败，而不是 Runtime/系统失败。
3. 当前报文没有稳定幂等键，因此提交后结果不明确时不得自动重试。
4. 所有者接受在此受限、非 Git 包中内嵌 ERP OAuth 凭据，并接受凭据轮换需要创建新 Flow 版本和更新 Binding。该例外不允许在本文档或日志中记录凭据。
5. 已发布的 Flow 版本保持不可变。在 `1.1.1` 单独完成上传、校验、发布和明确绑定前，当前 Binding 继续指向 `1.1.0`。

#### 阻塞项和风险

1. ERP 测试主数据目前拒绝客户料号与物料编码映射；在建立或修正该映射前，业务成功验收无法通过。
2. `1.1.1` 尚未上传或绑定；生产 Task 行为仍是 `1.1.0` 的仅顶层分类逻辑。
3. 私有 ZIP 包含真实 ERP 凭据，必须保持访问受控、置于 Git 之外，并且不得进入通用日志或共享存储。
4. 当前没有可安全处理提交后崩溃的 ERP 幂等/查询契约。Flow 可以减少常规重试，但无法独立保证最多投递一次。
5. 当前 Artifact API 不支持通用 JSON 结果 Artifact，因此 ERP 结果仅通过白名单内的非敏感事件传递；Runtime 会忽略 Python 返回值。

#### 后续行动

1. 上传、校验并发布准确的 `1.1.1` ZIP；记录其 Registry Flow Version UUID，并确认 Registry 校验和。
2. 创建或更新精确绑定 `1.1.1` UUID 和校验和的 WorkflowBinding，不覆盖历史 `1.1.0` 版本。
3. 在授权一次受控重跑前，确认 ERP 客户料号与物料编码测试数据，并确认上一次处理是否生成了任何订单。
4. 重跑时仅当每一行均为 `COMPLETE` 且具有 ERP `orderNumber` 才接受成功；否则保留业务失败或 `WAITING_HUMAN` 终态映射。
5. 在扩大部署范围前，定义生产凭据、幂等/查询和提交后恢复契约。

### 2026-07-18

#### RPA Engine 首批质量改进及延期生产事项

- 已完成并验证 Worker 取消与中断执行尝试的状态收敛、EVENT/FINISH Callback Outbox 持久投递、回溯信息中的密钥脱敏，以及 Flow Registry 对象隔离和事务边界修复。
- 验证通过：216 项 pytest 测试、Ruff、严格 mypy、`pip check`，以及在禁用外部依赖时的隔离服务启动。未执行真实 PostgreSQL、MinIO 或 Task 写入，也未执行 DDL 或迁移。
- 以下 Engine 工作延期处理，不阻塞当前受控的单 Worker 演示：
  1. **可靠 Artifact 投递：**将 Artifact 上传和元数据登记移入可恢复工作流，支持本地文件保留、重试、幂等登记、失败清理和重启恢复。EVENT 和 FINISH 当前使用 `rpa_callback_outbox`；Artifact 操作仍为直接调用。
  2. **按 Run 隔离执行：**将 Flow 执行从 Engine 进程移入受监管的子进程或容器，提供硬超时终止、CPU 和内存限制、浏览器进程清理及孤儿 Run 恢复。当前进程内 Flow 必须配合取消；若其吞掉 `CancelledError`，则无法安全强制终止。
- 两项延期工作在生产发布前均需要独立的实施计划、测试和验收标准。

#### 真实 Task 驱动的 SUCCESS 端到端验证

- 已通过真实 Task API 完成一次获授权的端到端运行：创建 Task、启动 Task、HTTP 租约、精确解析 Flow、托管浏览器执行、事件回调、Artifact 上传/登记、完成回调及运行后观察。
- Task `8f5d3928-6402-4bd8-b90f-858a383f8d64` 和 Run `1d72bfa9-0971-492f-9ebd-68e2879a95c1` 均到达 `SUCCESS`，没有错误代码或消息。Worker `server-worker-phase5-integration` 回到 `ONLINE`，占用槽位为 `0/1`。
- 不可变 Flow 快照为 `rpa_flow_mock_srm_fetch_po` `1.1.0`，Flow Version ID 为 `ffd5687a-b213-4f10-9265-1813addb48ec`，校验和为 `sha256:4950d0cc1302b11af330ef0abea5b2a603a310210b717d898c9981e64b83fd37`。
- Task 记录了 19 个运行事件和四个 Artifact：三张非空 PNG 截图及一个下载文件 `order-20260709122735.xlsx`。XLSX 大小为 4,169 字节，返回预期 MIME 类型，并通过 ZIP/XLSX `PK\x03\x04` 签名检查。
- Engine 持久化验证通过：一个 `LEASE` 执行尝试到达 `SUCCESS`，起止时间有效；Callback Outbox 序号 1-13 为 `EVENT`，序号 14 为 `FINISH`，全部 14 条记录均仅发送一次，没有重试、死信、残留锁或最后错误。
- 运行结束后，数据库、对象存储、Task API 和 Runtime 文件系统的就绪状态均保持健康。Engine 日志没有错误或回溯条目，也未检测到明文凭据或 Token。
- Task 集成后续事项：
  1. Artifact 下载 URL 当前使用环回主机 `127.0.0.1:4520`，远程客户端无法使用返回的 URL。仅将主机替换为可达的 Task 主机后返回 HTTP 200 和有效 XLSX；Task 必须修正 Artifact 对外/下载基础 URL。
  2. 对于该成功 Task，Task 详情响应中的 `portalAccountId`、`workflowBindingId`、`entityType` 和 `erpEntityCode` 为 null，尽管创建、Binding 解析、租约和执行均成功；Task 应修正响应映射。
- 本次端到端测试仅使用已授权的 Task/Worker/对象存储 API。未执行直接数据库写入、DDL、迁移或种子命令。

### 2026-07-16

#### 目标

1. 汇总已验证的 RPA Engine 第 1-5 阶段实施状态。
2. 记录 AutoTask 中心演示当前的 Engine/Task 集成边界。
3. 通过新增开发日志替代过时的 Engine 假设，不重写历史记录。

#### 已完成工作

Engine 基础和 Flow Registry：

- 将 `nodeskclaw-rpa-engine` 创建为使用 Python 3.12、FastAPI、SQLAlchemy 2、Alembic、asyncpg 和 S3 兼容存储的服务；当前服务版本为 `0.5.0`，默认端口为 `4610`。
- 增加基于环境变量的配置、密钥脱敏、结构化 Run/Worker/Flow 日志上下文、存活/就绪聚合，以及默认禁用的外部依赖。
- 实现 Flow Package ZIP 校验、MinIO 存储、GLOBAL/TENANT Flow Registry、不可变版本记录、校验、发布、弃用、禁用、回滚、包下载和精确 Binding 校验。
- 在 `dist/rpa_flow_mock_srm_fetch_po-1.0.0.zip` 准备了可上传的第 5 阶段 Flow 包；包中不含凭据或环境配置。

Worker Pool 和 Runtime：

- 实现内部 Worker Pool、Worker 注册/心跳、本地并发槽位、租约幂等、执行尝试编号、租约续期/过期取消、优雅排空、Task Worker API 兼容和只读 Worker 观察。
- Worker 和租约轮询默认保持禁用。注册/心跳可以单独启用；真实租约轮询继续受扩展 Task 契约门禁控制。
- 实现精确版本 Flow 加载及校验和验证、原子本地缓存修复、`RunContext`、MANAGED Playwright 浏览器会话、受控 Chrome/Chromium/Edge 通道、确定性清理、Runtime 重试和标准化 SUCCESS/FAILED/WAITING_HUMAN 错误映射。
- 实现截图、下载、Trace 和日志 Artifact 记录，以及 Task 上传 URL、Artifact 元数据、事件和完成回调。当前回调为直接调用；持久 Outbox 投递尚未连接到 Runtime 回调路径。

第 5 阶段演示：

- 在端口 `4600` 新增独立、确定性的 Mock SRM 服务和版本化采购订单 Flow。
- 使用真实 MANAGED Chrome 浏览器验证成功场景 `PO-20260708-001`、业务失败场景 `PO-NOT-FOUND` 和人工干预场景 `PO-MANUAL-001`。
- 已冻结的 WAITING_HUMAN 行为继续采用 A 型：捕获证据后关闭原浏览器上下文。在操作员输入后恢复同一浏览器会话被记录为未来优化项。

#### 公共接口和契约

- 健康检查：`GET /health/live` 和 `GET /health/ready`。
- Flow Registry：`GET /api/v1/flows`、包上传、Flow/版本详情和列表、校验、发布、弃用、禁用、回滚、包下载，以及 `POST /api/v1/flow-versions/validate-binding`。
- Worker 观察：`GET /api/v1/workers` 和 `GET /api/v1/workers/{workerId}`；未增加公开的排空/恢复变更端点。
- Runtime 继续作为内部 `RunCommandHandler`；未增加可直接用于生产运行/调试的 HTTP 端点。
- Engine 未增加业务调度/Cron 触发。`nodeskclaw-task` 负责调度配置和定时创建 AutomationTask；Engine 只租用并执行所产生的命令。
- Task 必须发送一份不可变执行快照，其中包含精确 Flow 版本、租户/工作流标识、凭据引用、门户配置、MANAGED 浏览器配置和租约过期时间。Engine 绝不替换为最新 Flow 版本。

#### 数据结构和存储

- 由于测试环境允许创建 schema、但不允许创建独立 Engine 数据库，可部署数据库目标已从早期独立数据库方案调整为 PostgreSQL 数据库 `nodeskclaw_task` 下的 `rpa_engine` schema。对于当前开发，本条记录取代早期独立数据库假设。
- 该 schema 包含九张 Engine 专属表：`rpa_flows`、`rpa_flow_versions`、`rpa_flow_validation_runs`、`rpa_flow_release_audits`、`rpa_worker_instances`、`rpa_execution_attempts`、`rpa_callback_outbox`、`rpa_browser_profiles` 和 `rpa_cdp_endpoints`。
- ORM/待执行 DDL 基线包含 142 个字段、七个内部外键、四个触发器函数和十二个触发器。跨服务标识继续作为外部字符串引用，不对 Task 专属表建立外键。
- Alembic 修订 `20260713_0001` 表示现有 schema 基线。应用启动和测试绝不会调用 `create_all`、执行迁移、创建 Bucket 或写入种子数据。
- 第 3-5 阶段不需要新增 Engine 表或迁移。Flow 包和 Runtime Artifact 使用 S3 兼容对象存储；密钥仍仅来自环境变量。

#### 验证结果

| 检查项 | 结果 |
| --- | --- |
| Engine 单元/API/契约测试套件 | 2026-07-16 共 102 项通过 |
| Ruff | 通过 |
| mypy 严格检查 | 55 个源码文件均无问题 |
| Python 依赖一致性 | `pip check` 通过 |
| 第 5 阶段 MANAGED Chrome 演示 | SUCCESS、FAILED 和 WAITING_HUMAN 场景均通过 |
| 自动化测试中的数据库行为 | 仅使用测试替身；测试套件未执行 PostgreSQL DDL 或写入 |
| Task 契约检查 | 已于 2026-07-15 检查测试 OpenAPI；真实租约仍按计划禁用 |

#### 决策

1. 当前 Engine 数据库位置为 `nodeskclaw_task.rpa_engine`；九张表仍由 Engine 独占所有。
2. Flow Binding 和运行命令必须固定到准确的已发布版本及校验和快照；禁止回退到最新版本。
3. 首个生产基线仅启用 `PLAYWRIGHT_CDP` 且 `browserSession.mode=MANAGED`。
4. 业务调度属于 `nodeskclaw-task`，不属于 Engine Worker Pool。
5. 第 5 阶段初始演示继续采用不可恢复的 A 型 WAITING_HUMAN 模型。
6. 仅用于测试的执行者请求头和 `TASK_AUTH_MODE=none` 不属于生产认证。

#### 阻塞项和风险

1. 2026-07-15 检查的 Task 测试服务器租约响应缺少 `tenantId`、工作流元数据、`rpaFlowVersion`、`credentialRef`、完整 `config.browserSession`、门户 URL 和 `leaseExpiresAt`；租约续期也不返回新的过期时间。扩展该契约前，中心 Task 驱动执行仍被阻塞。
2. Engine 默认凭据解析器会拒绝非空 `credentialRef`。Mock SRM 集成仍需要限定范围的测试解析器，之后还需实现受治理的生产凭据服务适配器。
3. Task 必须在不可变命令快照中包含受控门户 URL，或提供受治理的门户解析器；Flow 不得硬编码该地址。
4. 尽管存在 `rpa_callback_outbox` 表，直接回调仍无法保证在 Task 短暂故障后完成投递。
5. Python Flow 当前运行在 Engine 进程内。静态包策略检查不等于操作系统级隔离，整条 Flow 重试可能重复外部副作用。
6. 尚未实现 WAITING_HUMAN 后的同会话 CAPTCHA/MFA 继续执行；原浏览器会关闭。
7. 除两个基础 MANAGED 能力外，第 5 阶段 Worker 还必须声明 `SCREENSHOT` 和 `DOWNLOAD`。
8. 业务定时运行功能需要 Task 侧调度存储、触发处理和 AutomationTask 创建能力。

#### 后续行动

1. 按第 5 阶段集成契约扩展 `nodeskclaw-task` 的 Binding 快照、租约/续期响应、事件/Artifact 投影、完成处理和专用演示数据。
2. 在不暴露密钥的前提下增加 Engine 限定范围的 Mock SRM 凭据解析器，在受控测试网络部署 Mock SRM，并发布 Flow `1.0.0`。
3. 配置 Engine Worker 能力并验证一份专用租约快照，然后仅针对已批准的测试数据启用租约轮询并执行全部三个中心场景。
4. 在生产发布前接入持久 Callback Outbox 投递，并增加生产服务账号认证。
5. 单独决定业务调度和同会话人工继续执行是否进入下一产品阶段。

#### 变更文件和服务

- Engine 源码和测试位于 `D:\AutoTask-Workspace\nodeskclaw-rpa-engine\src` 和 `tests`。
- Engine 数据库基线位于 `migrations` 和 `sql`；未引入应用启动时执行 DDL 的行为。
- 阶段文档包括 `docs/PHASE2_API.md` 至 `docs/PHASE5_MOCK_SRM.md`。
- Mock SRM 和参考 Flow 位于 `examples/mock-srm-flow`，打包/演示脚本位于 `scripts`。

#### 公开 v0.1 提交更新

- 在保留现有 `prd/` 内容的同时，将 Engine `0.5.0` 演示基线发布到公开仓库 `loudon84/copilot-rpa` 根目录的 `v0.1` 分支。基线提交为 [`1e3c44d`](https://github.com/loudon84/copilot-rpa/commit/1e3c44d32c7de1c98fa17e6b8249229080885f31)，跨平台 CI 修复为 [`70f2dc4`](https://github.com/loudon84/copilot-rpa/commit/70f2dc4f0510205ea928f7b339276a22eb8d8da0)。
- 从受版本控制的源码、示例、文档、Postman 默认值和启动配置中移除专用测试服务器地址。公开默认值改用 localhost 或变量；`.env`、凭据、缓存、Runtime Artifact、生成包、截图、Trace 和下载文件继续被忽略且未提交。
- 新增 `CREDENTIAL_RESOLVER_MODE=disabled|mock_env`。`mock_env` 仅限开发/测试使用，会精确校验 `credentialRef`、`tenantId` 和 `portalAccountId`，凭据只保存在内存中，并在生产环境被拒绝。该项解决了早期 Mock SRM 凭据解析器阻塞；仍需受治理的生产凭据服务适配器。
- 将默认 Worker 能力集标准化为 `PLAYWRIGHT_CDP`、`BROWSER_SESSION_MANAGED`、`SCREENSHOT` 和 `DOWNLOAD`。只要 Worker 或 Runtime 任一启用，就绪检查现在会将 Task API 视为必需依赖。公共 HTTP 路由形状和九表数据库模型未改变。
- 在 Python 3.12 上新增 GitHub Actions，包含私有地址门禁、Ruff、mypy、pytest 和 `pip check`。将测试辅助导入改为兼容 Windows 与 Linux 后，最终工作流运行 [`29469612524`](https://github.com/loudon84/copilot-rpa/actions/runs/29469612524) 通过。

| 提交验证 | 结果 |
| --- | --- |
| 本地单元/API/契约测试套件 | 2026-07-16 共 122 项通过 |
| Ruff | 通过 |
| mypy 严格检查 | 56 个源码文件均无问题 |
| Python 依赖一致性 | `pip check` 通过 |
| 真实 MANAGED Chrome 演示 | SUCCESS、FAILED 和 WAITING_HUMAN 场景均通过 |
| 公开仓库检查 | 未提交本地 `.env`、凭据特征、专用测试地址、生成的 ZIP、缓存、截图、Trace、下载文件或 Runtime Artifact |
| 远程分支和 CI | `v0.1` HEAD 为 `70f2dc4`；GitHub Actions 通过 |

- 数据库 ORM、现有九张 Engine 表、待执行 DDL 和 Alembic 修订 `20260713_0001` 均未改变。公开提交过程中未执行 PostgreSQL、MinIO、Task API、迁移、种子或外部数据写入。
- 剩余集成风险不变：启用真实轮询前，Task 必须提供完整不可变的租约/续期快照；Redis Queue、持久 Callback Outbox 投递、生产服务账号认证、操作系统级 Flow 隔离和同会话 WAITING_HUMAN 继续执行均未闭环。

#### Task 集成契约对齐和测试服务器交接

- 2026-07-16 对 Task 测试服务器 OpenAPI 的只读检查确认了完整不可变租约快照、续期 `leaseExpiresAt` 和 Worker Artifact 上传 URL 路由。Engine 现在调用 `POST /worker-api/artifacts/upload-url`，携带必需的 snake_case 字段 `worker_id`、`task_id`、`run_id`、`name` 和 `mime_type`，随后执行签名 PUT 和 Artifact 元数据回调。
- `config.portalUrl` 现为必填 HTTP(S) 租约字段，并拒绝内嵌凭据。`TaskArtifactSink` 接收稳定配置的 Worker ID。Engine 公共 HTTP 路由没有变化。
- 新增 `docs/PHASE5_TEST_SERVER_HANDOFF.md`，覆盖部署、Flow 构建/上传/校验/发布、Task Portal/模板/Binding/Task 创建、队列隔离、两阶段租约启用，以及串行 SUCCESS/FAILED/WAITING_HUMAN 验收。当前 Task 请求契约混用命名风格：Portal 创建使用 camelCase；模板、Binding 和 Task 创建使用 snake_case。
- 将提交 [`dc09f0e`](https://github.com/loudon84/copilot-rpa/commit/dc09f0ed6224f5ea07fb58fab1136a028c7676e0) 发布到公开分支 `v0.1`。GitHub Actions 运行 [`29476820968`](https://github.com/loudon84/copilot-rpa/actions/runs/29476820968) 通过。

| 对齐验证 | 结果 |
| --- | --- |
| 本地单元/API/契约测试套件 | 125 项通过 |
| Ruff | 通过 |
| mypy 严格检查 | 56 个源码文件均无问题 |
| Python 依赖一致性 | `pip check` 通过 |
| 公开暂存内容扫描 | 未提交 `.env`、私有测试地址、凭据特征、生成的 ZIP 或 Runtime Artifact |
| 数据库/数据结构 | 九张 Engine 表和 Alembic 修订未改变；未新增或执行迁移 |

- 真实 Task 驱动的租约、续期、事件、签名 Artifact PUT/元数据和完成回调仍未经过端到端验证。启用租约前，Task 所有者必须取消或隔离所有无关 `QUEUED` Run，发布或验证精确 Flow 版本，创建新的有效 Portal/模板/Binding 数据，并拒绝任何 `seed-version-*` 或零校验和 Binding 快照。
- 当前发布风险仍然存在：Task 租约不会按 Worker 能力筛选，Runtime 回调没有持久 Outbox 调度器保护，生产 Worker 认证尚未完成，Python Flow 执行缺少操作系统级隔离，并且 A 型 WAITING_HUMAN 无法恢复原浏览器会话。

#### 真实供应商门户 Flow 1.1.0 更新

- 为已配置的供应商门户新增不可变 Flow 源码版本 `rpa_flow_mock_srm_fetch_po` `1.1.0`，同时逐字节保留确定性的本地 Mock `1.0.0` 包。历史 `1.0.0` 包校验和保持不变；支持版本感知的构建器现在生成可复现 ZIP，并拒绝发生变化的历史包。
- Flow `1.1.0` 仅使用 Engine 托管的 Playwright，执行登录、PO 查询、可见行详情导航、确认对话框下载、XLSX 签名校验和 Artifact 记录。未知 CAPTCHA 图片继续映射为 A 型 `WAITING_HUMAN`；凭据和部署地址继续作为 Runtime 输入，不存储在包或日志中。
- 使用 `POJS2606030010` 对受控供应商演示执行了一次真实 MANAGED Chrome 冒烟运行并成功完成。运行到达订单详情页，并将门户提供的非空 XLSX 记录为有效的 ZIP/XLSX Artifact。
- 最终验证：151 项 pytest 测试通过；Ruff、严格 mypy、`pip check`、包校验、差异检查和受版本控制私有地址扫描均通过。保留的 `1.0.0` SUCCESS/FAILED/WAITING_HUMAN 浏览器回归也通过。
- Engine 公共 HTTP 路由、九张 Engine 表和 Alembic 修订 `20260713_0001` 均未改变。未执行数据库迁移、数据库写入、MinIO 写入、Task 租约、Task 回调、Git 提交或 Git 推送。
- 剩余中心集成工作包括：上传/校验/发布准确的 `1.1.0` 包，将 Task WorkflowBinding 更新为返回的 UUID 和校验和，隔离 Task 队列，并端到端验证租约/续期、签名 Artifact 上传/元数据、事件和完成回调。生产凭据服务、Worker 认证、持久 Callback Outbox 投递、按能力选择租约和可恢复人工处理仍是未决风险。

#### Flow 1.1.0 Registry 和 Task Binding 集成

- 在 Engine Registry 中上传、重新校验并发布 `rpa_flow_mock_srm_fetch_po` `1.1.0`。不可变 Flow Version UUID 为 `ffd5687a-b213-4f10-9265-1813addb48ec`；包摘要为 `sha256:4950d0cc1302b11af330ef0abea5b2a603a310210b717d898c9981e64b83fd37`。
- 创建并启用 Task 工作流模板 `srm_fetch_po`，ID 为 `1c5a14a8-68e7-40d3-a853-986dcaedaac9`；随后使用当前账号所有的 Portal `b182630d-5023-45c3-ac9c-6b022765b7e1` 创建启用的 Binding `bdf51dd4-3fe0-45a7-b888-62a3f25b47cc`。该 Binding 指向 Flow `1.1.0`、上述精确 UUID，并使用带 `CLOSE_ON_FINISH` 的 MANAGED Chrome。
- Task 当前从响应顶层读取 Engine Binding 校验快照字段。Engine 暂时公开已弃用的顶层别名 `rpaFlowVersionId`、`packageChecksum` 和 `checksum`，同时保留规范契约 `version.rpaFlowVersionId` 和 `version.packageChecksum`。Task 必须切换到规范的嵌套映射；该修复部署后删除 Engine 别名。
- Task 将 `flowChecksumSnapshot` 保存为相同的规范化 64 位十六进制摘要，但不带 `sha256:` 前缀。规范化后的摘要完全一致，但各团队必须在生产前确定并记录统一的外部表示形式。
- 验证通过：152 项 pytest 测试、Ruff、全部 56 个已配置源码文件的严格 mypy、`pip check`、API 回读及规范化校验和比较。未创建或启动 Task/Run，未启用租约轮询，也未执行直接 Task 数据库写入、DDL、迁移、种子、Git 提交或 Git 推送。

### 2026-07-10

#### 目标

1. 将 UiPath 登录演示转换为 AutoTask RPA Flow 参考包。
2. 将 AutoTask Client 连接到远程 nodeskclaw 认证和任务服务。
3. 冻结 RPA Engine 数据库准备边界。
4. 建立持久的开发记录位置。
5. 使用 OCR 替换登录演示的验证码文件名映射，并测量其可用性。
6. 将 `D:\AutoTask-Workspace` 建立为产品级工作区，并分离 Client、Flow、UiPath 和开发记录。

#### 已完成工作

UiPath 登录流程：

- 已读取 UiPath 登录流程，当前位于 `D:\AutoTask-Workspace\rpa-authoring\uipath\login_demo\Main.xaml`。
- 已确认演示站点使用十张固定验证码图片，并且 UiPath 图片到验证码的映射与站点实现一致。
- 创建 `rpa_flow_login_demo` `1.0.0`，当前位于 `D:\AutoTask-Workspace\rpa-flows`。
- 使用 `ctx.credentials` 替换硬编码凭据。
- 将未知验证码映射为 `CAPTCHA_REQUIRED`，交由 `WAITING_HUMAN` 处理。
- 新增选择器、manifest 元数据、截图、登录结果处理和验证码适配器测试。

验证码 OCR 实验：

- 保持文件名映射 Flow `1.0.0` 不可变，并创建 OCR 版本 `1.1.0`。
- 使用 `ddddocr` 对图片字节进行识别，替代验证码文件名映射。
- 较新的 ONNX Runtime DLL 在当前 QEMU Windows 环境中失败后，锁定了经验证的 Windows/Python 3.11 OCR 依赖版本。
- 增加一次受控的验证码刷新和重试；OCR 不可用、结果格式错误或连续两次被拒绝时进入 `WAITING_HUMAN`。
- 防止已识别验证码文本写入日志。
- 增加 Canvas 自然像素捕获，并以元素截图作为回退。
- 新增五项 OCR 结果校验单元测试和详细 OCR 评估报告。
- 在 20 个隔离浏览器会话中重新运行最终 Canvas 版 Flow：17 次登录成功，3 次按设计进入 `WAITING_HUMAN`。

浏览器验证：

- 通过单元测试覆盖验证全部十个演示验证码映射。
- 针对 `http://192.168.102.247:3000/` 运行转换后的浏览器流程。
- 观察到登录成功，最终 URL 为 `http://192.168.102.247:3000/#/dashboard`。

远程服务集成：

- 配置 AutoTask 开发模式使用远程 API。
- 将 nodeskclaw-backend 配置为 `http://192.168.102.247:4510`。
- 将 nodeskclaw-task 配置为 `http://192.168.102.247:4520`。
- 从认证路径中移除两个残留的 `debugger` 语句。
- 成功启动 AutoTask Electron Client。

开发记录：

- 创建项目记录位置并迁移到 `D:\AutoTask-Workspace\project-docs`。
- 将当前项目状态和每日日志整合到本文档中。
- 更新仓库 Agent 指令，使后续 Codex 会话读取并更新本文档。
- 将完整的 RPA Engine 数据库准备行动计划、交付物、暂停点和未来执行门禁加入本文档。

产品工作区迁移：

- 将 `D:\AutoTask-Workspace` 建立为产品级 Codex 工作区。
- 保留 `D:\AutoTask-Workspace\copilot-autotask` 下的 Client Git 仓库和当前未提交工作。
- 将 RPA Flow 包分离到 `rpa-flows`，将 RPA Engine 设计文档分离到 `project-docs\designs`。
- 将 UiPath 登录项目复制到 `rpa-authoring\uipath\login_demo`。
- 新增根工作区指令、UTF-8 默认值、项目映射和迁移验证记录。
- 验证全部 280 个受版本控制的 Client 文件，缺失文件为零、SHA-256 差异为零。
- 通过 SHA-256 验证全部 12 个 Flow 文件、37 个 UiPath 文件和三份 RPA Engine 文档。
- 重新构建 Client 依赖，运行 Client 和 Flow 测试，启动 Electron，完成一次真实 Flow 登录，并在 UiPath Studio 中加载迁移后的项目。
- 在从新工作区根目录重新打开 Codex 前，所有旧源码位置保持不变。
- 从 `D:\AutoTask-Workspace` 重新打开 Codex，并将经验证的旧 Client、开发记录和 UiPath 登录目录归档到 `D:\AutoTask-Archive\workspace-migration-2026-07-10`。
- 确认三个旧源码路径已不存在、三个归档路径均存在；`D:\UiPathProj\test1` 不在已验证迁移范围内，因此保持不变。

#### 连通性和测试结果

| 检查项 | 结果 |
| --- | --- |
| Auth `/api/v1/health` | HTTP 200 |
| Auth `/openapi.json` | HTTP 200 |
| Task `/health` | HTTP 200 |
| Task `/api/v1/autotask/health` | HTTP 200 |
| Task `/openapi.json` | HTTP 200 |
| 无 Token 访问 Auth `/api/v1/auth/me` | HTTP 401，符合预期 |
| 无 Token 访问 Task `/api/v1/autotask/tasks` | HTTP 401，符合预期 |
| 端点单元测试 | 4 项通过 |
| PostgreSQL `5432` | 可达 |
| MinIO `9000` | 可达 |
| Redis `6379` | 不可达 |
| OCR 依赖一致性 | `pip check` 通过 |
| OCR 固定图片基准 | 6/10 精确匹配（60%） |
| OCR Playwright Flow 基准，初始截图捕获 | 11/20 登录成功（55%） |
| OCR Playwright Flow 基准，最终 Canvas 捕获 | 17/20 登录成功（85%）；3/20 进入 `WAITING_HUMAN` |
| 工作区 Client 受版本控制文件比较 | 280/280 存在；SHA-256 差异为零 |
| 工作区 Flow 和 UiPath 比较 | 12/12 个 Flow 文件及 37/37 个 UiPath 文件匹配 |
| 迁移后 Client 端点测试 | 4 项通过 |
| 迁移后 Flow 单元测试 | 1.0.0：3 项通过；1.1.0：5 项通过 |
| 迁移后 Client 启动 | Electron Forge 已从新路径成功构建并启动 |
| 迁移后 Flow 浏览器冒烟测试 | 登录成功并到达 `/#/dashboard` |
| 迁移后 UiPath 项目加载 | 观察到窗口标题 `login_demo - UiPath Studio 社区` |
| 迁移期间 Client 依赖审计 | 31 个漏洞：4 个低危、27 个高危 |
| 旧路径归档 | 三个已验证来源成功移动；归档文件数量分别为 Client 51,276 个、开发记录 1 个、UiPath 37 个 |
| 归档后工作区检查 | Client HEAD 仍为 `17c87a75ffe93a9faa0d725fd79239e048b0b2fa`；预期的本地修改和未跟踪工作区文件仍存在 |

#### 决策

1. 后续将扩展 Flow 功能；当前包继续作为登录参考 Flow。
2. RPA Engine 将使用名为 `nodeskclaw_rpa_engine` 的独立 PostgreSQL 数据库。
3. Flow Registry 同时支持 GLOBAL 和 TENANT 范围。
4. 数据库访问使用 owner/migrator、app 和 readonly 角色。
5. 可以准备数据库文档和 DDL，但在获得明确授权前不会创建数据库或执行 DDL。
6. 开发记录位于所有源码仓库之外的 `D:\AutoTask-Workspace\project-docs`。
7. 每日开发日志追加到本文档，而不是单独的 Markdown 文件。
8. OCR Flow `1.1.0` 是可行性实验。Canvas 捕获将测得的端到端成功率提高到 85%，但最终样本仍有 15% 需要人工处理，因此不得将其宣传为无人值守登录。
9. `D:\AutoTask-Workspace` 是产品工作区根目录；Client、Engine、Flow、UiPath 和开发记录使用独立所有权目录。
10. 远程同步与工作区迁移保持分离；在保存并评审本地认证修改前，不得拉取存在重叠的登录修复。
11. 迁移备份存储在活跃工作区之外的 `D:\AutoTask-Archive\workspace-migration-2026-07-10`；未验证的 `D:\UiPathProj\test1` 保留原位。

#### 变更的源码文件

- `D:\AutoTask-Workspace\copilot-autotask\.env.development`
- `D:\AutoTask-Workspace\copilot-autotask\src\types\endpoint-config.ts`
- `D:\AutoTask-Workspace\copilot-autotask\src\vite-env.d.ts`
- `D:\AutoTask-Workspace\copilot-autotask\src\types.d.ts`
- `D:\AutoTask-Workspace\copilot-autotask\src\main\auth\auth-client.ts`
- `D:\AutoTask-Workspace\copilot-autotask\src\ipc\auth\handlers.ts`
- `D:\AutoTask-Workspace\copilot-autotask\src\modules\auth\components\LoginForm.tsx`
- `D:\AutoTask-Workspace\copilot-autotask\src\tests\unit\autotask-api.test.ts`
- `D:\AutoTask-Workspace\rpa-flows\rpa_flow_login_demo\1.0.0\*`
- `D:\AutoTask-Workspace\rpa-flows\rpa_flow_login_demo\1.1.0\*`
- `D:\AutoTask-Workspace\AGENTS.md`
- `D:\AutoTask-Workspace\WORKSPACE.md`
- `D:\AutoTask-Workspace\project-docs\PROJECT_CONTROL.md`
- `D:\AutoTask-Workspace\project-docs\operations\workspace-migration-2026-07-10.md`

#### 阻塞项和风险

1. 由于 Agent 未输入用户凭据，尚未验证已认证的 Client 数据。
2. Client 的 HumanAction 路径与当前 Task 服务 API 不一致。
3. 当前 Task 服务 OpenAPI 缺少 RPA Components、Settings 和 Audit Logs API。
4. Queue 集成前必须解决 Redis 连通性问题。
5. 当时 RPA Engine SDK 和 Runtime 尚不存在，因此 Python Flow 无法由 Engine 加载。
6. 最终 OCR 基准在 20 次运行中仍有 3 次需要人工处理，因此尚未证明无人值守的生产可靠性。
7. `npm ci` 报告的 31 个漏洞仍待修复依赖。
8. `origin/master` 在提交 `1c75834` 上领先一个提交；其登录修复与本地修改的认证客户端重叠。

#### 后续行动

1. 评审远程提交 `1c75834`，并与本地认证修改协调。
2. 在 AutoTask Client 中完成用户登录，并验证 Dashboard 和 Task 响应。
3. 编制 RPA Engine 数据库设计和待执行 DDL 文件。
4. 使 Client 远程端点与实际 Task 服务 API 保持一致。
5. 获得实施授权后创建 RPA Engine 仓库。
6. 在门户专用模型达到获批准的准确率目标前，OCR 登录必须保留人工回退。

## 9. 记录维护规则

1. 所有每日开发日志均保存在本文档的“每日开发日志”章节中。
2. 每个工作日创建一个 `### YYYY-MM-DD` 章节，最新日期置于最前。
3. 同一天有多个会话时，继续更新已有日期章节。
4. 每个日期必须记录目标、已完成工作、变更文件或服务、验证结果、决策、阻塞项和后续行动。
5. 决策、状态、阻塞项、项目位置或后续行动发生变化时，同步更新上方摘要章节。
6. 绝不记录密码、Token、数据库凭据、私钥或签名存储 URL。
