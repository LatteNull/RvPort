## ADDED Requirements

### Requirement: 测试辅助 API 必须支持确定性触发 Worker 清理
测试构建 SHALL 提供手工触发一次失效 Worker 清理的能力，以便 E2E 无需等待真实调度周期即可验证生产清理服务。

#### Scenario: 触发一次 Worker 清理
- **WHEN** E2E 调用 Worker 清理测试辅助接口
- **THEN** 后端 SHALL 调用与生产调度器相同的清理服务
- **AND** SHALL 返回本轮标记离线、收敛 runtime handle、终止任务和删除 Worker 的数量

#### Scenario: 测试辅助接口不进入生产包
- **WHEN** 后端使用生产构建方式生成 JAR
- **THEN** 生产 JAR MUST NOT 包含 Worker 清理测试辅助 Controller 或接口映射
- **AND** 生产环境 MUST NOT 能通过 HTTP 手工触发该测试接口
