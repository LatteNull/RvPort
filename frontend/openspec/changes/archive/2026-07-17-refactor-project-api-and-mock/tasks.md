## 1. 项目领域 API 重组

- [x] 1.1 建立 `src/api/project/` 内部领域模块与共享 DTO/mapper 模块，并以 `src/api/project/index.ts` 作为既有公共 API 的 re-export facade。
- [x] 1.2 按 overview/workflow、assets、sbom、knowledge-base、knowledge-base-ai、migration-input、assessment-report 和 environments 迁移既有项目 API 函数，保持 URL、请求体、返回映射和函数签名不变。
- [x] 1.3 调整 `src/api/project.test.ts` 的组织或补充断言，确保测试仍经 `@/api/project` facade 覆盖各领域请求契约。

## 2. 清理与回归验证

- [x] 2.1 修正 `src/App.tsx` 的 import 排序，并清理与本次 API 目录调整相关的静态检查问题。
- [x] 2.2 在 Node `>=24.18.0` 环境运行 `openspec validate refactor-project-api-and-mock`、`pnpm format:check`、`pnpm lint`、`pnpm typecheck` 和 `pnpm test`。
