## ADDED Requirements

### Requirement: 生产 API 设计不得包含测试辅助接口
后端生产 API 设计 SHALL 明确 `/api/test-support/**` 和旧 `/api/dev/session` 不属于生产 API。

#### Scenario: 查看生产 API 文档
- **WHEN** 开发者查看 `backend/docs/API_DESIGN.md`
- **THEN** 文档 SHALL 不把 `/api/test-support/**` 作为前端可用生产接口
- **AND** 文档 SHALL 不把 `/api/dev/session` 作为可用接口

#### Scenario: 需要测试辅助接口说明
- **WHEN** 文档需要说明 E2E 或开发测试辅助能力
- **THEN** 该说明 SHALL 放入 E2E 或开发测试文档
- **AND** 说明 SHALL 明确该能力不进入默认生产构建产物

### Requirement: Test-support API 不改变生产认证和权限模型
测试辅助 API SHALL NOT 改变生产认证 API、项目访问守卫或超级管理员权限模型。

#### Scenario: 生产认证流程
- **WHEN** 后端以默认生产构建运行
- **THEN** 浏览器登录态 SHALL 继续使用服务端 Session 和 Cookie
- **AND** 用户 SHALL 通过真实认证 API 建立登录态

#### Scenario: 项目权限校验
- **WHEN** 后端以默认生产构建运行
- **THEN** 项目级 API 和 SSE API SHALL 继续执行项目访问权限校验
- **AND** 不存在 test-support API 绕过权限校验
