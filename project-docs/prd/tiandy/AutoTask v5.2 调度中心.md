# AutoTask v5.2 调度中心

| 项 | 内容 |
| --- | --- |
| 版本 | **v5.2**（本文件替换 2026-08-24 先前「两个全局 cron」方案） |
| 状态 | **已作废（2026-09-04）**。定时器挂 Binding 的模型推倒。现行需求与设计见 [AutoTask 调度中心](../AutoTask%20调度中心.md) |
| 实施计划 | [`.cursor/plans/v5.2_调度中心_binding任务.plan.md`](../../.cursor/plans/v5.2_调度中心_binding任务.plan.md)（随 Binding 方案一并作废，勿按此实施） |
| 原则 | ~~定时器挂在 Binding 上~~ **作废**。下文仅作历史，不要按此开发。 |

---

## 1. 痛点

先前实现把扫单、回签轮询做成全站两个开关，配置写在 `autotask_settings`：

- 门户一多，列表里分不清这条定时器是谁的、干什么；
- 扫单/回签检查逻辑是天地伟业客户订单定制的，不能当平台能力复用；
- 运维改 cron 要和「功能从哪来」脱节，设置页也不该承载越来越多的硬编码任务。

`.env` 改定时器要重启的问题，上一版已经用 cron + 热加载解决；**本版改的是产品模型和归属**，不是再发明一种 cron 语法。

## 2. 范围

| | 内容 |
| --- | --- |
| 纳入 | 调度任务档案（一行 = 一条 Binding）；管理中心列表/详情；详情改 cron/开关；详情下执行任务日志；Binding 保存时按规则插入；现有扫单、回签轮询迁到该模型 |
| 不纳入 | 用户在调度中心「新建」定时器；上传/发布 Flow 插入定时器；编辑 Binding JSON 覆盖已有调度行；JSON 去掉 `schedule` 删除调度行；`SUCCESSOR_JOB_*`；Engine 侧业务调度 |

## 3. 产品结构

### 3.1 入口

管理中心（侧栏与运行监控、门户并列）增加 **调度中心**：

- 列表：项目里全部调度任务；可筛选启用 / 停用；
- 详情：维护 cron 与开关；展示下次触发；
- 详情下方：该定时器触发产生的执行任务日志（按 Binding 关联的 `automation_tasks`）。

系统设置页上的「两个全局调度器」卡片删除。

### 3.2 命名（门户专有必填）

显示名格式：`门户名-流程名-动作名`，三段都有值。

例：`天地伟业-客户订单-回签轮询`、`天地伟业-客户订单-扫单`。

名称在首次插入时生成并落库，之后不因改 JSON 而重算覆盖（门户改名是否重算不在本期；本期按插入时的门户名固化）。

### 3.3 谁创建、谁改

- **创建**：开发保存 Binding（创建或更新）且 `config.schedule` 首次出现时，Task **自动插入**调度行。用户不点新建。
- **改 cron/开关**：只在调度中心详情。
- **不是创建点**：上传 Flow、只改 Flow 版本号。

## 4. Binding config

`schedule` 只做**第一次插入的声明**，不是运行时真相。

```json
{
  "searches": [],
  "schedule": {
    "enabled": true,
    "cron": "0 8 * * *",
    "processName": "客户订单",
    "actionName": "扫单"
  }
}
```

| 字段 | 含义 |
| --- | --- |
| `enabled` | 首次插入时的默认开关 |
| `cron` | 首次插入时的默认 5 段 cron（本地服务器时间） |
| `processName` | 名称第二段，如 `客户订单` |
| `actionName` | 名称第三段，如 `扫单` / `回签轮询` |

校验：`cron` 必须能解析且存在下一次触发；`processName`、`actionName` 非空。非法则 Binding 保存失败（422），不插调度行。

## 5. 数据归属

调度行 **必须绑定 `binding_id`（唯一）**。用它判断「是否已经创建过」。

| 动作 | 调度中心 |
| --- | --- |
| 新建 Binding，且带合法 `schedule` | 插入一行：名称、默认 cron、默认开关 |
| 已有调度行，再改 Binding JSON（含改 cron、改 enabled、去掉 `schedule`） | **忽略 `schedule`，不覆盖、不删除** |
| 只升级 Flow 版本（如 1.1.3 → 1.1.4） | 同一行，继续打这条 Binding |
| Binding 停用 | 对应调度行停用（不再触发） |
| Binding 删除（软删） | 对应调度行停用或软删，不再触发 |
| 调度中心停用 | 只停定时器，Binding 仍在 |

运行时以调度表的 `enabled` + `cron` 为准。Binding JSON 里过期的 `schedule.cron` 可以和详情不一致，这是预期。

## 6. 触发与执行

- 调度器常驻：加载所有 **启用** 的调度行；到点按剩余秒数醒（沿用现有语义：不补跑上一拍、不固定傻睡 30 秒）。
- 到点只为 **该 Binding 所属门户** 执行：
  - 模板 `srm_scan_pending_orders`（`SCAN_TASK_TYPE`）：为该门户建扫单任务（现有 `create_scan_task`）；
  - 模板 `srm_check_reply_status`（`CHECK_REPLY_TEMPLATE_CODE`）：只轮询该门户下的待回签/待签章客户订单实例（现有 `run_sign_poll_once` 加门户过滤）。
- 换一家门户 = 再绑一条带 `schedule` 的 Binding，自动多一行，不共用天地伟业检查实现。
- 执行日志 = 该 `workflow_binding_id` 下、由调度触发产生的任务（可与手工「立即扫单/立即回签」并列展示，详情注明来源即可）。

热加载：Binding 新插入的行、详情改 cron，最长约 30 秒被调度循环看到。

## 7. 接口与权限

权限与现门户管理一致：`admin` / `operator` / 超管可改开关和 cron。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/autotask/scheduler-jobs` | 列表；query `enabled` 可选 |
| GET | `/api/v1/autotask/scheduler-jobs/{id}` | 详情 + `next_run_at` |
| PATCH | `/api/v1/autotask/scheduler-jobs/{id}` | 只改 `enabled`、`cron`；非法 cron 422；写审计 |
| GET | `/api/v1/autotask/scheduler-jobs/{id}/tasks` | 该 Binding 关联执行任务（分页） |

废弃 Client 对 `GET/PUT /settings/schedulers` 的依赖（接口可暂留以免旧页报错，设置页不再使用）。

## 8. 存储

新表 `scheduler_jobs`（名称以迁移为准），至少：

- `id`
- `binding_id`（唯一，未删除行）
- `portal_account_id`（列表筛选/展示）
- `name`（已生成的显示名）
- `enabled`
- `cron`
- 时间戳、软删

**迁移文件可以提交；未获用户授权不得对数据库执行 DDL。** 现有 `autotask_settings` 的 `scheduler.signPoll.*` / `scheduler.scan.*` 不再作为运行时真相；回填完成后可停止读取。

已有扫单/回签 Binding：一次性给 config 补上 `schedule` 并走插入逻辑（脚本或受控 PATCH），不是靠上传 Flow。

## 9. 验收

- 给天地伟业扫单 Binding 写入合法 `schedule` 并保存 → 调度中心出现 `天地伟业-客户订单-扫单`，默认 cron 为声明值。
- 再改 Binding JSON 的 cron 或去掉 `schedule` → 调度行 cron/开关不变、行不删。
- 只升 Flow 版本 → 仍是同一行。
- 调度中心改 cron 后热生效；到点只给该门户建任务。
- 列表可筛启用/停用；详情能看到执行任务。
- Binding 停用后该行不再触发。
- 用户无法在调度中心手工「新建」一条无 Binding 的定时器。

## 10. 本期落地顺序

1. 表 + 插入规则 + Binding 钩子（含单测）。
2. 按门户触发扫单/回签，替换两个全局调度器。
3. 管理中心列表/详情/任务日志；撤掉设置页全局卡片。
4. 回填现网两条 Binding；授权后再执行迁移。

`SUCCESSOR_JOB_*` 是否同样挂 Binding，不在本期。
