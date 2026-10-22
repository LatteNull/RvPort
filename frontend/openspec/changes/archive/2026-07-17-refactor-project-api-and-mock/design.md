## Context

项目领域 API 原先以单文件承载多个相互独立的业务领域。原 `src/api/project.ts` 同时包含后端 DTO、转换函数和项目、制品、环境、分析、迁移输入及报告 API；`src/api/auth.ts` 则与项目 API 的目录结构不一致。

调用方已统一使用 `@/api/project`、`@/api/auth` 与 `@/types/project`。本次重构不得改变这些外部边界。

## Goals / Non-Goals

**Goals:**

- 将项目 API 的内部实现按既有领域划分，同时保持 `@/api/project` 的函数导出和签名不变。
- 以既有 API 契约测试和新增的纯逻辑测试保护拆分后的行为。
- 清理当前 lint 阻塞项。

**Non-Goals:**

- 不改变正式后端 API、前端类型公共出口、页面 UI、TanStack Query 行为或工作流业务规则。
- 不拆 `src/types/project.ts`，不重构 Drawer，不引入依赖或新的运行时抽象。
- 不修改开发 mock；mock 将在后续独立工作中删除。

## Decisions

### 1. 以稳定 facade 保持 API 调用方不变

以 `src/api/project/index.ts` 作为 facade，只从同目录的领域模块 re-export 现有函数。领域模块按当前 API 函数职责拆分为 projects、workflow、assets、sbom、knowledge-base、knowledge-base-ai、migration-input、assessment-report、environments；后端 DTO 与转换函数置于仅 API 层使用的共享模块。

这样页面和测试不必因文件移动修改 import，且领域模块不会反向依赖页面。替代方案是直接让调用方改为深层路径导入；该方案会造成无行为价值的广泛变更，并把内部目录变成长期公共契约，因此不采用。

### 2. 以“返回值写缓存”或“失效重取”之一为准

本 change 只维持现有 API/mock 行为，不改页面缓存策略；但拆分 API 后，测试与实现必须保留当前函数返回值。页面后续重构可选择“使用完整 mutation 返回值写缓存”或“无完整返回值时失效重取”，不得在同一次动作中对同一 query 同时做两者。

该约定记录为后续 Drawer change 的约束，不在本 change 改动页面。

## Risks / Trade-offs

- [内部模块导出遗漏导致 facade 不完整] → 将现有 `src/api/project.test.ts` 按领域覆盖并保持由 facade 导入。
- [重构范围膨胀至 UI 或类型系统] → tasks 明确排除 Drawer 和 `src/types/project.ts` 的目录重组；新增范围另起 change。

## Migration Plan

1. 先建立内部模块与 facade，逐个移动 API 函数、DTO 和 mapper，并保持现有测试通过。
2. 将 `src/api/project.ts` 与 `src/api/auth.ts` 分别迁移为 `src/api/project/index.ts` 与 `src/api/auth/index.ts`，使领域 API 均使用目录入口。
3. 清理 import 排序问题。
4. 运行 OpenSpec、格式、lint、类型与完整单元测试。

若任一步出现行为回归，保留稳定 facade，将对应领域模块移回入口或回退该模块迁移；本次不涉及开发 mock、数据迁移、发布配置或后端回滚。

## Open Questions

无。`src/types/project.ts` 与 Drawer 重构均明确延后到独立 change。
