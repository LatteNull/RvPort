## Why

前端的严格 OpenSpec 校验、格式化、lint 与 TypeScript 检查目前均未通过；审查还发现超大页面模块、依赖 Ant Design 内部样式、非标准表单语义和无界日志渲染等质量风险。需要在不改变已有业务流程与 API 契约的前提下恢复可交付门禁，并收敛这些现代化设计缺口。

## What Changes

- 修复所有主 OpenSpec 规格的 Purpose 与格式，使严格校验通过。
- 修复当前 lint、格式和 TypeScript 错误，并补充对应回归测试。
- 拆分职责混杂的大型 Stage Drawer，保持公开行为与已有路由、API 契约不变。
- 以 Ant Design 语义化 `styles`/`classNames` 替换业务样式中的内部选择器；修复无效的 CSS Module 选择器。
- 为表单补齐原生输入语义，为日志视图提供大内容渲染保护，并集中地区化格式化。

## Capabilities

### New Capabilities

- `frontend-quality-baseline`: 定义前端工程质量门禁、可访问表单、可扩展日志和样式边界的持续性要求。

### Modified Capabilities

<!-- 现有业务能力的可观察流程与 API 契约不变。 -->

## Impact

- 受影响区域：`openspec/specs/`、`src/components/`、`src/pages/`、`src/styles/` 及相应测试。
- 不新增运行时依赖，不变更后端 API、认证模型、路由地址或业务状态机。
