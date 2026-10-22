## Why

构建验证已经具备 API、运行记录和 worker 主干，API 文档和主 spec 也声明了任务级 `environmentVariables`，但当前后端实现缺少输入校验、worker 注入和脱敏闭环。需要补齐该能力，使构建验证与自动化测试在运行参数、安全边界和 E2E 验证上保持一致。

## What Changes

- 为构建任务创建请求补齐可选 `environmentVariables` 输入。
- 在构建任务创建时校验环境变量名和值长度，并在任务输入快照、API 响应、任务事件和审计摘要中只保存脱敏摘要。
- 在远程构建命令或脚本执行时注入任务级环境变量，变量只作用于本次构建，不写入环境配置、凭据表或系统配置。
- 为构建环境变量补充正常流程、异常流程和 edge case 测试，并补充独立 API E2E 覆盖。
- 不在本 change 中实现日志比较、结构化测试报告解析或新的配置中心能力。

## Capabilities

### New Capabilities

### Modified Capabilities
- `backend-api-design`: 补齐构建任务 environmentVariables 的 API 行为、输入边界和脱敏要求。
- `task-runtime`: 补齐 BUILD 任务在 worker 执行阶段注入任务级环境变量的运行时要求。
- `backend-app-skeleton`: 补齐构建环境变量相关测试覆盖要求。

## Impact

- 影响构建验证 API、构建任务 service/repository、构建 worker handler、远程 SSH 执行封装和任务输入快照。
- 影响任务事件、日志摘要、审计摘要中的敏感信息脱敏。
- 影响独立 API E2E 脚本和构建模块单元测试。
