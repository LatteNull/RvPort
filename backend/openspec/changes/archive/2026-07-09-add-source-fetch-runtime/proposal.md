## Why

当前 Git 同步 API 只创建 `SOURCE_GIT_SYNC` 任务并投递队列，worker 还没有真实从 Git 仓库获取源码。后续检测、构建、报告都依赖后端本机可访问的源码目录，因此需要先把源码获取运行时闭环。

## What Changes

- 实现 `SOURCE_GIT_SYNC` worker handler，在后端本机执行 Git clone/fetch/checkout。
- 将源码工作副本保存到后端本机受配置控制的 runtime source 目录。
- Git 同步成功后创建新的 `source_revisions`，更新 `source_imports` 状态，并支持按请求启用新版本。
- Git 同步失败时保留失败状态、`tool_runs` 执行记录、任务日志和安全错误摘要。
- 支持 Git token/password 凭据运行时解密，避免明文凭据进入任务输入、队列消息、日志、审计和 API 响应。
- 为 Git 同步运行时补充正常流程、异常流程和 edge case 测试。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `project-source-environment`: 补齐 Git 同步任务的本机源码获取运行时、执行记录、状态更新和脱敏要求。

## Impact

- 影响 `source` 模块：`SourceService`、`SourceRepository`、Git 同步请求和 source import/revision 状态更新。
- 影响 worker 模块：新增 `SOURCE_GIT_SYNC` handler 和 Git 执行适配层。
- 影响 credential 模块：新增 Git 凭据运行时读取能力。
- 影响配置：增加后端本机源码 runtime 目录配置，默认位于 runtime 管理目录下。
- 影响测试：补充 source runtime、credential runtime、worker handler 和 API/E2E 脚本覆盖。
