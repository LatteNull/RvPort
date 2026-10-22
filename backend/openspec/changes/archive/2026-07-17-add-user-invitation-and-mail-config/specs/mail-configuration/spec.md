## ADDED Requirements

### Requirement: 系统配置必须使用统一配置表
后端 SHALL 使用统一 `system_configs` 表保存邮箱、通知以及后续服务配置，并 SHALL 通过业务 API 控制不同 namespace 的可写字段。

#### Scenario: 保存邮箱配置
- **WHEN** 超级管理员保存邮箱服务器配置
- **THEN** 后端 SHALL 将配置写入 `system_configs` 的 `mail` namespace
- **AND** 后端 SHALL 对 host、port、username、password、from address、TLS/SSL 开关和超时时间执行字段级校验
- **AND** 后端 MUST NOT 允许客户端提交任意未声明的配置 key

#### Scenario: 保存敏感配置
- **WHEN** 配置项包含 SMTP 密码、token 或其他 secret
- **THEN** 后端 SHALL 在持久化前加密配置值
- **AND** API 响应 MUST NOT 返回明文 secret
- **AND** 审计日志 MUST NOT 记录明文 secret 或加密密文

#### Scenario: 读取配置
- **WHEN** 超级管理员读取邮箱配置
- **THEN** 后端 SHALL 返回非敏感配置和 secret 是否已配置的布尔摘要
- **AND** 后端 MUST NOT 返回 SMTP 密码明文

### Requirement: 邮件服务器配置必须可测试
后端 SHALL 提供邮箱服务器配置测试能力，允许超级管理员验证当前或临时配置能否发送测试邮件。

#### Scenario: 使用当前配置测试发送
- **WHEN** 超级管理员调用邮箱配置测试发送 API
- **THEN** 后端 SHALL 使用已保存的邮箱配置发送测试邮件
- **AND** 响应 SHALL 返回发送成功或失败摘要
- **AND** 失败摘要 MUST NOT 暴露 SMTP 密码或完整服务器敏感响应

#### Scenario: 邮箱配置缺失
- **WHEN** 邮箱配置缺少必要字段
- **THEN** 测试发送 API SHALL 返回配置不完整错误
- **AND** 后端 MUST NOT 尝试发送邮件

### Requirement: 邮件发送服务必须支持用户邀请和密码重置
邮件发送服务 SHALL 支持发送用户邀请邮件和忘记密码邮件，并 SHALL 使用配置中的前端 URL 生成用户可点击链接。

#### Scenario: 发送邀请邮件
- **WHEN** 管理员创建用户或重新发送邀请
- **THEN** 后端 SHALL 生成包含邀请 token 的 URL
- **AND** 邮件内容 SHALL 引导用户设置密码完成注册
- **AND** 邮件和日志 MUST NOT 包含密码哈希或 SMTP secret

#### Scenario: 发送忘记密码邮件
- **WHEN** 用户触发忘记密码流程且账号存在并可用
- **THEN** 后端 SHALL 生成包含密码重置 token 的 URL
- **AND** 邮件内容 SHALL 引导用户设置新密码
- **AND** 响应 MUST NOT 暴露账号是否存在

### Requirement: 任务完成邮件推送必须不影响任务终态
任务完成邮件推送 SHALL 在任务进入终态后发送通知，且邮件发送失败 MUST NOT 回滚或改变任务终态。

#### Scenario: 任务成功后发送通知
- **WHEN** 任务状态变为 `SUCCEEDED`
- **THEN** 后端 SHALL 在任务状态和任务事件已落库后尝试发送完成邮件
- **AND** 邮件 SHALL 包含任务摘要、项目摘要和前端查看 URL

#### Scenario: 任务失败后发送通知
- **WHEN** 任务状态变为 `FAILED`
- **THEN** 后端 SHALL 在通知开启时尝试发送失败邮件
- **AND** 邮件内容 MUST NOT 包含完整日志、明文凭据、token 或服务器真实敏感路径

#### Scenario: 邮件发送失败
- **WHEN** 任务完成邮件发送失败
- **THEN** 任务状态 SHALL 保持原终态
- **AND** 后端 SHALL 记录脱敏失败摘要
- **AND** 后端 MUST NOT 将任务重新标记为失败或重新投递任务
