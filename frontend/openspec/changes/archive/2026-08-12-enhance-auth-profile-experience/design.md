## Context

当前登录页直接提交账号和密码，认证状态通过 Cookie Session 恢复；Zustand 的持久化只保存当前用户摘要，不能也不应作为登录凭证。Header 已展示用户名称和下拉菜单，但菜单仅提供账户安全与退出登录。后端已提供 `GET /api/auth/me`、`PATCH /api/auth/profile` 和 `POST /api/auth/change-password`，其中用户只能自行更新显示名称。

## Goals / Non-Goals

**Goals:**

- 减少重复输入账号的成本，同时不扩大认证凭证在浏览器侧的存储范围。
- 提供主布局内的个人中心，集中展示当前账户资料并支持编辑显示名称。
- 在个人中心内提供常规改密码操作，复用既有密码策略、API 和用户状态更新行为。
- 保留强制改密码路径及其路由 guard，确保必须改密码的用户无法进入业务页面。

**Non-Goals:**

- 不保存密码、Cookie、token、完整用户资料或任何可用于恢复登录态的凭证。
- 不实现“记住登录态”、会话延期、忘记密码、邮件重置、邀请激活或用户管理。
- 不允许用户自行修改账号、邮箱、角色、账户状态或强制改密码标记。
- 不修改后端 API、Cookie Session 时长或鉴权模型。

## Decisions

### “记住账号”仅保存账号名

登录表单使用一个明确命名的本地存储键保存账号字符串；勾选时写入，未勾选登录或取消勾选时删除。登录页初始化时只回填该账号并同步勾选状态。

备选方案是使用“记住我”保存完整登录信息或延长会话。当前后端没有逐次登录的持久会话契约，且前端不得保存密码、Cookie 或 token，因此该方案不成立。

### 个人中心作为受保护 Settings 子路由

`/settings/profile` 位于 `MainLayout` 的受保护子路由下，并与既有安全设置同属 `pages/settings/`，由 Header 用户菜单进入。页面直接消费认证 store 中的当前用户摘要，显示名称提交成功后调用 `setUser` 同步 Header 与页面。

备选方案是使用独立的 `/profile` 顶层目录。资料和账户安全实际属于设置域，使用 `settings/profile` 能与现有密码设置保持清晰的一致性，同时仍保留主布局体验。

### 常规改密码使用个人中心内的 Modal

个人中心的账户安全区域通过 `BaseModal` 打开密码表单，复用已有密码规则并在成功后关闭 Modal、提示成功和更新认证 store。强制改密码页继续保留独立路由与阻断逻辑。

备选方案是让所有用户跳转到 `/settings/security/password`。这会使普通设置操作离开主布局，并把强制安全流程与常规设置混为一个体验。

### 前端 API 与 Mock 同步补齐资料更新契约

认证 API 模块增加显式的 `updateProfile` 方法，Vite mock 模拟仅更新显示名称并返回完整 `User`。所有页面通过该 API 边界调用，不直接请求 Axios。

## Risks / Trade-offs

- [Risk] 用户将“记住账号”误解为保持登录。→ Mitigation: 使用准确文案，不使用“记住我”，且不保存密码。
- [Risk] 认证 store 持久化的用户摘要过期。→ Mitigation: 继续由既有路由 guard 调用 `/api/auth/me` 验证 Cookie Session。
- [Risk] 常规与强制改密码页面出现规则漂移。→ Mitigation: 提取或复用同一套密码字段校验规则，并覆盖两种提交场景的测试。
- [Risk] 后端拒绝不可写资料字段。→ Mitigation: 个人中心只提交 `displayName`，账号、邮箱和权限信息均为只读。
