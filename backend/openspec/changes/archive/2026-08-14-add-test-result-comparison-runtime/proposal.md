## Why

自动化测试已经能够在远程环境执行并回收日志与报告，但目前后端还不能对原始环境和目标环境的测试结果做统一比较。迁移流程需要在构建验证和自动化测试完成后，由 agent 对两侧测试输出、日志和报告进行差异分析，给出可审计的比较结论。

## What Changes

- 新增测试结果比较运行时，作为自动化测试节点的内部后续步骤，在两侧自动化测试完成后自动创建 `TEST_LOG_COMPARE` 长任务。
- 新增测试比较结果持久化能力，保存比较运行摘要、结构化差异项、agent 输出制品和状态。
- 新增测试比较查询 API，支持查询项目比较列表、查询比较详情、查询差异项和下载原始 agent 输出；不新增用户手动创建比较任务入口。
- 比较任务 SHALL 通过 `TEST_LOG_COMPARE` 阶段绑定解析模型 profile；如果未配置或不可用，自动化测试仍成功保存结果，比较记录 SHALL 标记为不可用并给出前端提示。
- 自动化测试节点 SHALL 对用户表现为一次点击开始：测试执行完成后自动进入比较阶段，最终展示比较报告或比较不可用提示。
- 比较输入 SHALL 从已存在的 `test_runs`、任务日志文件和测试报告 artifact 聚合，避免重新执行远程测试。
- 比较运行 SHALL 使用项目级 SSE 推送任务状态变化，前端通过详情接口查询历史结论。

## Capabilities

### New Capabilities
- `test-result-comparison-runtime`: 测试结果比较任务、agent 输入聚合、比较结论和差异项管理。

### Modified Capabilities
- `backend-api-design`: 新增测试结果比较查询 API，并明确自动化测试完成后自动触发比较；未配置模型时比较报告不可用但测试结果正常展示。
- `backend-database-design`: 新增测试比较运行、差异项和 agent 输出制品的持久化要求。
- `task-runtime`: 新增长任务类型 `TEST_LOG_COMPARE` 的创建、执行、状态和 SSE 行为。
- `automated-test-runtime`: 明确自动化测试结果作为比较输入，并不因 AI 配置缺失而受阻。
- `model-profile-management`: 明确 `TEST_LOG_COMPARE` 阶段绑定是比较任务的硬前置条件。
- `backend-app-skeleton`: 测试结果比较实现需要覆盖正常流程、异常流程和 edge case。

## Impact

- 新增 Liquibase changelog、jOOQ 生成代码和测试比较领域代码。
- 新增测试比较 service、repository、worker handler、agent runtime、输入聚合器和查询 controller。
- 复用 `model_profiles`、`model_stage_assignments`、`CodexProcessRunner`、`task_logs`、`stored_artifacts` 和对象存储。
- 新增或更新独立 API E2E 模块，覆盖自动化测试完成后自动排队比较、未配置模型提示、权限隔离和结果查询。
