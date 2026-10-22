## ADDED Requirements

### Requirement: 个人中心访问与账户资料展示

应用 SHALL 为已完成强制改密码要求的登录用户提供位于主布局内的 `/settings/profile` 个人中心，并展示当前认证用户的账户资料。

#### Scenario: 用户从账户菜单进入个人中心

- **WHEN** 已登录用户在 Header 账户菜单选择个人中心
- **THEN** 应用 SHALL 导航至 `/settings/profile`
- **AND** 页面 SHALL 保持主布局和当前有效登录会话

#### Scenario: 个人中心展示只读账户资料

- **WHEN** 用户打开 `/settings/profile`
- **THEN** 页面 SHALL 展示账号、邮箱、账户状态、创建时间和最近登录时间
- **AND** 页面 SHALL NOT 提供修改账号、邮箱、权限、账户状态或 `mustChangePassword` 的控件

### Requirement: 用户编辑显示名称

个人中心 SHALL 允许当前用户编辑显示名称，并通过既有个人资料接口同步认证状态。

#### Scenario: 用户保存显示名称

- **WHEN** 用户提交有效的显示名称
- **THEN** 应用 SHALL 调用 `PATCH /api/auth/profile` 且请求体只包含 `displayName`
- **AND** 成功后 SHALL 用响应中的 `User` 更新认证 store、个人中心和 Header 显示名称

#### Scenario: 显示名称更新失败

- **WHEN** 显示名称更新请求失败
- **THEN** 应用 SHALL 保留最近一次已保存的用户资料
- **AND** SHALL 展示可理解的失败反馈

### Requirement: 个人中心常规改密码

个人中心 SHALL 为不处于强制改密码状态的用户提供常规改密码入口，并复用既有密码安全规则与接口。

#### Scenario: 用户在个人中心修改密码

- **WHEN** 用户在个人中心打开改密码操作并提交有效的当前密码、新密码和确认密码
- **THEN** 应用 SHALL 调用 `POST /api/auth/change-password`
- **AND** 成功后 SHALL 更新认证 store、关闭改密码界面并展示成功反馈

#### Scenario: 常规改密码的表单校验

- **WHEN** 用户在个人中心提交空白密码、与账号相同的新密码、与当前密码相同的新密码或不一致的确认密码
- **THEN** 应用 SHALL 展示相应表单校验错误
- **AND** SHALL NOT 发送改密码请求

#### Scenario: 强制改密码流程保持独立

- **WHEN** 当前用户的 `mustChangePassword` 为 `true`
- **THEN** 既有路由 guard SHALL 继续将用户导向 `/settings/security/password`
- **AND** 用户 SHALL NOT 通过 `/settings/profile` 绕过强制改密码要求
