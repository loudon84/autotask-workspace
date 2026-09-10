---
name: 引入 APScheduler
overview: 把调度中心到点从手写 30 秒循环换成 APScheduler 3（Asia/Shanghai）。产品、登记、入口、表结构不动；不迁库。dow 按 crontab 语义垫片后再交给框架。
todos:
  - id: dep
    content: pyproject.toml 加 apscheduler>=3.10,<4
    status: completed
  - id: unix-cron
    content: crontab→APScheduler 垫片（dow 数字改英文名，范围展开；开火与 next_run_at 共用）
    status: completed
  - id: scheduler
    content: TimerScheduler 用 APScheduler；add_job id 固定为 timer.id；保留 _fire/notify
    status: completed
  - id: next-run
    content: next_run_at 与保存校验走垫片+CronTrigger；get_next_fire_time 为 None 则 422
    status: completed
  - id: tombstone
    content: cron_schedule.py 文件头墓碑：Timer 路径禁止 import
    status: completed
  - id: tests
    content: dow 三条、2/30 走 timer_service、同步/时区/_fire；跑 pytest
    status: completed
  - id: docs
    content: lat.md、PRD 状态、PROJECT_CONTROL；lat check
    status: completed
isProject: false
---

# 引入 APScheduler

依据：[project-docs/prd/AutoTask 调度中心-引入APScheduler.md](project-docs/prd/AutoTask 调度中心-引入APScheduler.md)。父文档、清场结论、任务入口均不改。不执行 DDL、不默认启用 catalog、不碰作废排重。

和 Java 死循环换成 Spring 调度同一件事：谁负责「到点」从手写 tick 换成框架。

```mermaid
flowchart LR
  timersTable[timers表]
  shim[unixCron垫片]
  syncLoop[30秒只同步启用行]
  aps[APScheduler CronTrigger]
  notify[notify target]
  timersTable --> syncLoop
  syncLoop --> shim
  shim -->|from_crontab| aps
  aps -->|到点| notify
```

30 秒循环只负责把库里的开关/cron 同步进框架，**不再自己判断是否到点**。库里仍存运维写的 **crontab 5 段**（dow `0`/`7`=周日）；交给 APScheduler 之前过垫片。

## 依赖

在 [service/pyproject.toml](service/pyproject.toml) 增加 `apscheduler>=3.10,<4`。`tzdata` 已有。不新增 `.env` 键；时区写死 `Asia/Shanghai`。

## crontab dow 垫片（必须，不能直接 from_crontab）

APScheduler 3 的 `day_of_week`：`0`=周一，只认 0–6，`7` 报错。crontab：`0`/`7`=周日，`1-5`=周一到周五。现网表达式虽没用 dow，契约是 5 段 cron；不垫片则 `0 8 * * 1-5` 会变成周二到周六。

新建小模块（例如 [service/app/services/unix_cron.py](service/app/services/unix_cron.py)）：`to_apscheduler_crontab(expr) -> str`。只改 **第 5 段**：

- `*` 不动；已是 `mon`/`sun` 等名字则原样。
- 数字：`0`/`7`→`sun`，`1`→`mon` … `6`→`sat`。
- 列表、范围、步长都要处理。**范围展开成名字列表**，不要输出 `sun-sat`（APScheduler 名字顺序是 mon…sun，跨周范围会错）。例如 `1-5`→`mon,tue,wed,thu,fri`；`0-6`→七天名字；`0,6`→`sun,sat`。

`TimerScheduler.add_job` 和 `timer_service.next_run_at` / 保存校验 **必须走同一函数**，禁止一处垫片一处直接 `from_crontab`。

## 改 [service/app/services/timer_scheduler.py](service/app/services/timer_scheduler.py)

- `AsyncIOScheduler(timezone="Asia/Shanghai")`。
- 垫片后再 `CronTrigger.from_crontab(..., timezone="Asia/Shanghai")`。
- `add_job`：**`id=str(timer.id)` 写死**（`replace_existing=True` / `remove_job` 都靠这个）。`args` 另传 `timer_id` + `target`，不挂 ORM。
- `misfire_grace_time=120`，`max_instances=1`，`coalesce=True`，`replace_existing=True`。
- `start()` / `stop()`：启动框架 + 同步协程；表不存在则跳过（现 `ProgrammingError`）。
- `_fire` / `timer_runs` / `notify` 原样保留。
- 非法 cron：不加入调度器，warning。

## 「下次触发」与保存校验

[service/app/services/timer_service.py](service/app/services/timer_service.py)：垫片 + `CronTrigger` + `get_next_fire_time`。

**`get_next_fire_time` 返回 `None` → 422**（与现在 `0 0 30 2 *` 拒绝一致）。`from_crontab` 对这种表达式结构合法、静默接受，不能只看解析是否抛错。列表里已有脏行则 `next_run_at` 可以是 `None`。JSON 带 `+08:00`。不改 Client。

`china_clock.CHINA_TZ` 可继续当常量；`now_china()` 不再参与开火。

## `cron_schedule.py` 墓碑（本轮不删文件）

[service/app/services/cron_schedule.py](service/app/services/cron_schedule.py) 文件头写明：仅为历史 Binding JSON / `scheduler_job_service` 解析保留；**Timer 路径和新代码禁止 import**。开火和 `next_run_at` 不走它。

[service/app/main.py](service/app/main.py) 仍只 `TimerScheduler.start()`。不改 register / `ensure_catalog_rows`。

## 测试

[service/tests/test_timer_scheduler.py](service/tests/test_timer_scheduler.py)：

- 同步：启用 `add_job`（**job id == timer.id**）；停用 `remove_job`；非法 cron 不挂。
- 时区：`5 9 * * *` 下次是上海 09 点。
- 不补跑：下次在「现在」之后。
- `_fire`：直接调 SUCCESS / NO_LISTENER / FAILED。
- `misfire_grace_time==120`、`max_instances==1`。

dow 三条（垫片或 `next_run_at`，以真正 Trigger 为准，不要只测字符串替换）：

- `0 8 * * 1-5`：下次是工作日（周一到周五）。
- `* * * * 0` 与 `* * * * 7`：都是周日。

[service/tests/test_timer_service.py](service/tests/test_timer_service.py)：

- 更新 `next_run_at` 断言（aware 上海）。
- **`0 0 30 2 *` 保存路径 422**（不能只靠 `test_scheduler_config.py`：那条测的是旧 `CronSchedule`）。

`test_scheduler_config.py` 可留，但不算 Timer 校验覆盖。

在 `service/` 跑相关 pytest，不连用户库、不点立即执行。

## 文档

- lat.md：Due Time Uses APScheduler 改为已落地；写明 crontab dow 垫片。
- PRD 状态；PROJECT_CONTROL（需重启 4520；UTC 主机到点纠正为北京）。
- `npx lat check`。

## 明确不做

Client、catalog 默认关、任务入口、`timers` DDL、正式库迁移、匹配 409、删除 `cron_schedule.py`。
