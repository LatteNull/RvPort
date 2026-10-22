## ADDED Requirements

### Requirement: 登录页记住账号

登录页 SHALL 使用“账号 / 请输入账号”和“密码 / 请输入密码”作为账户凭据字段文案，并提供“记住账号”选项用于回填账号输入值，但不得将其实现为登录态持久化。

#### Scenario: 登录页展示标准字段文案

- **WHEN** 用户打开登录页
- **THEN** 账号字段 SHALL 展示“账号”标签和“请输入账号”占位提示
- **AND** 密码字段 SHALL 展示“密码”标签和“请输入密码”占位提示

#### Scenario: 用户选择记住账号并登录

- **WHEN** 用户勾选“记住账号”并成功登录
- **THEN** 应用 SHALL 在浏览器本地存储中仅保存该账号字符串
- **AND** 应用 SHALL NOT 保存密码、Cookie、token 或用户资料

#### Scenario: 登录页回填已保存账号

- **WHEN** 浏览器本地存储中存在已保存账号且用户打开登录页
- **THEN** 登录表单 SHALL 自动回填账号字段并选中“记住账号”

#### Scenario: 用户不再记住账号

- **WHEN** 用户取消“记住账号”或未勾选该选项成功登录
- **THEN** 应用 SHALL 删除已保存账号
- **AND** 该行为 SHALL NOT 修改服务端 Cookie Session 的有效期

### Requirement: 个人资料更新 API 消费

前端 SHALL 通过认证 API 模块消费既有 `PATCH /api/auth/profile`，并让开发 Mock 与正式响应形状保持一致。

#### Scenario: 前端更新显示名称

- **WHEN** 个人中心提交显示名称
- **THEN** 认证 API 模块 SHALL 向 `PATCH /api/auth/profile` 提交只包含 `displayName` 的请求
- **AND** 成功响应 SHALL 映射为 `User`

#### Scenario: 开发 Mock 更新显示名称

- **WHEN** Vite mock 模式收到 `PATCH /api/auth/profile`
- **THEN** Mock SHALL 更新当前会话用户的显示名称并返回正式 API 成功包络中的 `User`
