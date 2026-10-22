## Why

后端已提供超级管理员的用户与邮箱配置能力，但前端没有独立入口、权限边界或操作界面，管理员无法完成平台账户和邮件基础设施管理。

## What Changes

- 新增独立 `/admin/*` 管理中心路由、布局和超级管理员守卫。
- 新增用户管理：查询、筛选、新增、编辑、启用/禁用、重置密码和重发邀请。
- 新增邮件服务器配置：读取、保存和测试发送。
- 在账户菜单中仅向超级管理员展示“管理中心”入口。
- 补充 API 模块、Vite mock 和测试。

## Capabilities

### New Capabilities

- `admin-center`: 仅超级管理员可访问的用户管理与邮件配置中心。

### Modified Capabilities

- `incremental-api-integration`: 接入管理员用户和邮箱配置 API。

## Impact

- 影响路由、Header 用户菜单、认证守卫、`src/pages/admin/`、管理员 API 与 mock。
- 使用后端既有 `/api/admin/users` 和 `/api/admin/configs/mail` 接口；不新增依赖。
