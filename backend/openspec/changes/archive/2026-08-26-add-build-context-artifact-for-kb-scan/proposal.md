## Why

当前 x86 构建验证已经能够在远端构建目录中观测 `compile_commands.json`，但平台只把它摘要到构建日志中，没有作为可复用的构建上下文制品保存。KB Scanner 本身支持 `--compile-commands`，因此应让后端在 KB 扫描时自动复用最新成功 x86 构建产生的 compile database，减少前端手动配置，并提升源码扫描上下文准确度。

## What Changes

- 构建验证成功后，后端在远端工作目录中发现可用 `compile_commands.json` 时，将其安全下载、脱敏校验并保存为构建上下文 artifact。
- 构建运行记录保存 compile database 的 artifact 引用、sha256、大小、来源环境、来源构建运行和可用状态。
- KB 扫描创建或执行时，根据 `projectId + sourceRevisionId` 自动寻找最新成功的 x86/source-only 构建上下文；存在可用 compile database 时自动传入 KB Scanner。
- KB 扫描摘要、artifact 摘要和日志中记录本次是否使用 compile database，以及来源 `buildRunId` / `artifactId`，但不暴露服务器真实路径或远端路径。
- 如果没有可用 compile database、下载失败或格式不可用，KB 扫描应降级为现有源码上下文扫描并记录 warning，不阻断扫描。
- 补充 API/E2E/单元测试，覆盖正常流程、异常流程和 edge case。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `build-validation-runtime`: 构建验证需要保存可复用 compile database 构建上下文制品。
- `kb-scan-runtime`: KB 扫描需要自动复用最新成功构建上下文中的 compile database，并支持降级。
- `object-storage-artifacts`: 对象存储 artifact owner/type 需要覆盖构建上下文制品。
- `backend-database-design`: 数据库需要保存构建上下文 artifact 引用和查询索引。
- `backend-api-design`: KB 扫描和构建详情响应需要返回安全的构建上下文摘要。
- `api-e2e-test-suite`: E2E 需要覆盖构建生成 compile database 后 KB 扫描自动复用的端到端链路。

## Impact

- 影响构建验证 worker、KB 扫描 worker、artifact 存储、构建运行查询、KB 扫描响应摘要和 E2E。
- 需要新增 Liquibase migration，并重新生成 jOOQ 代码。
- 不需要前端上传 `compile_commands.json`；前端只消费后端返回的摘要字段。
- 不改变 KB Scanner CLI 能力，只在后端调用时按需传递已有 `--compile-commands` 参数。
