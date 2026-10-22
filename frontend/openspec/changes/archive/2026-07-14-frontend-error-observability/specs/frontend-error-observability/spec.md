## ADDED Requirements

### Requirement: 前端异常安全采集

当前端配置有效的 Sentry DSN 时，系统 SHALL 通过统一可观测性边界初始化 `@sentry/react` 并采集未处理异常和 React 渲染错误。React 19 root SHALL 使用 `onUncaughtError` 和 `onRecoverableError` 接入 `Sentry.reactErrorHandler()`；已使用 `Sentry.ErrorBoundary` 时 MUST NOT 同时使用 `onCaughtError` 采集相同错误。初始化 SHALL NOT 阻塞应用启动；缺少或为空 DSN 时，系统 SHALL 禁用事件上报并保持应用可用。

#### Scenario: 配置 DSN 后发生渲染错误

- **WHEN** 已配置 `VITE_SENTRY_DSN` 的前端发生未被页面处理的 React 渲染错误
- **THEN** 系统 SHALL 将异常发送至 Sentry，并向用户展示可恢复的全局错误界面

#### Scenario: 未配置 DSN 时启动应用

- **WHEN** `VITE_SENTRY_DSN` 缺失或为空
- **THEN** 系统 SHALL NOT 初始化 Sentry 传输，且应用 SHALL 正常启动

#### Scenario: React 19 自动恢复渲染错误

- **WHEN** React 19 自动恢复一次渲染错误
- **THEN** 系统 SHALL 通过 `onRecoverableError` 将该错误交给 Sentry 错误处理器

### Requirement: 安全的异常发布上下文

系统 SHALL 使用 `VITE_APP_ENV` 标记 Sentry 环境，并使用 `VITE_APP_VERSION` 标记 release；未设置环境时 SHALL 使用 Vite mode。系统 MUST 禁用默认 PII 发送，且 MUST NOT 配置用户身份、会话回放、性能追踪、完整请求体、Cookie、凭据或 Sentry 上传令牌到浏览器产物。

#### Scenario: 生产事件带有发布信息

- **WHEN** 部署者以 `VITE_APP_ENV` 和 `VITE_APP_VERSION` 构建已配置 DSN 的前端
- **THEN** 新上报的 Sentry 事件 SHALL 带有对应的 environment 和 release

#### Scenario: 构建浏览器产物

- **WHEN** Docker Compose 使用 `FRONTEND_*` 部署变量构建 frontend 镜像
- **THEN** 系统 SHALL 仅在 frontend build args 中将其映射为公开的 `VITE_*` 监控配置，且 SHALL NOT 将 `SENTRY_AUTH_TOKEN` 或其他私密凭据写入镜像

### Requirement: 根级错误恢复

系统 SHALL 为根级 React 组件树提供错误边界。错误边界界面 MUST 使用可理解的中文文案，并提供刷新页面的恢复操作。

#### Scenario: 用户遇到不可恢复的渲染错误

- **WHEN** 根级 Error Boundary 捕获渲染错误
- **THEN** 用户 SHALL 看到错误说明和刷新页面操作，而不是空白页面或原始堆栈

### Requirement: React 19 工具链一致性

前端生产构建和 Vitest SHALL 使用相同的 React Compiler 配置。项目 MUST 声明 Node.js `>=24.18.0`，且前端 Dockerfile MUST 使用不低于该基线的 Node.js 镜像，以满足已解析前端依赖的运行时要求。

#### Scenario: 运行生产构建和单元测试

- **WHEN** 开发者运行生产构建或 Vitest 单元测试
- **THEN** 两者 SHALL 启用相同的 React Compiler preset

#### Scenario: 安装前端依赖

- **WHEN** 开发者使用不低于 `24.18.0` 的 Node.js 版本安装依赖
- **THEN** 已解析的 React Router SHALL 满足其 Node.js engine 要求

#### Scenario: 构建前端容器

- **WHEN** Docker 构建前端开发或生产镜像
- **THEN** 构建阶段 SHALL 使用不低于 `24.18.0` 的 Node.js 镜像
