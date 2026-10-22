## Why

项目领域功能持续增加后，原 `src/api/project.ts` 已聚合多个无关领域的后端 DTO、字段映射与 API 函数。继续在单一入口追加功能会提高改动冲突、回归与定位成本。

本次 change 在不改变任何前端可观察行为或正式 API 契约的前提下，按领域重组项目 API 与开发期 mock，并恢复当前 lint 基线。

## What Changes

- 将 `src/api/project/` 与 `src/api/auth/` 统一为领域目录入口，并将项目 API 按现有领域拆分为内部模块，保留 `@/api/project` 与 `@/api/auth` 的公共导出和全部现有函数签名。
- 清理与本次 API 目录调整相关的静态检查问题。
- 保持 API 请求 URL、请求体、响应映射和既有页面调用方不变；迁移或补充覆盖这些边界的单元测试。

## Capabilities

### New Capabilities

- `project-domain-modularity`：项目领域 API 的模块化边界，以及公共调用契约不因内部重组发生变化。

### Modified Capabilities

无。请求契约、UI 行为和现有规范需求均不改变。

## Impact

- 受影响代码：`src/api/auth/`、`src/api/project/`、`src/api/project.test.ts`、`src/App.tsx`。
- 调用方影响：调用方继续从 `@/api/project` 与 `@/types/project` 导入，无需因目录重组修改业务页面。
- API 与依赖：不改变正式 API 契约，不新增或移除依赖。
- 验证：执行 API 单元测试、`pnpm format:check`、`pnpm lint`、`pnpm typecheck`、`pnpm test` 与 OpenSpec 校验。
