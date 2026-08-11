# Flow 包上传与发布操作手册

本文面向已经完成部署的 RPA Engine，说明如何把一个符合规范的 Flow ZIP 包上传到 Flow Registry、发布为可绑定版本，并把精确版本信息交给 Task。

## 1. 接口调用顺序

推荐按以下顺序执行：

| 顺序 | 方法 | 接口 | 用途 |
| --- | --- | --- | --- |
| 1 | `GET` | `/health/ready` | 确认数据库和对象存储已经就绪 |
| 2 | `POST` | `/api/v1/flows/packages` | 上传 ZIP，静态校验并创建 DRAFT 版本 |
| 3 | `POST` | `/api/v1/flow-versions/{flowVersionId}/validate` | 从对象存储重新读取并校验包 |
| 4 | `POST` | `/api/v1/flow-versions/{flowVersionId}/publish` | 发布精确版本 |
| 5 | `GET` | `/api/v1/flow-versions/{flowVersionId}` | 回读发布状态、UUID 和 checksum |
| 6 | `POST` | `/api/v1/flow-versions/validate-binding` | 验证 Task 是否可以绑定该精确版本 |

其中第 3 步是推荐的显式检查。上传和发布自身也会校验包，但保留该步骤更利于联调和问题定位。

## 2. 前置条件

开始前确认：

- Engine 的数据库迁移已完成。
- MinIO/S3 已启用，配置的 Bucket 已提前创建。
- `GET /health/ready` 返回 HTTP 200。
- 响应中的 `database` 和 `objectStorage` 均为 `healthy`，并且所有 `required=true` 的依赖均为 `healthy`。
- 已准备符合 Flow 规范的 ZIP 文件。

所有 `/api/v1/**` 请求必须携带：

```text
X-Actor-Id: <本次操作人或调用系统标识>
```

当前该 Header 用于测试环境的审计上下文，不等同于生产鉴权。若上传 `TENANT` 范围的 Flow，还必须在上传及所有后续请求中携带：

```text
X-Tenant-Id: <租户 ID>
```

`GLOBAL` Flow 不需要 `X-Tenant-Id`。

## 3. Flow ZIP 基本约束

ZIP 根目录至少应包含：

```text
manifest.json
flow.py
```

不要在 ZIP 外再包一层同名目录。`manifest.json` 示例：

```json
{
  "rpaFlowId": "rpa_flow_supplier_example",
  "name": "供应商门户示例 Flow",
  "version": "1.0.0",
  "engineType": "PLAYWRIGHT_CDP",
  "entrypoint": "flow.py:run",
  "supportedWorkflowCodes": [
    "supplier_example"
  ],
  "supportedPortalTypes": [],
  "inputSchema": [
    {
      "name": "po_no",
      "type": "string",
      "required": true,
      "description": "采购订单号"
    }
  ],
  "capabilities": [
    "PLAYWRIGHT_CDP",
    "BROWSER_SESSION_MANAGED",
    "SCREENSHOT",
    "DOWNLOAD"
  ],
  "minimumEngineVersion": "0.5.0"
}
```

`flow.py` 必须提供顶层异步入口：

```python
async def run(ctx):
    ...
```

默认限制为：压缩包不超过 50 MiB、解压后不超过 200 MiB、最多 500 个文件、压缩比不超过 100。包内禁止绝对路径、`..`、反斜杠路径、符号链接、加密条目以及 `.env`、`credentials.json`、`secrets.json`。Flow 源码和清单中不得包含账号、密码、Token 或环境专用地址。

同一范围内的 `rpaFlowId + version` 是不可覆盖的。已经上传 `1.0.0` 后，修改包内容必须升级为新版本，例如 `1.0.1` 或 `1.1.0`，不能重新上传覆盖原版本。

## 4. Postman 操作

仓库已提供集合：

```text
postman/AutoTask_RPA_Engine_v0.5.0.postman_collection.json
```

导入后配置集合变量：

| 变量 | 示例 | 说明 |
| --- | --- | --- |
| `engine_base_url` | `http://localhost:4610` | 改成实际 Engine 地址 |
| `actor_id` | `flow-registry-operator` | 操作人或调用系统标识 |
| `tenant_id` | 留空 | TENANT Flow 才填写 |
| `flow_scope` | `GLOBAL` | `GLOBAL` 或 `TENANT` |
| `workflow_code` | `supplier_example` | 必须存在于 Manifest 的 `supportedWorkflowCodes` 中 |
| `change_reason` | `首次发布 Flow 1.0.0` | 发布原因 |
| `allow_registry_writes` | `true` | 必须显式开启，写请求才会执行 |

然后依次执行：

1. `00 Health / Ready - 依赖就绪检查`。
2. `02 Registry Write / Upload Flow Package - 上传 ZIP`。
3. 在 `package` 文件控件中选择 ZIP；不要手工设置 multipart 的 `Content-Type` 或 boundary。
4. `02 Registry Write / Validate Flow Version - 重新校验包`。
5. `02 Registry Write / Publish Flow Version - 发布版本`。
6. `03 Binding Contract / Get Flow Version - 精确版本详情`。
7. `03 Binding Contract / Validate Binding - Task 精确绑定校验`。

集合会从上传响应自动保存：

- `flow_id`
- `flow_version`
- `flow_version_id`
- `package_checksum`

生命周期禁用、弃用和回滚不属于常规发布流程，不要开启 `allow_lifecycle_changes`。

## 5. 接口详细说明

以下示例使用：

```text
Engine 地址：http://localhost:4610
X-Actor-Id：flow-registry-operator
ZIP：D:\FlowPackages\rpa_flow_supplier_example-1.0.0.zip
```

请替换为实际值，不要把环境地址或凭据提交到仓库。

### 5.1 就绪检查

```http
GET /health/ready
```

PowerShell：

```powershell
$EngineBaseUrl = "http://localhost:4610"
Invoke-RestMethod "$EngineBaseUrl/health/ready"
```

成功标准：HTTP 200、顶层 `status=ready`，所有 `required=true` 的依赖状态均为 `healthy`。如果 Registry 所需的数据库或对象存储未启用/不可用，后续接口会返回 503。

### 5.2 上传 Flow ZIP

```http
POST /api/v1/flows/packages
Content-Type: multipart/form-data
X-Actor-Id: flow-registry-operator
```

表单字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `package` | file | 是 | Flow ZIP 文件 |
| `scope` | text | 否 | 默认 `GLOBAL`，也可为 `TENANT` |
| `description` | text | 否 | Flow 说明 |
| `labels` | text | 否 | JSON 字符串数组，例如 `["supplier","order"]` |

PowerShell（使用系统自带或单独安装的 `curl.exe`）：

```powershell
$EngineBaseUrl = "http://localhost:4610"
$ActorId = "flow-registry-operator"
$PackagePath = "D:\FlowPackages\rpa_flow_supplier_example-1.0.0.zip"

$Upload = curl.exe --fail-with-body --silent --show-error `
  -X POST "$EngineBaseUrl/api/v1/flows/packages" `
  -H "X-Actor-Id: $ActorId" `
  -F "package=@$PackagePath;type=application/zip" `
  -F "scope=GLOBAL" `
  -F "description=供应商门户示例 Flow" `
  -F 'labels=["supplier","order"]' | ConvertFrom-Json

$FlowId = $Upload.flow.rpaFlowId
$FlowVersion = $Upload.version.version
$FlowVersionId = $Upload.version.rpaFlowVersionId
$PackageChecksum = $Upload.version.packageChecksum

$Upload.validation.status
$FlowVersionId
$PackageChecksum
```

成功标准：

- HTTP 201。
- `flow.rpaFlowId` 与 Manifest 一致。
- `version.version` 与 Manifest 一致。
- `version.status` 为 `DRAFT`。
- `validation.status` 为 `PASSED`。
- 保存 `version.rpaFlowVersionId`；它是后续发布和 Task Binding 使用的精确 UUID。
- 保存 `version.packageChecksum`；API 返回值带 `sha256:` 前缀。

注意：上传成功并不等于已经发布。此时 Task 不能将该 DRAFT 版本作为有效运行版本使用。

### 5.3 显式重新校验

```http
POST /api/v1/flow-versions/{flowVersionId}/validate
X-Actor-Id: flow-registry-operator
```

该请求没有 Body：

```powershell
$Validation = Invoke-RestMethod `
  -Method Post `
  -Uri "$EngineBaseUrl/api/v1/flow-versions/$FlowVersionId/validate" `
  -Headers @{ "X-Actor-Id" = $ActorId }

$Validation.status
$Validation.errors
```

成功标准：HTTP 200、`flowVersionId` 等于上传返回的 UUID、`status=PASSED`、`errors=[]`。

### 5.4 发布 Flow 版本

```http
POST /api/v1/flow-versions/{flowVersionId}/publish
Content-Type: application/json
X-Actor-Id: flow-registry-operator
```

请求 Body：

```json
{
  "reason": "首次发布 Flow 1.0.0"
}
```

PowerShell：

```powershell
$PublishBody = @{
  reason = "首次发布 Flow $FlowVersion"
} | ConvertTo-Json

$Published = Invoke-RestMethod `
  -Method Post `
  -Uri "$EngineBaseUrl/api/v1/flow-versions/$FlowVersionId/publish" `
  -Headers @{ "X-Actor-Id" = $ActorId } `
  -ContentType "application/json" `
  -Body $PublishBody

$Published.status
$Published.rpaFlowVersionId
$Published.packageChecksum
```

成功标准：HTTP 200、`status=PUBLISHED`、`rpaFlowVersionId` 等于上传返回的 UUID，并且 `packageChecksum` 非空且与上传结果一致。

### 5.5 回读精确版本

```http
GET /api/v1/flow-versions/{flowVersionId}
X-Actor-Id: flow-registry-operator
```

```powershell
$Version = Invoke-RestMethod `
  -Method Get `
  -Uri "$EngineBaseUrl/api/v1/flow-versions/$FlowVersionId" `
  -Headers @{ "X-Actor-Id" = $ActorId }

$Version | Select-Object `
  rpaFlowVersionId, rpaFlowId, version, status, packageChecksum
```

交给 Task 同事的四个关键值是：

```text
rpaFlowId
version
rpaFlowVersionId
packageChecksum
```

不要仅凭“最新版本”建立 Binding，也不要把版本号字符串当成 `rpaFlowVersionId`。

### 5.6 验证 Task Binding 契约

推荐使用精确 UUID 校验：

```http
POST /api/v1/flow-versions/validate-binding
Content-Type: application/json
X-Actor-Id: flow-registry-operator
```

```json
{
  "rpaFlowVersionId": "<上传返回的 UUID>",
  "workflowCode": "supplier_example"
}
```

PowerShell：

```powershell
$BindingBody = @{
  rpaFlowVersionId = $FlowVersionId
  workflowCode = "supplier_example"
} | ConvertTo-Json

$BindingValidation = Invoke-RestMethod `
  -Method Post `
  -Uri "$EngineBaseUrl/api/v1/flow-versions/validate-binding" `
  -Headers @{ "X-Actor-Id" = $ActorId } `
  -ContentType "application/json" `
  -Body $BindingBody

$BindingValidation.valid
$BindingValidation.reasonCode
$BindingValidation.version | Select-Object `
  rpaFlowVersionId, rpaFlowId, version, status, packageChecksum
```

成功标准：

- HTTP 200。
- `valid=true`。
- `reasonCode=null`。
- `version.status=PUBLISHED`。
- `version.rpaFlowVersionId` 和 `version.packageChecksum` 与发布结果完全一致。
- `workflowCode` 存在于 Manifest 的 `supportedWorkflowCodes` 中。

接口在业务校验失败时也可能返回 HTTP 200，因此不能只看 HTTP 状态，必须检查 `valid` 和 `reasonCode`。

## 6. TENANT Flow 的差异

如果 Flow 只属于一个租户：

1. 上传时表单使用 `scope=TENANT`。
2. 上传请求携带 `X-Tenant-Id`。
3. 后续 validate、publish、详情查询和 validate-binding 均使用相同的 `X-Tenant-Id`。
4. Task 创建 Binding 时使用相同租户上下文。

示例 Header：

```powershell
$Headers = @{
  "X-Actor-Id" = "flow-registry-operator"
  "X-Tenant-Id" = "tenant-example"
}
```

租户 ID 不一致时，精确版本会按不可见/不存在处理，不能借此跨租户绑定。

## 7. 常见问题

| 现象 | 常见原因 | 处理方式 |
| --- | --- | --- |
| ready 返回 503 | 数据库或 MinIO 未启用/不可用，Bucket 不存在 | 检查 `.env`、网络、迁移和 Bucket |
| `FLOW_REGISTRY_UNAVAILABLE` | Registry 必需依赖未启用 | 启用数据库和 MinIO 后重启 Engine |
| `FLOW_VERSION_EXISTS` | 相同 `rpaFlowId + version` 已存在 | 升级 Manifest 版本，禁止覆盖旧版本 |
| 上传返回 400/422 | multipart 字段、labels JSON 或 Manifest 格式错误 | 不手工设置 multipart boundary，检查字段和清单 |
| 校验为 `FAILED` | 包结构、入口、敏感文件或静态策略不合规 | 查看响应的 `errors`，修包并提升版本后重新上传 |
| 发布失败 | 版本不可见、状态不允许或包重新校验失败 | 核对租户 Header、版本 UUID 和校验错误 |
| Binding 返回 `valid=false` | 版本未发布、Workflow Code 不支持或租户不一致 | 检查 `reasonCode` 和响应中的版本快照 |
| Task 仍运行旧 Flow | Binding 仍保存旧 UUID/checksum | 在 Task 中更新或重建精确 Binding |

业务错误响应格式：

```json
{
  "error": {
    "code": "FLOW_VERSION_EXISTS",
    "message": "The Flow version already exists and cannot be overwritten",
    "details": null
  }
}
```

Engine 接口直接返回 JSON，不使用 Task 的 `{code,data}` 响应信封。

## 8. 发布完成后的交接记录

每次发布至少记录以下非敏感信息：

```text
Engine 环境：
Flow 名称：
rpaFlowId：
版本：
rpaFlowVersionId：
packageChecksum：
scope：GLOBAL / TENANT
tenantId：仅 TENANT 填写
supportedWorkflowCodes：
发布人：
发布时间：
Binding 校验：valid=true / false
```

不要在交接记录中保存账号、密码、Token、数据库连接串或对象存储签名 URL。
