## Purpose

定义 RvPort-Frontend 的单元测试运行环境、测试隔离规则、关键边界覆盖与后续功能 change 的可执行测试入口。

## Requirements

### Requirement: 前端单元测试运行环境

前端 SHALL 提供基于 Vitest 的单元测试命令，并使用 jsdom 运行需要 DOM 的 React 组件测试。测试运行器 SHALL 解析既有 `@` 源码别名，并加载统一测试初始化。`pnpm test` MUST 以非 watch 模式执行并以退出码反映结果。

#### Scenario: 开发者运行单元测试

- **WHEN** 开发者在 `frontend/` 目录运行 `pnpm test`
- **THEN** 系统 SHALL 以非 watch 模式执行所有已发现的前端单元测试并以退出码反映通过或失败

#### Scenario: 开发者持续编写测试

- **WHEN** 开发者在 `frontend/` 目录运行 `pnpm test:watch`
- **THEN** 系统 SHALL 以 watch 模式运行测试，但该命令 SHALL NOT 被用作交付验证

#### Scenario: 测试导入源码别名

- **WHEN** 单元测试通过 `@/...` 导入前端源码
- **THEN** 测试运行器 SHALL 将该别名解析至 `src/`

### Requirement: 测试隔离

前端单元测试 SHALL 不依赖真实后端、真实浏览器会话、外部 CDN 或此前测试遗留的共享状态。测试初始化和 helper SHALL 在每例测试后清理 DOM、mock、浏览器存储、计时器、QueryClient 与被测共享状态。若模块级状态无法通过清理恢复，测试基础设施 SHALL 提供明确可重置边界。

#### Scenario: 连续运行状态测试

- **WHEN** 两个测试连续使用认证 store 或浏览器存储
- **THEN** 后一个测试 SHALL 不观察到前一个测试写入的认证状态或存储数据

### Requirement: 共享请求客户端与领域 API 契约测试

前端 SHALL 为共享请求客户端和受影响领域 API 维护边界测试。测试 SHALL 验证请求客户端对成功包络、CSRF、认证/权限失败和通用失败的可观察处理，并使用隔离的测试替身验证领域 API 的方法、路径、数据形状和当前响应包络。

#### Scenario: 不安全请求使用 CSRF

- **WHEN** 领域 API 发起 `POST`、`PUT`、`PATCH` 或 `DELETE` 请求
- **THEN** 测试 SHALL 验证请求客户端获取并附加 CSRF token，且不会将 token 获取请求再次视为不安全请求

#### Scenario: API 失败被正确处理

- **WHEN** 请求客户端接收未认证、无权限或通用 API 失败响应
- **THEN** 测试 SHALL 验证认证状态、重定向/刷新行为和用户反馈符合共享请求边界的定义

#### Scenario: 领域 API 与测试 fixture 一致

- **WHEN** 一个领域 API 被新增或修改
- **THEN** 测试 SHALL 验证其方法、路径、请求数据和成功/失败响应包络与已批准契约一致

### Requirement: 核心业务行为测试

前端 SHALL 为关键业务边界维护单元测试，至少覆盖阶段状态归一化、认证会话与路由守卫、项目流水线状态数据处理，以及环境列表的筛选与重置行为。测试 SHALL 验证业务可观察结果，而非第三方组件内部实现。

#### Scenario: 后端阶段状态映射

- **WHEN** 测试向阶段状态映射提供后端 `DONE`、`RUNNING`、`BLOCKED` 或 `PENDING` 状态
- **THEN** 测试 SHALL 验证其映射为正确的前端 workflow 状态及对应展示配置

#### Scenario: 未认证访问受保护路由

- **WHEN** 认证会话校验失败且测试执行受保护路由守卫
- **THEN** 测试 SHALL 验证认证状态被清除并发生到 `/login` 的重定向

#### Scenario: 环境列表组合筛选

- **WHEN** 用户在环境列表选择角色和状态筛选条件
- **THEN** 测试 SHALL 验证向分页 API 传递全部已选角色和状态条件，且重置后重新请求未筛选列表

### Requirement: 项目级测试策略的可执行入口

前端 SHALL 提供项目级 `openspec/project.md` 所规定的单元测试执行入口。该入口 SHALL 支持后续功能 change 为可观察业务行为补充测试，并支持在交付前以非 watch 模式验证测试结果。

#### Scenario: 功能实现包含行为变更

- **WHEN** 后续前端 change 新增或修改可观察业务行为
- **THEN** 实施者 SHALL 能通过项目测试环境，在同一 change 中新增或更新覆盖该行为的单元测试

#### Scenario: 完成功能 change 前验证

- **WHEN** 实施者准备将包含前端功能代码的 change 标记为完成
- **THEN** 实施者 SHALL 能运行 `pnpm test` 并获得可用于项目级交付验证的通过、失败或阻塞记录
