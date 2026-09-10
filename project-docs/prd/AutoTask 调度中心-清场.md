# AutoTask 调度中心 · 清场

| 项 | 内容 |
| --- | --- |
| 版本 | **清场（2026-09-09）** |
| 父文档 | [AutoTask 调度中心.md](./AutoTask%20调度中心.md)（**2026-09-04 架构原文不动**） |
| 状态 | 独立定时器已能用；本次只拆旧循环，不改「能不能用」 |
| 分支 | 在 `develop/v3.0` 做；合回 `develop/v2.0` 时不改已打开的开关 |
| 控制记录 | `project-docs/PROJECT_CONTROL.md` |

本文不记录密码。不替代父文档：定时器是什么、怎么登记任务、调度中心怎么维护，仍以父文档为准。

---

## 0. 一句话

进程里只准有一个闹钟：`TimerScheduler`。打开调度中心开关就会跑；这次清场不改 target、不改入口、不改库里的开关和 cron。

---

## 1. 为什么要清

父文档落地后，旧方案没有拆干净。启动时 `JobScheduler` 仍在转（`scheduler_jobs` 已全停所以打不着）；`ScanScheduler` / `SignPollScheduler` / `BoeMatchScheduler` 文件还在；`.env` 和 `/settings/schedulers` 还像能管扫单。保存 Binding 仍可能按 `config.schedule` 往 `scheduler_jobs` 插行。

两套都开时，扫单可能跑两遍。运维分不清「调度中心打开」和「旧 job / 旧设置页」谁说了算。

独立定时器本身可用：`ensure_catalog_rows` 已有行不覆盖开关和 cron；改开关热生效。默认关只是第一次插入的值，正式打开就是在用。

---

## 2. 明确不改（能不能用）

| 项 | 保持 |
| --- | --- |
| `target` | `demo.print_now` / `tiandy.scan_pending` / `tiandy.sign_poll` / `boe.pack_match` / `boe.srm_login` |
| 默认登记 | 仍默认关；已有库行的 `enabled`、`cron` **永不被代码默认值盖掉** |
| 到点入口 | `tiandy_timers.scan_pending_due` / `sign_poll_due`；`boe_timers.pack_match_due` / `srm_login_due` |
| 扫单真正干什么 | 仍 `run_scan_once`（只扫 TIANDI + 已启用扫单 Binding 的门户） |
| 回签真正干什么 | 仍 `run_sign_poll_once` |
| `/timers` 与立即执行 | 不变 |
| Client 调度中心 | 仍走 `/timers`，不改交互 |
| 表 `timers` / `timer_runs` | 不改结构；**不执行 DDL** |
| 表 `scheduler_jobs` | **不删表、不迁库**；只是进程不再读它开火 |

禁止：把天地伟业/京东方定时器改成默认启用；改 cron 默认值去覆盖运维已改的行。

---

## 3. 本次拆掉什么

启动只留 `TimerScheduler`。下列不再启动、不再作为开关来源：

1. **`JobScheduler`**（Binding 表 `scheduler_jobs` 循环）
2. **`ScanScheduler` / `SignPollScheduler` 类**（`autotask_settings` 循环）。保留 `run_scan_once`。
3. **`BoeMatchScheduler`**（已不启动，文件删掉）
4. **`GET/PUT /settings/schedulers`**（Client 已不用）
5. **Binding 保存时 `sync_scheduler_job_from_binding`**（避免再往旧表插启用行）
6. **`.env` 的 `SCAN_JOB_*` / `SIGN_POLL_JOB_*` / `BOE_PACK_MATCH_JOB_*`**。`SUCCESSOR_JOB_*` 保留。接口路径不进 `.env`（测/正式只换 `SMC_API_BASE_URL` 等域名）。

`/scheduler-jobs` API 一并下线（Client 已改 `/timers`）。Alembic `g3b8e2a91c40` 和 ORM 模型可留在仓库，避免未授权删表。

历史脚本 `scripts/backfill_scheduler_jobs.py` 标明作废，不删。

---

## 4. 正式环境

- 调度中心已打开的行：发这版代码后继续按原 cron 跑。
- 上线前看一眼正式 `scheduler_jobs`：若后来又启用了旧行，拆掉 `JobScheduler` 后那条路会停。按 2026-09-04 记录旧行已全停；若仍有启用行，先在调度中心确认独立定时器已开，再发这版。
- 正式库没有 `timers` 时，独立定时器本来就开不了。迁 `timers` / `timer_runs` 仍须口头授权，不在本次清场里执行。
- 正式 **禁止** 对着含 BOE 地区表/`extra` 的工作区 `alembic upgrade head`。

---

## 5. 验收

1. 启动日志只有「独立定时器调度器已启动」，没有「Binding 调度器已启动」。
2. 调度中心打开一条（或立即执行），`timer_runs` 有记录，业务入口仍被调用。
3. 已有 `timers` 行的 `enabled`/`cron` 重启后不变。
4. 保存扫单 Binding（即使 JSON 里还有 `schedule`）不再新增/改写 `scheduler_jobs` 启用行。
5. Client 调度中心列表/详情/立即执行与清场前一致。

---

## 6. 和父文档的关系

父文档 §1–§7、附录 A 仍有效。附录 B 的三条任务之外，现网还登记了 `boe.srm_login`（京东方-SRM晨间登录，默认 `0 7 * * *`、默认关），入口在任务模块，不写进内核。

父文档写「旧 Binding 行 / 专用调度器在入口接上并验证后再拆」——本次就是这一拆。

清场留下的到点已改为 APScheduler，见 [AutoTask 调度中心-引入APScheduler.md](./AutoTask%20调度中心-引入APScheduler.md)。
