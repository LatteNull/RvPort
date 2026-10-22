## Why

构建验证完成后，RvPort 需要进入自动化测试节点，在远程环境中运行用户提供的测试脚本或命令，并回收 stdout/stderr 日志、退出码和测试生成的文字报告。现有文档只定义了测试摘要字段和占位 API，缺少实际远程测试输出、报告产物与日志回收能力。

## What Changes

- 新增自动化测试运行时，允许用户基于源码版本、执行环境和可选构建结果创建测试任务。
- 支持在远程环境运行用户提供的测试脚本或命令，并保存退出码、状态、stdout/stderr 日志引用、测试报告产物引用和安全摘要。
- 支持用户指定多个报告回收目标，每个目标明确为报告文件路径或报告输出目录；即使 stdout 内容很少，也可以回收测试程序生成的文字报告。
- 构建任务和测试任务都支持前端传入环境变量，并在远程执行时注入这些变量。
- 使用既有任务运行时、SSH runtime、任务日志、对象存储和项目级 SSE 推送测试任务状态。
- 保持 MVP 边界：不解析 JUnit、CTest、pytest 等结构化测试报告，不创建用例级测试表，不提供失败用例重跑，不实现日志比较或测试结果对比。

## Capabilities

### New Capabilities

- `automated-test-runtime`: 自动化测试节点的任务创建、远程执行、测试输出、报告产物和日志回收能力。

### Modified Capabilities

- `backend-api-design`: 补充构建/测试 API 的环境变量输入，以及自动化测试 API 的远程执行参数、输出日志摘要、报告产物回收参数和权限边界。
- `backend-database-design`: 补充 `test_runs` 的测试输出、报告产物引用和日志回收持久化约束。
- `task-runtime`: 补充 `AUTOMATED_TEST` 任务类型、构建/测试环境变量输入传递、状态事件和取消行为。
- `backend-app-skeleton`: 补充自动化测试运行时的测试覆盖要求。

## Impact

- 后端 API：新增或补齐 `POST /api/projects/{projectId}/tests`、测试列表、测试详情和取消接口。
- 后端任务：新增 `AUTOMATED_TEST` handler，复用任务队列、日志事件、取消机制和 SSE。
- 数据库：复用/扩展 `test_runs`，保存远程测试执行摘要、日志引用和报告产物摘要。
- 外部依赖：复用现有 SSH runtime、SCP/SFTP 文件回收能力、任务日志和对象存储；不接入 Codex provider 或任何 LLM 日志比较能力。
- 测试：需要覆盖正常流程、异常流程和 edge case，并补充独立 E2E 模块用例。
