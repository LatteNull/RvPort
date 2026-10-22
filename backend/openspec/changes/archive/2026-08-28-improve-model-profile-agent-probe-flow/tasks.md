## 1. 数据库和生成代码

- [x] 1.1 增加 Liquibase 变更集，保存模型连通性摘要、agent probe run 和 profile-agent runtime 分项结果。
- [x] 1.2 为 profile 活跃 run 查询、profile-agent 最新结果查询增加必要索引。
- [x] 1.3 运行 Liquibase 并重新生成 jOOQ 代码。

## 2. 后端服务

- [x] 2.1 拆分模型连通性测试服务，确保不启动任何 agent runtime。
- [x] 2.2 实现多 agent runtime probe run 创建、后台执行、聚合状态更新和单 runtime 分项结果保存。
- [x] 2.3 在模型 profile 列表和详情响应中增加连通性摘要、agent 兼容性摘要和 `activeAgentProbeRun`。
- [x] 2.4 保留旧 `:test` 接口兼容行为，并在实现中避免泄漏 secret、完整命令和真实路径。

## 3. API

- [x] 3.1 增加 `POST /api/admin/model-profiles/{profileId}:test-connectivity`。
- [x] 3.2 增加 `POST /api/admin/model-profiles/{profileId}:test-agents`。
- [x] 3.3 增加 `GET /api/admin/model-profile-agent-test-runs/{runId}`。
- [x] 3.4 增加 `GET /api/admin/model-profiles/{profileId}/agent-probe-results`。
- [x] 3.5 补齐超级管理员权限校验、异常输入校验和响应脱敏。

## 4. 测试

- [x] 4.1 增加单元测试覆盖连通性测试正常流程、配置缺失、临时覆盖和脱敏。
- [x] 4.2 增加单元测试覆盖多 agent probe run 正常流程、局部失败、空列表、重复 runtime 和禁用 runtime。
- [x] 4.3 增加 API E2E 模块，覆盖连通性测试、多 agent probe、active run 恢复、旧接口兼容和普通用户越权。
- [x] 4.4 运行后端单元测试和相关 E2E，记录实际结果。

## 5. 文档和校验

- [x] 5.1 更新后端 API 文档和 README 中模型测试接口说明。
- [x] 5.2 运行 `openspec validate improve-model-profile-agent-probe-flow --strict`。
