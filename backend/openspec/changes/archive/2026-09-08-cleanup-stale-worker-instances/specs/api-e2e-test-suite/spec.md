## ADDED Requirements

### Requirement: Worker E2E 必须覆盖失效实例收敛和清理
API E2E 测试套件 SHALL 在独立 Worker 模块中覆盖失效 Worker 清理的正常流程、异常流程和 edge case，并 SHALL 在完成后清理测试数据。

#### Scenario: 正常收敛并删除失效 Worker
- **WHEN** E2E 创建超过失联确认时间的 Worker、`RUNNING` 任务和活动 runtime handle 并触发清理
- **THEN** runtime handle SHALL 变为 `WORKER_LOST`
- **AND** 任务 SHALL 以 `WORKER_LOST` 错误码进入 `FAILED`
- **AND** 对应失败事件 SHALL 可查询
- **AND** 超过保留期且没有非终态句柄的 Worker SHALL 被删除

#### Scenario: 异常和权限边界
- **WHEN** 未授权调用者尝试访问 Worker 清理测试辅助接口，或生产构建检查接口映射
- **THEN** 后端 SHALL 拒绝未授权访问
- **AND** 生产构建 SHALL 不存在该接口
- **AND** 响应和日志 MUST NOT 泄露任务输入、凭据或服务器真实路径

#### Scenario: 心跳恢复和重复触发边界
- **WHEN** E2E 创建处于短时离线窗口、清理期间恢复心跳、任务已终态或被重复清理的 Worker 数据
- **THEN** 短时离线或已恢复 Worker MUST NOT 被收敛或删除
- **AND** 已终态任务 MUST NOT 被覆盖
- **AND** 重复清理 MUST NOT 产生重复失败事件
- **AND** 测试结束后 SHALL 删除本次创建的 Worker、任务、事件和 runtime handle fixture
