## Context

`@sentry/react` 已加入前端依赖和 lockfile，但应用入口没有初始化 SDK，生产异常不可观测。前端采用 React 19、Vite 构建，`VITE_*` 在构建期注入浏览器产物；生产镜像由 Docker Compose 构建，Nginx 仅在运行时处理 API 反向代理。

项目级宪章要求错误上报经统一边界进行，关联环境、版本和可安全传输的排障信息，且不得包含凭据、Cookie、完整请求体或敏感文件内容。

## Goals / Non-Goals

**Goals:**

- 在有 DSN 时初始化 Sentry 浏览器 SDK，采集未处理异常和 React 渲染错误。
- 为根级渲染错误提供可恢复界面，并保持 Sentry 未配置时的正常应用启动。
- 使用 `VITE_SENTRY_DSN`、`VITE_APP_ENV` 和 `VITE_APP_VERSION` 统一标记环境与 release。
- 让 Docker Compose 在**构建期**传递浏览器可见配置，且不把私密 token 写入前端产物。
- 让测试与生产构建使用一致的 React Compiler 配置，并声明满足已安装 React Router 的 Node.js 基线。

**Non-Goals:**

- 不启用会话回放、性能追踪、用户身份/PII 采集或 source map 上传。
- 不引入后端 Sentry SDK、告警策略或 Sentry 组织/项目创建流程。
- 不将 Sentry DSN 作为运行时 Nginx 环境变量替换；静态 Vite 产物不能因此在不重建时改变 DSN。

## Decisions

- 在 `src/observability/sentry.ts` 集中读取并校验环境变量，再调用 `Sentry.init()`；缺少 DSN 时返回而不初始化。这样页面、组件和 API 模块不会散落读取 `import.meta.env`。
- 使用 `Sentry.ErrorBoundary` 包裹根 `App`，通过 Ant Design `Result` 提供刷新页面的恢复入口。相比只依赖全局错误捕获，它能覆盖 React 组件树渲染失败并保留可理解的用户反馈。
- React 19 的 `createRoot` 使用 `Sentry.reactErrorHandler()` 配置 `onUncaughtError` 和 `onRecoverableError`。不配置 `onCaughtError`，因为 `Sentry.ErrorBoundary` 已负责采集被边界捕获的错误，避免重复上报。
- 设置 `sendDefaultPii: false`，不设置用户信息，不启用 replay 和 tracing。Sentry 上报失败由 SDK 自行处理，绝不阻断应用渲染。
- Vite 和 Vitest 共用 `react()`、`@rolldown/plugin-babel` 与 `reactCompilerPreset()`；`package.json` 声明 Node.js `>=24.18.0`，两个前端 Dockerfile 使用 `node:24.18-alpine`。该 LTS 基线满足已解析的 `react-router@8.2.0` engine 要求，并提供比 Node 22 更长的支持周期。
- Dockerfile 声明 `VITE_SENTRY_DSN`、`VITE_APP_ENV`、`VITE_APP_VERSION` build args；根 Compose 使用 `FRONTEND_SENTRY_DSN`、`FRONTEND_APP_ENV`、`FRONTEND_APP_VERSION` 作为整套部署的分组变量，并仅在 frontend build 中映射为对应 `VITE_*` 值。DSN 是浏览器可见标识，不是密钥；`SENTRY_AUTH_TOKEN` 等上传凭据不进入 Dockerfile、Compose 或前端产物。
- `VITE_APP_VERSION` 未显式传入时使用 `package.json` 版本作为构建默认值；生产发布流程可覆盖为 Git tag 或构建号。

## Risks / Trade-offs

- [未设置 DSN 导致没有生产事件] → 初始化模块明确禁用并在 README 中列出生产部署必填配置。
- [构建变量被误认为运行时变量] → README 与 Compose 注释明确 `FRONTEND_*` 仅映射至 frontend `build.args`，修改后必须重建 frontend 镜像。
- [浏览器配置泄露敏感数据] → 仅允许 `VITE_*` 中的公开 DSN、环境和版本；不配置 auth token 或 PII。
- [Error Boundary 无法捕获事件回调/异步错误] → 保留 React 19 root error hooks 与 SDK 默认全局异常采集；领域异步错误仍必须按既有用户反馈规则处理。
- [测试与生产编译结果不一致] → Vitest 使用与 Vite 相同的 React Compiler 配置。

## Migration Plan

1. 在 Sentry 创建前端项目并取得公开 DSN。
2. 部署时设置 `FRONTEND_SENTRY_DSN`、`FRONTEND_APP_ENV=production` 和发布版本后重建 Compose frontend 镜像。
3. 通过受控测试异常验证事件带有 `environment` 和 `release` 标签。
4. 回滚时移除 DSN 或回退镜像；缺少 DSN 的构建不会发送事件。

## Open Questions

无。性能采样、会话回放和 source map 上传将在实际监控容量、隐私和 CI 凭据策略明确后另行变更。
