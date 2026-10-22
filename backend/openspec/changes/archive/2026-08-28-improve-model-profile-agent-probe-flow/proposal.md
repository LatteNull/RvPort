## Why

当前模型 profile 测试接口把模型连通性和 agent runtime 兼容性混在一次同步请求里执行，前端等待较久时容易触发网关超时并跳转 500。随着后端支持 Codex、DeepSeek Harness、OpenCode 以及后续更多 agent，单一“最近一次测试结果”也无法表达同一个模型对多个 agent 的兼容性矩阵。

## What Changes

- 新增独立的模型连通性测试 API，只验证模型 profile 的 provider/base URL/API key/model/wire API 是否可用，不启动 agent runtime。
- 新增批量 agent 兼容性测试 API，前端提交 `agentRuntimeIds` 列表后，后端为所选 agent runtime 创建一次可查询的测试 run。
- agent 兼容性测试结果按 profile + agent runtime 分项持久化，单个 agent 失败不影响其他 agent 的测试结果记录。
- 模型 profile 列表和详情返回连通性摘要、agent 兼容性摘要，便于前端展示用户选择结果。
- 保留旧 `POST /api/admin/model-profiles/{profileId}:test` 的兼容边界，但新前端 SHALL 使用新的连通性和批量 agent 测试接口。
- E2E 增加模型连通性、指定多个 agent runtime 测试、局部失败、无权限和脱敏校验。

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `model-profile-management`: 拆分模型连通性测试和 agent runtime 兼容性测试，并支持多 agent runtime 结果矩阵。
- `backend-api-design`: 增加模型连通性测试、批量 agent 测试 run、结果查询和列表摘要字段。
- `backend-database-design`: 增加连通性结果和 profile-agent probe 结果的持久化设计，避免只保存最近一次单 agent 结果。
- `agent-runtime-selection`: 明确 agent runtime 兼容性 probe 按用户选择的 runtime 列表执行。
- `api-e2e-test-suite`: 增加模型连通性和多 agent runtime probe 的端到端覆盖。

## Impact

- 影响后端模型 profile 管理 API、agent runtime probe 服务、数据库迁移、jOOQ 生成代码、管理员权限校验和 E2E 脚本。
- 需要避免返回 API key、授权头、完整 prompt、完整 agent 命令和服务器真实敏感路径。
- 前端后续需要改为先调用连通性测试，再提交用户选中的 `agentRuntimeIds` 做 agent 兼容性测试，并通过 run 查询接口展示结果。
