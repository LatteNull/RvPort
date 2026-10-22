## ADDED Requirements

### Requirement: 用户 action token 历史数据必须按保留期清理
数据库中的 `user_action_tokens` 历史记录 SHALL 按 30 天保留期清理，以控制历史 token 数据增长。

#### Scenario: 清理已消费历史 token
- **WHEN** 后台清理任务执行
- **THEN** 数据库 SHALL 删除 `consumed_at` 早于当前时间 30 天前的 `user_action_tokens` 记录

#### Scenario: 清理已过期历史 token
- **WHEN** 后台清理任务执行
- **THEN** 数据库 SHALL 删除 `expires_at` 早于当前时间 30 天前的 `user_action_tokens` 记录

#### Scenario: 保留仍在保留期内的 token
- **WHEN** 后台清理任务执行
- **THEN** 数据库 MUST NOT 删除 `consumed_at` 或 `expires_at` 未早于当前时间 30 天前的 token

#### Scenario: 保留仍有效 token
- **WHEN** 后台清理任务执行
- **THEN** 数据库 MUST NOT 删除未消费且未过期的 token
