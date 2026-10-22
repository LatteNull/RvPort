## 1. 测试基础设施

- [x] 1.1 安装 Vitest、jsdom、React Testing Library、jest-dom 和 user-event 开发依赖
- [x] 1.2 配置 Vitest 测试环境、`@` 别名和测试发现规则；将 `pnpm test` 定义为 `vitest run`
- [x] 1.3 将 `pnpm test:watch` 定义为本地开发用的 `vitest` watch 命令，且不将其作为交付验证命令
- [x] 1.4 创建统一测试 setup，清理 DOM、mock、`localStorage`、计时器、QueryClient 与共享状态
- [x] 1.5 创建可复用测试 helper，提供 QueryClient/Router 渲染包装、最小 fixture，以及按需浏览器 API 或第三方模块 mock
- [x] 1.6 为 auth store 的持久化和模块级会话状态建立可靠的测试重置边界；必要时进行最小可测试性重构

## 2. 首批单元测试

- [x] 2.1 为阶段状态归一化、展示文本和样式配置添加纯逻辑测试
- [x] 2.2 为认证 store 的会话缓存、并发校验与登出行为添加测试
- [x] 2.3 为认证与访客路由守卫的重定向行为添加测试
- [x] 2.4 为共享请求客户端的 CSRF、响应拆包、401/403 和通用失败处理添加边界测试
- [x] 2.5 为受影响领域 API 与 Vite mock 的方法、路径、数据和成功/失败包络一致性添加契约测试
- [x] 2.6 为项目流水线数据 hook 的查询启用条件、状态复用和当前阶段标题添加测试
- [x] 2.7 为环境列表的关键词、组合筛选和重置行为添加组件测试

## 3. 质量验证与交付约定

- [x] 3.1 运行 `pnpm test` 并修复测试失败
- [x] 3.2 运行 `pnpm format:check`、`pnpm lint` 和 `pnpm typecheck`
- [x] 3.3 核对测试脚本和首批测试能够执行 `openspec/project.md` 的单元测试策略与交付验证要求
- [x] 3.4 运行 `openspec validate frontend-unit-tests --strict` 并记录验证结果
