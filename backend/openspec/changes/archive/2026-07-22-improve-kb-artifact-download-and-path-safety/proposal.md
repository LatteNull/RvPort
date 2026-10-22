## Why

当前 KB 扫描 artifact 下载需要前端先查询 artifact 列表并拿到具体 `artifactId`，不利于直接按报告格式选择下载 HTML 或 JSON。与此同时，KB 扫描运行、artifact 下载、finding 代码上下文和 scanner evidence 中存在多处本地路径处理逻辑，需要统一成可复用的服务器路径安全边界，避免路径逃逸和服务器真实路径泄露。

## What Changes

- 新增 KB 扫描按格式下载 artifact 的 API，允许前端直接选择 `html`、`json` 或 `log`。
- 保留现有按 `artifactId` 下载接口，用于 artifact 列表中的精确下载。
- 新增通用服务器路径安全工具，用于根目录内路径解析、真实路径边界校验和路径文本脱敏。
- KB artifact 下载 SHALL 校验目标文件位于受控 KB 输出根目录下，越界、符号链接逃逸或不存在时返回安全错误。
- finding 代码上下文读取 SHALL 复用统一路径安全工具校验源码工作副本边界。
- scanner evidence、日志摘要和错误摘要中的服务器真实路径 SHALL 通过统一工具脱敏。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `backend-api-design`: 增加 KB 扫描按格式下载 artifact 的 API 要求，并明确下载响应和错误响应不得泄露服务器真实路径。
- `kb-scan-runtime`: 增加服务器路径安全工具、artifact 下载边界校验、finding 代码上下文边界校验和 scanner 输出脱敏要求。

## Impact

- 影响 `cn.rvport.backend.kb` 下 KB 扫描 artifact 下载和 finding 代码上下文读取逻辑。
- 影响 scanner runtime 中 evidence、日志摘要和错误摘要的路径脱敏逻辑。
- 新增公共路径安全工具及其单元测试。
- 新增或更新 KB scan service/controller 单元测试和 E2E 覆盖。
- 不涉及数据库 schema 变更。
