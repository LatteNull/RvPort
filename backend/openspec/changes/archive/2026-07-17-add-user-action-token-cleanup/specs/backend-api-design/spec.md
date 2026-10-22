## ADDED Requirements

### Requirement: 用户 action token 清理任务不得影响认证流程正确性
后端 SHALL 提供用户 action token 历史数据清理任务，但 token 是否有效 MUST 始终由接口实时校验决定。

#### Scenario: 接口实时校验 token 有效性
- **WHEN** 用户接受邀请或确认密码重置
- **THEN** 后端 SHALL 实时校验 token hash、token type、`consumed_at is null`、`expires_at > now()` 和用户状态
- **AND** 后端 MUST NOT 依赖后台清理任务判断 token 是否有效

#### Scenario: 清理任务延迟或失败
- **WHEN** 用户 action token 清理任务未执行、延迟执行或执行失败
- **THEN** 已过期 token 仍然 MUST 被邀请接受和密码重置确认接口拒绝
- **AND** 已消费 token 仍然 MUST 被邀请接受和密码重置确认接口拒绝

#### Scenario: 清理任务执行成功
- **WHEN** 用户 action token 清理任务删除历史 token
- **THEN** 后端 SHALL 只删除 30 天前已经过期或已经消费的 token
- **AND** 后端 MUST NOT 删除仍可能被用户使用的未过期未消费 token
