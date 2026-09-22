# AutoTask 开发总控

最后更新：2026-09-21

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
| Auth | `http://192.168.102.247:4510` | 测试服务器；**当前 4510 端口未监听**（桌面登录会失败）。不在本工作区代码扫描根内 |

天地伟业线：`develop/v2.0` / `master`。京东方线：`develop/v3.0`。两边共用这份活页；合分支时只同步仍有效的状态，不要把 [`PROJECT_CONTROL_HISTORY.md`](./PROJECT_CONTROL_HISTORY.md) 全文并回来。

## 3. 当前架构决策

1. `rpa-engine` 是独立服务。Worker Pool 是其内部模块，不是另一个服务。Python 包名仍可为 `nodeskclaw_rpa_engine`。
2. Task（`service/`）负责任务业务、WorkflowBinding、RpaRun、事件、HumanAction、调度。Engine 负责 Flow Registry、Worker、Runtime、浏览器会话、Artifact、回调。
3. RPA 执行用 Playwright + CDP。首个实现是 `MANAGED`。
4. Flow 入口 `flow.py:run(ctx)`。Flow 不自行启动浏览器、不直连 CDP、不访问业务库。门户凭据走 `ctx.credentials`。
5. Flow 包按版本存在 MinIO/S3；Worker 本地目录只是缓存。Registry 同时支持 `GLOBAL` 与 `TENANT`。
6. 跨服务 ID 用外部字符串，不对对方表建外键。
7. 可以准备 DDL；未口头授权不建库、不执行迁移。**正式库不得 `upgrade` 到京东方/v3 测库 head**（测库已有门户 JSONB `extra`、BOE 地区表、箱单排重索引）。
8. **正式门户演练与上线共用同一份 Flow。** 样例单号、`treatAsPending`、`dryRun` 进 Binding。天地伟业 SOP：`project-docs/prd/tiandy/` 下 v4.1 / 正式上线清单。
9. 换人/换门户不改 Task `.env` 和 Flow 源码：密码在门户；ERP/SDMS 基址在 Task 配置。
10. 调度中心用独立 `timers` / `timer_runs`，不再靠 Binding 循环开火。天地伟业入口默认**停用**；打开即对着已绑门户跑，正式站会写真实 SRM。
11. **Client 在线更新与 Work 共用 `release.superic.com` / `/data/smc-release`，只换目录 `autotask`。** 发版：`staging` → promote → `releases` → `stable`。程序只读 `app/.env`；git 只提交空白 `.env.example`。不做代码签名门。安装包落在 `D:\Programs\SMC\updates\AutoTask`。规格：`project-docs/prd/AutoTask 在线更新.md`。

## 4. 环境对照

| | 测库 | 正式库 |
| --- | --- | --- |
| 数据库 | `nodeskclaw_task` | `rpa_autotask` |
| Task Alembic | **v3 测库 head `f8c2e91b4a70`**（含 extra / 地区表 / 箱单排重索引） | **`d4b2f7a91e05`**（2026-09-10：category、分类文档、`timers`、`timer_runs`）。**未迁** extra / 地区表 / 排重索引 |
| Task 配置 | `.env` | `.env.product`（`SKIP_AUTO_MIGRATE=1`） |
| 天地伟业门户 | 天地伟业-芯云-正式演练 | 天地伟业-芯云（`https://supplier.tiandy.com`），`category=TIANDI` |
| 生成/提交 dryRun | 生成 **1.1.3** `dryRun=true`（本机 4610 已起、Worker 关；本机 4520 未起）/ 提交 `1.1.5` 测库为 true | 生成 **1.1.3**、**无 dryRun**；点生成会写正式 SRM |
| 扫单/回签定时器 | 已登记，默认停用 | 表已建；catalog 行要等用 `.env.product` **重启正式 4520** 后插入，默认停用 |

不要用正式 `.env.product` 覆盖测库 `.env`。本地 `restart_task_4520.ps1` 杀的是本机，不是 247。禁止对正式库 `upgrade head` 到测库 head。

## 5. 当前状态

| 项 | 状态 |
| --- | --- |
| 正式库迁移 | 已到 `d4b2f7a91e05`。门户「天地伟业-芯云」仍 ENABLED。 |
| 正式 Task 进程 | **需用 `.env.product` 重启 247 的 4520**。迁库前已在跑的进程不会补 catalog；调度中心可能仍是空表。 |
| 天地伟业定时器 | `tiandy.scan_pending`（`0 8 * * *`）/ `tiandy.sign_poll`（`*/30 * * * *`）默认停用。测库已登记。未授权不要在正式打开。 |
| 对账单生成 | **1.1.3** 已发正式 Engine 并绑「天地伟业-芯云」（无 dryRun）。测库「天地伟业-芯云-正式演练」已绑本机 4610 的 **1.1.3**（`dryRun=true`）。同 ZIP、不同 `versionId`。本机 Engine 现为发包装包模式（Worker 关，因 4520 未起）；要本地真跑需先起本机 Task，再开 Worker 重启 Engine。 |
| 对账单金额不一致 | 可确认后继续生成（`confirmAmountMismatch`）。Client 与 Task 必须一起发；旧 Client 没有确认框。随下一版安装包发出。 |
| 京东方发票箱单 | 一期已落地；09-10 体验：流水号可进详情、失败才显示重试、子任务抽屉、净重默认千克、WMS 地区未维护则停本阶段、删草稿 1.0.1。排重索引仅测库。设计：`prd/boe/AutoTask-BOE v1.0 设计-发票箱单SOP.md`。**需重启测库 4520**。 |
| 填交期 / 签章正式包 | 仍未绑。 |
| 在线更新 | **已通，0.1.26 已上 stable（2026-09-22）。** Feed `autotask/stable`。与 Work 同一台机、同一套 staging/releases/stable；promote 脚本与 Work 同构（`PROMOTION_FAILED` 错误码），门禁换成 SHA256/sha512 + `release-manifest.json` 校验，不验代码签名。`release:build` 拒绝脏工作区（`AUTOTASK_RELEASE_ALLOW_DIRTY=1` 可强制），manifest 记 gitCommit/gitBranch，线上版本可追回到确切提交（对齐 Work 的可追溯设计）。发布机用 SSH 公钥免密（密码登录会被限流掐断）。安装包发布者 `SMC`，落 `D:\Programs\SMC\updates\AutoTask`。规格：`project-docs/prd/AutoTask 在线更新.md`。 |
| 租约死循环 | 未改代码。Worker 不续租 + `WORKER_LEASE_TTL_SECONDS=60` 会把 RUNNING 打回 QUEUED，同一 Run 从头再跑。 |

## 6. 未决问题

1. 正式 4520 尚未按 `.env.product` 重启时，调度中心无 catalog 行，新列/新 API 也不在该进程上。
2. 正式站生成/提交 dryRun 已关：误点会写真实 SRM。
3. 金额确认功能未随安装包上正式 Client；只升 Task 或只升 Client 都会断。
4. 正式库禁止 `upgrade head` 到 v3 测库 `f8c2e91b4a70`，除非另授权迁 extra / 地区表 / 排重索引。
5. 扫单/收货「有数据却重复领取」：租约过期重派，不是 Flow 业务死循环。
6. `.env` 的 `SKIP_AUTO_MIGRATE=1` 若只写在文件里、启动逻辑只看进程环境，重启仍可能跑 Alembic。
7. 演示验证码 OCR 达不到无人值守，必须留 `WAITING_HUMAN`。
8. ERP 订单没有稳定幂等键；Worker 在提交后崩溃时结果不确定。
9. 填交期/签章正式包未绑；正式链路这两步仍缺。
10. 桌面登录：247 **4510 Auth 未监听**；4520 Task、4610 Engine 正常。登录只打 Auth `/account-login`，需把 Auth 服务拉起来。

## 7. 后续行动

1. 正式「天地伟业-芯云」下一笔生成走 1.1.3（每页 100 + 表头勾选，超过 100 翻页）。会**真写 SRM**。已退回待生成的那笔可重新生成。
2. 金额确认：打新 Client 安装包，并部署对应 Task；不要只发一端。
3. 未明确要跑定时扫单/回签前，不要打开正式定时器。
4. 需要填交期/签章时再发正式包并切 Binding。
5. 租约续期或提高 TTL，避免 RUNNING 被打回 QUEUED。
5. 租约续期或提高 TTL，避免 RUNNING 被打回 QUEUED。
6. 修正 `SKIP_AUTO_MIGRATE` 从 `.env` 读入启动逻辑。
7. 京东方测库 4520 重启后验收箱单一期体验改动。

## 8. 记录维护规则

1. **只改活页**：状态、决策、环境对照、未决、下一步。条目过时就删或改成现在的事实，不要在下面堆会话日记。
2. **禁止**新建 `### YYYY-MM-DD` 或「今日完成」流水，除非用户当场要求写归档。
3. 需要留长证据时写入对应 PRD/SOP，或追加到 [`PROJECT_CONTROL_HISTORY.md`](./PROJECT_CONTROL_HISTORY.md) 的归档区，不要胀回本文。
4. 绝不记录密码、Token、数据库凭据、私钥或签名存储 URL。
5. 合入 `master` / `develop/v3.0` 时保留这套规则；不要把 HISTORY 全文合并回活页。
