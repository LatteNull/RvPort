## Context

RvPort-Frontend 使用 Vite、React、TanStack Query、Zustand、Axios、Ant Design 与 React Flow，但尚无测试运行器、浏览器测试环境或首批测试。项目级 `openspec/project.md` 定义了所有前端功能 change 的测试责任、隔离原则和交付验证门槛；本 change 的职责是提供满足这些约定的最小实现，而不是再次定义项目治理规则。

## Goals / Non-Goals

**Goals:**

- 建立可在本地和自动化环境中重复运行的前端单元测试命令。
- 用与 Vite 相容的工具链测试纯逻辑、状态边界和用户可见的组件行为。
- 将项目级“同步测试与交付验证”约定落实为可执行脚本、测试隔离机制和首批示例测试。

**Non-Goals:**

- 不在本 change 引入端到端测试、视觉回归测试或浏览器自动化。
- 不以覆盖率百分比作为合并门槛。
- 不测试 Ant Design、React Flow、Monaco 或 Axios 自身的内部实现。
- 不修改 `project.md` 之外的产品需求、API 合同或生产运行时行为。

## Decisions

### 使用 Vitest、jsdom 与 React Testing Library

Vitest 与现有 Vite 配置、ESM、TypeScript 和 `@` 路径别名兼容，jsdom 提供组件测试所需 DOM，React Testing Library 以用户可见的文本、角色和交互验证行为。`@testing-library/jest-dom` 提供 DOM 断言，`@testing-library/user-event` 用于模拟真实用户操作。

Jest 是可行替代方案，但需要额外处理 Vite 转换、别名和 ESM 配置，故不采用。覆盖率报告仅在开发者安装 `@vitest/coverage-v8` 并明确启用相应脚本时提供，不作为初始硬性要求。

### 保持测试层次轻量且按边界隔离

纯函数直接单测；Zustand、路由守卫、TanStack Query hook 测试其公开行为；组件仅测试用户可见结果和回调。网络请求、Monaco 和 React Flow 等外部或浏览器依赖通过 Vitest mock 隔离，避免测试依赖真实后端、CDN 或复杂浏览器 API。

测试初始化在每例后清理 DOM、mock、`localStorage`、计时器、QueryClient 与共享状态，确保用例独立。为避免把测试框架细节散入业务用例，提供可复用的测试 helper：组件渲染所需的 QueryClient/Router provider、最小领域 fixture，以及按需提供的浏览器 API 或第三方模块 mock。

认证 store 的持久化状态和模块级会话 promise 是已知隔离风险。测试必须能在每例后恢复初始状态；若现有边界无法可靠恢复，应以最小重构建立明确的可重置边界，而不是依赖测试执行顺序。

### 首批覆盖用于证明工具链与策略可行

首批测试选择项目级策略中的五类高价值边界：纯状态映射、认证/路由状态、共享请求客户端与 API/mock 契约、TanStack Query 数据处理、用户可见的列表筛选。它们共同验证别名解析、jsdom 渲染、异步状态、共享 store 隔离、错误处理与外部依赖 mock，而无需测试所有页面。

| 测试层次  | 首批对象                            | 验证重点                                           |
| --------- | ----------------------------------- | -------------------------------------------------- |
| 纯逻辑    | 阶段状态映射                        | 确定性输入输出和默认值                             |
| 状态/路由 | auth store、guards                  | 会话缓存、并发复用、重定向                         |
| 请求/契约 | request client、领域 API、Vite mock | CSRF、响应拆包、认证/权限失败、URL/方法/包络一致性 |
| 数据边界  | pipeline hook                       | 查询启用、状态复用、派生展示值                     |
| 组件行为  | 环境列表                            | 筛选、重置和可见结果                               |

### 提供项目级约定所需的命令，而非重新定义约定

`openspec/project.md` 是所有前端 change 的规范来源：可观察业务行为变更必须同步测试；纯重构不强制新增测试但不可破坏既有测试；断言面向业务结果并隔离外部边界。此 change 仅负责提供执行这些规则所需的工具、脚本和首批示例。

交付脚本 `pnpm test` 固定为 `vitest run`，完成后以退出码报告结果；`pnpm test:watch` 固定为 `vitest`，仅服务本地开发，不能作为交付验证。交付前失败必须修复，或在交付说明中记录经确认的外部阻塞和未验证范围；不得通过静默删除、跳过或弱化测试绕过失败。

## Risks / Trade-offs

- [jsdom 与真实浏览器存在差异] → 仅在单元测试验证业务行为；复杂布局、编辑器和画布交互留给后续端到端测试。
- [第三方 UI 库 DOM 结构升级造成断言脆弱] → 优先按角色、标签和可见文本断言，避免内部 className 与实现细节。
- [Zustand 持久化和模块级 promise 导致测试泄漏] → 在测试 setup 中统一恢复 store、存储与 mock，并为时间/并发场景编写显式测试。
- [测试运行时间增长] → 首批聚焦高风险边界，默认命令只运行单元测试，不启动 Vite server 或真实网络。
