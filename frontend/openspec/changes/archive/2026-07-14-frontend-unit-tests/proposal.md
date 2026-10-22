## Why

`project.md` 已将单元测试纳入前端功能交付基线，但前端当前缺少可重复执行的测试命令、隔离环境和示例覆盖，导致该项目级约定无法执行。需要通过本 change 建立最小而可靠的单元测试能力，使后续功能 change 可以遵循统一的测试与验证规则。

## What Changes

- 为 React/Vite 前端引入 Vitest、jsdom 和 React Testing Library 单元测试基础设施及可执行测试脚本。
- 建立能执行项目级测试策略的测试运行环境和隔离规范，包括浏览器环境、测试初始化、外部依赖 mock 与每例测试后的状态清理。
- 为关键纯逻辑、认证/路由状态、共享请求客户端、API/mock 契约和代表性用户交互补充首批单元测试。
- 为项目级约定提供可执行入口：后续功能代码变更可同步补充或更新测试，并在功能完成前以非 watch 模式运行单元测试、处理失败结果或记录外部阻塞。

## Capabilities

### New Capabilities

- `frontend-unit-testing`: 前端单元测试运行环境、测试覆盖范围与功能交付时的测试执行要求。

### Modified Capabilities

无。

## Impact

- 受影响代码：`frontend/package.json`、Vite/Vitest 测试配置、测试初始化与测试 helper、必要的可测试性边界，以及 `src/` 下的测试文件。
- 新增开发依赖：`vitest`、`jsdom`、`@testing-library/react`、`@testing-library/jest-dom`、`@testing-library/user-event`；覆盖率报告如启用则增加 `@vitest/coverage-v8`。
- 不改变生产 API、页面路由或运行时业务行为。
