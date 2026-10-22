## ADDED Requirements

### Requirement: API E2E 必须覆盖用户邀请和邮件配置
API E2E 测试套件 SHALL 覆盖用户邀请注册、忘记密码、邮箱配置和任务完成邮件推送的端到端行为。

#### Scenario: 覆盖管理员邀请创建用户
- **WHEN** E2E 使用超级管理员创建用户
- **THEN** 测试 SHALL 验证创建请求不提交 `initialPassword`
- **AND** 测试 SHALL 验证数据库创建用户和邀请 token hash
- **AND** 测试 SHALL 验证邮件发送请求被触发或测试邮件收件箱收到邀请邮件

#### Scenario: 覆盖接受邀请
- **WHEN** E2E 使用邀请 token 调用邀请接受 API
- **THEN** 测试 SHALL 验证用户可以设置密码并登录
- **AND** 测试 SHALL 验证 token 被消费后不能再次使用

#### Scenario: 覆盖管理员直接重置密码
- **WHEN** E2E 使用超级管理员调用重置密码 API
- **THEN** 测试 SHALL 验证管理员可直接设置新密码
- **AND** 测试 SHALL 验证 `mustChangePassword` 可按请求设置
- **AND** 测试 SHALL 验证该流程不发送重置密码邮件

#### Scenario: 覆盖忘记密码流程
- **WHEN** E2E 调用忘记密码 request 和 confirm API
- **THEN** 测试 SHALL 验证 request 响应不暴露账号是否存在
- **AND** 测试 SHALL 验证有效 token 可设置新密码
- **AND** 测试 SHALL 验证过期、已消费和错误类型 token 不能修改密码

#### Scenario: 覆盖邮箱配置
- **WHEN** E2E 使用超级管理员保存邮箱服务器配置
- **THEN** 测试 SHALL 验证配置写入 `system_configs`
- **AND** 测试 SHALL 验证 secret 配置不会明文返回
- **AND** 测试 SHALL 验证测试发送 API 返回可审计结果

#### Scenario: 覆盖任务完成邮件推送
- **WHEN** E2E 创建任务并使任务进入终态
- **THEN** 测试 SHALL 验证邮件通知开启时触发任务完成邮件
- **AND** 测试 SHALL 验证邮件内容不包含明文凭据、完整日志或服务器真实敏感路径

#### Scenario: 覆盖异常和 edge case
- **WHEN** E2E 验证用户邀请和邮件配置边界
- **THEN** 测试 SHALL 覆盖重复 username、重复 email、缺失 email、无效邮箱格式、无权限访问管理员邮件配置、SMTP 配置不完整、邮件发送失败、token 过期、token 重放和 token 类型不匹配
