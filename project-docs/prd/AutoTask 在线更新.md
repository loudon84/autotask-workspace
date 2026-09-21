# AutoTask 在线更新

| 项 | 内容 |
| --- | --- |
| 版本 | v1.2（2026-09-21） |
| 状态 | **已落地。** 与 SMC-Copilot 并列第二份目录 `autotask`。Feed：`https://release.superic.com/autotask/stable/` |
| 参考实现 | `smc-copilot` 的 `apps/work`（同一台 `release.superic.com`，目录是 `work`） |
| 原则 | 打开 AutoTask 有新版就弹窗；用户点了才下载、装。开发模式不检查。 |

本文不记录密码。实现锚点见 `lat.md/client.md` 的 Online Updates。

---

## 1. 解决什么

发版不再靠每次把安装包发给用户手动装。客户端自己查 `latest.yml`，用户确认后下载并安装。

发版结构抄 SMC：他是 1（`work`），我们是 2（`autotask`），目录和验证一样，只换名字和安装包文件名。

---

## 2. release.superic.com

静态 HTTPS（nginx，只读 GET/HEAD，无鉴权、无上传 API）。SMC-Copilot 用 `/work/stable/`，AutoTask 用 `/autotask/stable/`。

```text
/data/smc-release/
├── work/                      ← SMC-Copilot
│   ├── staging/
│   ├── releases/<版本>/
│   └── stable -> releases/<版本>
└── autotask/                  ← AutoTask，结构相同
    ├── staging/
    ├── releases/<版本>/
    └── stable -> releases/<版本>
```

客户端地址：`https://release.superic.com/autotask/stable/latest.yml`。

安装包文件名：`AutoTask-Studio-<版本>-setup.exe`（不要解压 exe）。另有同名 `.blockmap`、`latest.yml`、`SHA256SUMS.txt`。

验证：能打开 `latest.yml`，且 `version` / `path` / `sha512` 与 exe 一致。

---

## 3. 总体方案（与实现一致）

- **electron-updater** generic provider，地址 `https://release.superic.com/autotask/stable/`。打包写入 `resources/app-update.yml`，运行时再 `setFeedURL`。可用 `AUTOTASK_UPDATE_URL` 覆盖，但必须仍是 `https://release.superic.com/autotask/` 下的路径。
- 仅 **Windows NSIS 安装版** 检查更新。`npm start` 开发模式不检查。
- 启动约 15 秒首查，之后每 6 小时。`autoDownload=false`，不退出时强装。
- 有新版弹窗：**发现新版本 x / 是否立即更新？** 「稍后」或「立即更新」（立即更新 = 下载完再装）。
- 下载中：**正在下载 / 请稍候。** 带百分比，可后台下载。
- 下完：**已就绪 / 安装时将关闭 AutoTask。** 「现在安装」或「稍后」。
- 系统设置默认打开 **关于**：当前版本、「检查更新」；用户菜单也有「关于与更新」。
- 安装程序参数：`--updated --force-run`，**不用 `/S`**（要显示安装进度）。`--updated` 跳过选目录和“正在运行”页。
- 日志：`<userData>/logs/updater.log`。

---

## 4. 安装目录与安装包落点

| 路径 | 用途 |
| --- | --- |
| `D:\Programs\SMC\AutoTask` | `$INSTDIR`。程序文件。快捷方式指向 `AutoTaskStudio.exe`。**禁止**把正在运行的 setup 放在这里面：NSIS 重装会清掉整个目录。 |
| `D:\Programs\SMC\updates\AutoTask` | AutoTask 在线更新安装包。其它桌面端用 `updates\<产品>`，互不影响。 |
| `D:\Programs\SMC\` 根目录 | 杀毒若拦子目录时的兜底。只处理 `AutoTask-Studio-*-setup.exe`，不动 SMC-DESP 等其它文件。 |

不要从 `%LocalAppData%\AutoTask-updater` 直接启动安装包。不要用 `elevate.exe` 拉起。

从 AutoTask 进程里启动的 setup 与客户端同属一个 Windows 作业对象。NSIS `customInit` 先经 **explorer** 再启动一份（`/autotask-detached`），关掉 AutoTask 不会把安装程序一起杀掉。只有 setup **已经拉起成功** 才 `app.quit()`；拷贝或启动失败则保持当前版本可用。

装完后只删除其它 `AutoTask-Studio-*-setup.exe`，留下刚启动的那一份。

---

## 5. 打包与安装程序

- 产物：`AutoTask-Studio-<version>-setup.exe`。
- NSIS：`productName` AutoTask，`executableName` AutoTaskStudio，`perMachine`，不允许改安装目录（避免再拼一层 `AutoTaskStudio` 文件夹）。
- `npm run release:build`：读取当时已保存的 `package.json` 版本，make，校验 `latest.yml` 的 version/sha512，拷到 `app/release/autotask/<版本>/`。
- 把该目录放到 `/data/smc-release/autotask/`，操作方式与 `work` 相同，再把 `stable` 指到该版本。
- `npm run release:publish` 需要本机 ssh/scp 能连发布服务器；不能直连时只跑 `release:build`。

---

## 6. 版本与通道

- 版本号：`app/package.json` 的 semver，手动 bump 并保存后再打包。
- 通道：只有 **stable**。electron-updater channel 为 `latest`（读 `latest.yml`）。
- 客户端只在 feed 上的版本 **高于** 本机版本时弹「发现新版本」。本机已是最新则不弹，设置里检查会显示「已是最新版本」。
- `releases/<版本>` 发出后不要覆盖；回滚切 `stable` 软链。

---

## 7. 签名

electron-builder 打包时会调用 signtool。是否被 SmartScreen / 企业策略信任以现场为准。不另做一套发版签名流程。

---

## 8. 与代码的对应

| 能力 | 位置 |
| --- | --- |
| 状态机、检查/下载/安装 | `app/src/main/app-updater.ts` |
| 安装包落点、禁止 `$INSTDIR` | `app/src/main/pending-nsis-setup.ts` |
| NSIS 参数与 explorer 再启动 | `app/src/main/delayed-setup-launch.ts`、`app/installer/install-dir.nsh` |
| 弹窗 | `app/src/features/app-update/` |
| 关于与检查更新 | `app/src/features/settings/about-pane.tsx` |
| 打包 feed | `app/forge/maker-nsis-install-dir.ts` |
| 发版脚本 | `app/scripts/build-release.ps1` |

架构说明：`lat.md/client.md` Online Updates。
