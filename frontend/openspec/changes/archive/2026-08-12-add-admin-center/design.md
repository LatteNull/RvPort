## Context

超级管理员的用户和邮件配置 API 已由后端实现。管理能力必须与普通用户的个人设置隔离，同时保留未来在 monorepo 中拆为独立管理应用的边界。

## Goals / Non-Goals

**Goals:**

- 以 `/admin/*`、`AdminLayout` 和统一超级管理员 guard 提供独立管理模块。
- 完整接入用户管理和 SMTP 邮件配置的现有 API。
- 仅向超级管理员显示入口，非管理员访问统一进入 `/403`。

**Non-Goals:**

- 不拆分独立前端应用，不实现审计、租户、系统监控或角色权限系统。
- 不在前端保存 SMTP 密码或邀请、重置 token。

## Decisions

### 独立管理路由与布局

使用 `/admin/users` 作为默认入口、`/admin/mail` 作为配置页；`AdminLayout` 只负责标题、返回业务端和二级导航。`requireAdmin` 在路由 loader 层读取现有会话并校验 `isSuperAdmin`，而不是由页面自行判断。

### 页面按能力分组

用户列表使用既有 `BaseTable`、查询参数和 Ant Design Modal 表单；邮件配置采用受控表单与 TanStack Query 查询/mutation。API 模块和 mock 独立为 `admin` 领域。

### 高风险操作

禁用、管理员重置密码和重发邀请均要求明确确认；密码仅本次提交，不进入状态存储或页面回显。

## Risks / Trade-offs

- [管理员误操作用户状态] → 对禁用和密码重置增加确认，并在成功后刷新列表。
- [SMTP 密码泄露] → 响应只消费 `passwordConfigured`，输入框不回填密码。
- [未来拆分应用] → 通过独立页面、布局和 API 模块保持边界，避免 admin 页面依赖业务页面。
