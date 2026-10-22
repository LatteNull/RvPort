## ADDED Requirements

### Requirement: API E2E 必须覆盖用户 action token 清理边界
API E2E 测试套件 SHALL 覆盖用户 action token 清理任务的关键边界，确保清理不会影响有效邀请和忘记密码流程。

#### Scenario: 覆盖清理不影响有效邀请
- **WHEN** E2E 创建未过期且未消费的邀请 token 后触发或等待清理任务
- **THEN** 测试 SHALL 验证该邀请 token 仍可用于接受邀请

#### Scenario: 覆盖过期或已消费历史 token 清理
- **WHEN** E2E 或维护脚本准备 30 天前已过期或已消费 token 并执行清理
- **THEN** 测试 SHALL 验证这些 token 被删除
- **AND** 测试 SHALL 验证 30 天内的已过期或已消费 token 被保留

#### Scenario: 覆盖清理任务失败不影响接口校验
- **WHEN** 清理任务未执行或失败
- **THEN** E2E SHALL 验证过期 token 和已消费 token 仍被 API 拒绝
