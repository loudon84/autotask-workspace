# AutoTask 开发总控

最后更新：2026-09-11

## 1. 用途

本文档是 AutoTask 的**活页总控**：当前决策、状态、阻塞和下一步。不是日报、不是工作汇报。

开始新会话前读本文。已验证的工作若改变了状态、决策、阻塞、路径或下一步，**只改对应章节**。不要追加「每日开发日志」。历史流水在 [`PROJECT_CONTROL_HISTORY.md`](./PROJECT_CONTROL_HISTORY.md)。

不得记录密码、访问令牌、数据库凭据、私钥或带签名的对象存储 URL。

## 2. 项目位置

| 项目 | 位置 | 状态 |
| --- | --- | --- |
| AutoTask 产品工作区 | 本仓库根（Cursor workspace） | 活跃工作区 |
| AutoTask Client | `app/` | 开发中 |
| Task 服务 | `service/` | 测试 `http://192.168.102.247:4520` |
| RPA Engine | `rpa-engine/` | 测试基线可运行 |
| RPA Flow | `rpa-flows/` | 允许扫描的代码根 |
| RPA authoring | `rpa-authoring/` | 登录演示已完成 |
| Auth | `http://192.168.102.247:4510` | 测试服务器可达；**不在**本工作区代码扫描根内 |

天地伟业线在 `develop/v2.0`（可再合 `master`）。京东方线在 `develop/v3.0`。本活页以天地伟业为准；合 v3 时只同步仍有效的状态，不要把归档流水拷回来。

## 3. 当前架构决策

1. `rpa-engine` 是独立服务。Worker Pool 是其内部模块，不是另一个服务。Python 包名仍可为 `nodeskclaw_rpa_engine`。
2. Task（`service/`）负责任务业务、WorkflowBinding、RpaRun、事件、HumanAction、调度。Engine 负责 Flow Registry、Worker、Runtime、浏览器会话、Artifact、回调。
3. RPA 执行用 Playwright + CDP。首个实现是 `MANAGED`。
4. Flow 入口 `flow.py:run(ctx)`。Flow 不自行启动浏览器、不直连 CDP、不访问业务库。门户凭据走 `ctx.credentials`。
5. Flow 包按版本存在 MinIO/S3；Worker 本地目录只是缓存。Registry 同时支持 `GLOBAL` 与 `TENANT`。
6. 跨服务 ID 用外部字符串，不对对方表建外键。
7. 可以准备 DDL；未口头授权不建库、不执行迁移。**正式库不得 `upgrade` 到京东方/v3 测库 head**（测库可能已有额外 JSONB、区域表、箱单唯一索引）。
8. **正式门户演练与上线共用同一份 Flow。** 样例单号、`treatAsPending`、`dryRun` 进 Binding。SOP：`project-docs/prd/tiandy/` 下 v4.1 / 正式上线清单。
9. 换人/换门户不改 Task `.env` 和 Flow 源码：密码在门户；ERP/SDMS 基址在 Task 配置。
10. 调度中心用独立 `timers` / `timer_runs`，不再靠 Binding 循环开火。天地伟业入口默认**停用**；打开即对着已绑门户跑，正式站会写真实 SRM。

## 4. 环境对照

| | 测库 | 正式库 |
| --- | --- | --- |
| 数据库 | `nodeskclaw_task` | `rpa_autotask` |
| Task Alembic（天地伟业线） | `d4b2f7a91e05`（v3 测库可能更前，勿混） | **`d4b2f7a91e05`**（2026-09-10 已迁） |
| Task 配置 | `.env` | `.env.product`（`SKIP_AUTO_MIGRATE=1`） |
| 门户 | 天地伟业-芯云-正式演练 | 天地伟业-芯云（`https://supplier.tiandy.com`） |
| 生成/提交 dryRun | 生成 **1.1.3** `dryRun=true`（本机 4610 已起、Worker 关；本机 4520 未起）/ 提交 `1.1.5` 测库为 true | 生成 **1.1.3**、**无 dryRun**；点生成会写正式 SRM |
| 扫单/回签定时器 | 已登记，默认停用 | 表已建；catalog 行要等用 `.env.product` **重启正式 4520** 后插入，默认停用 |

不要用正式 `.env.product` 覆盖测库 `.env`。本地 `restart_task_4520.ps1` 杀的是本机，不是 247。

## 5. 当前状态

| 项 | 状态 |
| --- | --- |
| 正式库迁移 | 已到 `d4b2f7a91e05`（category 回填 TIANDI、分类文档、`timers`、`timer_runs`）。门户「天地伟业-芯云」仍 ENABLED。 |
| 正式 Task 进程 | **需用 `.env.product` 重启 247 的 4520**。迁库前已在跑的进程不会补 catalog；调度中心可能仍是空表。 |
| 天地伟业定时器 | `tiandy.scan_pending`（`0 8 * * *`）/ `tiandy.sign_poll`（`*/30 * * * *`）默认停用。测库已登记。未授权不要在正式打开。 |
| 对账单生成 | **1.1.3** 已发正式 Engine 并绑「天地伟业-芯云」（无 dryRun）。测库「天地伟业-芯云-正式演练」已绑本机 4610 的 **1.1.3**（`dryRun=true`）。同 ZIP、不同 `versionId`。本机 Engine 现为发包装包模式（Worker 关，因 4520 未起）；要本地真跑需先起本机 Task，再开 Worker 重启 Engine。 |
| 对账单金额不一致 | 可确认后继续生成（`confirmAmountMismatch`）。Client 与 Task 必须一起发；旧 Client 没有确认框。需新安装包；在线更新服务器目录尚未配好。 |
| 填交期 / 签章正式包 | 仍未绑。 |
| 在线更新 | Client 已接 electron-updater；发版脚本已有。服务器 `/data/smc-release/autotask/` 与端到端验证未做。 |
| 租约死循环 | 未改代码。Worker 不续租 + `WORKER_LEASE_TTL_SECONDS=60` 会把 RUNNING 打回 QUEUED，同一 Run 从头再跑。 |

## 6. 未决问题

1. 正式 4520 尚未按 `.env.product` 重启时，调度中心无 catalog 行，新列/新 API 也不在该进程上。
2. 正式站生成/提交 dryRun 已关：误点会写真实 SRM。
3. 金额确认功能未随安装包上正式 Client；只升 Task 或只升 Client 都会断。
4. 正式库禁止 `upgrade head` 到 v3/京东方测库 revision，除非另授权。
5. 扫单/收货「有数据却重复领取」：租约过期重派，不是 Flow 业务死循环。
6. `.env` 的 `SKIP_AUTO_MIGRATE=1` 若只写在文件里、启动逻辑只看进程环境，重启仍可能跑 Alembic。
7. 演示验证码 OCR 达不到无人值守，必须留 `WAITING_HUMAN`。
8. ERP 订单没有稳定幂等键；Worker 在提交后崩溃时结果不确定。
9. 填交期/签章正式包未绑；正式链路这两步仍缺。
10. 在线更新：本机到 `release.superic.com:443` 不通（内网 `192.168.102.104`）；服务器目录与 SSH 权限未配。

## 7. 后续行动

1. 正式「天地伟业-芯云」下一笔生成走 1.1.3（每页 100 + 表头勾选，超过 100 翻页）。会**真写 SRM**。已退回待生成的那笔可重新生成。
2. 金额确认：打新 Client 安装包，并部署对应 Task；不要只发一端。
3. 未明确要跑定时扫单/回签前，不要打开正式定时器。
4. 需要填交期/签章时再发正式包并切 Binding。
5. 租约续期或提高 TTL，避免 RUNNING 被打回 QUEUED。
6. 在线更新：配服务器目录与 promote，再做一次安装包升级验证。
7. 修正 `SKIP_AUTO_MIGRATE` 从 `.env` 读入启动逻辑。

## 8. 记录维护规则

1. **只改活页**：状态、决策、环境对照、未决、下一步。条目过时就删或改成现在的事实，不要在下面堆会话日记。
2. **禁止**新建 `### YYYY-MM-DD` 或「今日完成」流水，除非用户当场要求写归档。
3. 需要留长证据时写入对应 PRD/SOP，或追加到 [`PROJECT_CONTROL_HISTORY.md`](./PROJECT_CONTROL_HISTORY.md) 的归档区，不要胀回本文。
4. 绝不记录密码、Token、数据库凭据、私钥或签名存储 URL。
5. 合入 `master` / `develop/v3.0` 时保留这套规则；不要把 HISTORY 全文合并回活页。
