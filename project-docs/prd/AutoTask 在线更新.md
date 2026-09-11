# AutoTask 在线更新

| 项 | 内容 |
| --- | --- |
| 版本 | v1.1（2026-09-11） |
| 状态 | **抄 SMC `work`。我们是并列第二份 `autotask`。** 0.1.2 zip 已打好，交给同事按 `work` 同样方式放。 |
| 参考实现 | `D:\work_space260811\smc-copilot` 的 `apps/work`（SMC-Copilot 桌面端，已在生产使用同一套机制） |
| 原则 | 用户打开 AutoTask，有新版就弹窗提示，点了才下载、下完点了才安装。不再每次发安装包让人手动装。 |

本文不记录密码。

---

## 1. 解决什么

现在每次发版：打包 → 把安装包发给用户 → 用户手动安装。门户、调度中心这类页面改动也要走这一趟，慢且容易有人不更新。

目标：客户端自己检查更新。发版抄 SMC：他是 1（`work`），我们是 2（`autotask`），目录和验证一样，只换名字。

---

## 2. release.superic.com 是什么

一台已经在跑的静态文件服务器（nginx，只读，只支持 GET/HEAD，无鉴权、无上传 API）。SMC-Copilot 的在线更新已经在用它。

按产品分目录：

```text
/data/smc-release/
├── work/                      ← SMC-Copilot 在用
│   ├── staging/<版本-时间戳>/   ← 上传暂存
│   ├── releases/<版本>/        ← 正式版本目录，写入后不可变
│   └── stable -> releases/<版本>  ← 软链，客户端喂这个路径
└── autotask/                  ← 我们要加的，结构同上
```

客户端看到的地址：`https://release.superic.com/autotask/stable/latest.yml`。

发布不走 nginx 上传。他项目已经是 1：

```text
/data/smc-release/work/releases/<版本>/
/data/smc-release/work/stable → 当前版
https://release.superic.com/work/stable/latest.yml
```

我们加入就是 2，结构照抄，只换目录名和安装包文件名：

```text
/data/smc-release/autotask/releases/<版本>/
/data/smc-release/autotask/stable → 当前版
https://release.superic.com/autotask/stable/latest.yml
```

nginx 不用改。验证也抄他的：能打开 `.../autotask/stable/latest.yml`，且 `version` / `path` 对得上，和现在打开 `.../work/stable/latest.yml` 一样就算成。

每次发版：我们打好版本目录（或 zip）交给同事；他按放 `work` 的方式放 `autotask`。

安装包文件名他那边写死 `smc-copilot-<版本>-setup.exe`，我们这边对应是 `AutoTask-Studio-<版本>-setup.exe`。不要解压 exe。

---

## 3. 总体方案

- 客户端用 **electron-updater**（generic provider），喂 `https://release.superic.com/autotask/stable/`。
- 更新地址在**打包时烧进安装包**（`app-update.yml`），运行时不改。
- 交互与 SMC-Copilot 一致：**用户确认式**。启动后自动检查 → 有新版弹窗（可稍后）→ 用户点下载 → 进度条 → 下完提示「现在安装 / 稍后」。不静默下载、不退出时强装。
- 只有 Windows 打包版（NSIS，非绿色版）启用更新；开发模式不检查。

---

## 4. 客户端要改什么（`app/`）

| 项 | 现状 | 改成 |
| --- | --- | --- |
| 更新库 | 没有 electron-updater；`update-electron-app` 是指向模板仓库的死代码（从没被调用） | 装 `electron-updater`，删掉死代码 |
| 打包 publish 配置 | 自定义 NSIS maker（`forge/maker-nsis-install-dir.ts`）里 `publish: null`，不生成 `latest.yml` | `publish: { provider: "generic", url: "https://release.superic.com/autotask/stable/", channel: "latest" }` |
| 安装包文件名 | 固定 `AutoTask-Studio.exe`，不带版本号 | 带版本号，如 `AutoTask-Studio-0.1.2-setup.exe`（否则缓存和回滚会乱） |
| 主进程更新逻辑 | 无 | 新增 updater 模块：启动 15 秒后首次检查，之后每 6 小时一次；检查/下载/安装三个动作经 IPC 暴露给界面 |
| 更新 UI | 无 | 三个弹窗：有新版（下载/稍后）、下载进度、可安装（现在装/稍后）；参考 smc `apps/work/src/renderer/src/update/` |

参考代码（smc 侧，照抄改路径）：

- 主进程：`smc-copilot/apps/work/src/main/app/updater.ts`
- 弹窗：`smc-copilot/apps/work/src/renderer/src/update/`（AppUpdateProvider + 三个 Dialog）
- 打包配置：`smc-copilot/apps/work/electron-builder.yml` 的 `publish` 段

---

## 5. 发版流程（以后每次发版）

和 SMC 发 `work` 一样，只是产物在 `autotask`。

1. 改 `app/package.json` 版本号。
2. `npm run release:build`。
3. 把 `app/release/autotask/<版本>/`（或打好的 zip）交给同事，按 `work` 同样方式放到 `autotask/`。

目录里是：`AutoTask-Studio-<版本>-setup.exe`、同名 `.blockmap`、`latest.yml`、`SHA256SUMS.txt`。

## 6. 服务器侧

第一次在 `/data/smc-release/` 下建 `autotask/`，结构抄 `work/`（`staging/`、`releases/`、`stable` 软链）。以后每个新版本往 `releases/<版本>/` 放一份，再把 `stable` 指过去。nginx 不用改。

---

## 7. 版本与通道

- 版本号：`app/package.json` 的 semver，手动 bump。
- 通道：只有 **stable** 一个。electron-updater 的 channel 固定 `latest`（读 `latest.yml`）。
- 版本目录不可变：发出去的 `releases/<版本>` 永不覆盖，出问题用回滚脚本切软链。

---

## 8. 签名（可选，不阻塞）

SMC-Copilot 的安装包有 Authenticode 签名。AutoTask 目前没签名——electron-updater 不要求签名也能更新，但用户安装/更新时 Windows SmartScreen 可能拦。建议后续补签名，一期不做。

---

## 9. 开放问题

| 问题 | 结论 |
| --- | --- |
| 服务器谁操作 | **已定**：每次新版本把最新包交给同事。我们不登 release、不指定他用哪条脚本。 |
| 灰度 | 一期不做（全量 stable）；以后要灰度可加 beta 通道 |
| 签名 | 一期跳过 |

---

## 10. 实施步骤

1. ~~客户端接入 electron-updater、弹窗、带版本号安装包、`release:build`。~~ 已完成。
2. 下次发 Client：bump 版本，`npm run release:build`，把 `app/release/autotask/<版本>/` 交给同事。
3. 已装旧包的用户手动装这一次；之后打开客户端即可在线更新。
