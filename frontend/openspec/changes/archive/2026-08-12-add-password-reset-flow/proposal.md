## Why

登录页缺少忘记密码入口，用户无法在忘记本地密码后自行恢复账号访问。后端已提供邮件重置接口和一次性 token 链接，需要补齐对应的前端流程。

## What Changes

- 在登录页提供“忘记密码”入口。
- 新增密码重置申请页，支持以账号或邮箱请求重置邮件，并使用统一成功反馈避免账号枚举。
- 新增密码重置确认页，从邮件链接读取 token、设置并确认新密码，成功后返回登录页。
- 补充认证 API 模块、Vite mock、路由和单元测试。

## Capabilities

### New Capabilities

- `password-reset-flow`: 未登录用户通过邮件完成密码重置的前端页面、路由和交互。

### Modified Capabilities

- `incremental-api-integration`: 接入密码重置申请和确认 API，并保持类型、mock 与正式契约一致。

## Impact

- 影响 `src/pages/auth/` 下的认证页面、`src/router/routes.ts`、`src/api/auth/` 和 `mock/auth.ts`。
- 使用既有 `POST /api/auth/password-resets/request` 与 `POST /api/auth/password-resets/confirm` 接口，不新增依赖。
