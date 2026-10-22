## Why

前端尚未具备统一的生产异常上报边界。发生未捕获异常或渲染失败时，团队无法可靠关联运行环境和前端发布版本，也不能在不泄露敏感数据的前提下进行排障。

## What Changes

- 使用已安装的 `@sentry/react` 初始化统一的浏览器异常上报边界。
- 增加根级 Error Boundary，为渲染崩溃提供可恢复的用户界面。
- 通过受控的 `VITE_*` 配置提供 Sentry DSN、环境和前端发布版本；未配置 DSN 时静默禁用上报。
- 将生产镜像的 Sentry 构建配置接入 Compose build args，并补充部署说明与单元测试。

## Capabilities

### New Capabilities

- `frontend-error-observability`: 前端异常采集、发布版本标记和安全的降级体验。

### Modified Capabilities

无。

## Impact

- `src/main.tsx`、新增可观测性模块与应用级错误兜底组件。
- `vite.config.ts`、生产 Dockerfile、根 `docker-compose.yml` 与前端 README。
- 使用现有 `@sentry/react` 依赖；不引入性能追踪、会话回放、后端 Sentry SDK 或 source map 上传。
