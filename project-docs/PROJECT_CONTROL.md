# AutoTask 开发总控

最后更新：2026-08-25

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
10. 可以准备数据库设计和 DDL，但目前尚未授权创建数据库或执行 DDL。

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

### 2026-08-25

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
