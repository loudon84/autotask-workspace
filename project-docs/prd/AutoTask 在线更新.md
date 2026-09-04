# AutoTask 在线更新

| 项 | 内容 |
| --- | --- |
| 版本 | v1（2026-09-04） |
| 状态 | **客户端与发版脚本已落地（2026-09-04）；服务器侧 `/autotask/` 目录待配，端到端未验证。** |
| 参考实现 | `D:\work_space260811\smc-copilot` 的 `apps/work`（SMC-Copilot 桌面端，已在生产使用同一套机制） |
| 原则 | 用户打开 AutoTask，有新版就弹窗提示，点了才下载、下完点了才安装。不再每次发安装包让人手动装。 |

本文不记录密码。

---

## 1. 解决什么

现在每次发版：打包 → 把安装包发给用户 → 用户手动安装。门户、调度中心这类页面改动也要走这一趟，慢且容易有人不更新。

目标：客户端自己检查更新、自己下载、用户确认后安装。发版变成「跑一次发布脚本」。

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

发布 = SCP 上传到 staging → 服务器上跑 promote 脚本 → 原子切换 `stable` 软链。回滚 = 软链指回旧版本目录（不影响已经更新完的客户端）。

nginx 按整个根目录服务，加 `autotask/` 目录**不需要改 nginx 配置**。

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

SSH 不通，走**手动搬运**：

1. 改 `app/package.json` 版本号（如 0.1.1 → 0.1.2）。
2. `npm run release:build`：打出 NSIS 安装包 + `latest.yml` + `.blockmap`，校验后暂存到 `app\release\autotask\<版本>\`。
3. 把整个版本文件夹**手动拷到服务器**（远程桌面 / 共享盘 / U 盘均可）：
   放到 `/data/smc-release/autotask/staging/<版本>-manual/`。
4. 服务器上执行一条命令（移入 releases、校验 sha256、原子切 stable 软链）：

   ```bash
   bash /data/smc-release/autotask/promote-autotask-release.sh <版本> <版本>-manual
   ```

5. 验证：`https://release.superic.com/autotask/stable/latest.yml` 里的版本号正确。
6. 完。客户端下一轮检查（最迟 6 小时，重启则 15 秒）就会看到新版。

（若以后开通了 SSH 免密，`npm run release:publish` 可自动完成 3-5 步。）

---

## 6. 服务器侧一次性配置

需要有 release.superic.com SSH 权限的人执行一次：

1. 建目录 `/data/smc-release/autotask/{staging,releases}`。
2. 放两个脚本：`promote-autotask-release.sh`、`rollback-autotask-stable.sh`（照抄 smc 的改 `work` → `autotask`）。
3. 验证：`https://release.superic.com/autotask/` 路径可 GET（放一个测试文件）。

nginx 不用动。

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

| 问题 | 选项 |
| --- | --- |
| 服务器侧谁配 | 有 SSH 权限的人直接配 / 找运维加目录 / 先写脚本之后执行 |
| 灰度 | 一期不做（全量 stable）；以后要灰度可加 beta 通道 |
| 签名 | 一期跳过 / 一期就做 |

---

## 10. 实施步骤

1. 服务器侧：建 `autotask/` 目录 + promote/rollback 脚本（§6，一次性）。
2. 客户端：装 electron-updater、改 maker publish 配置、安装包名带版本、updater 主进程模块、更新弹窗 UI（§4）。
3. 发布脚本：build/validate/publish 三个脚本（§5）。
4. 自测：本机装 0.1.2 → 发一个 0.1.3 到自己的 stable → 验证弹窗、下载、安装全流程。
5. 随下一版天地伟业发布一起出包，用户最后一次手动装，之后都在线更新。
