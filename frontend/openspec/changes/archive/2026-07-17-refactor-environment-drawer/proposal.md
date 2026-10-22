## Why

`StageDrawer/Environment/index.tsx` 已承载视图状态、表单初始化、查询、mutation、错误恢复、Drawer 标题/Footer 和六类视图渲染，超过 500 行。继续在入口堆叠逻辑会提高环境功能迭代与回归的成本。

## What Changes

- 拆分环境 Drawer 的纯视图、标题/Footer 组合和领域操作编排，保留 `index.tsx` 作为公开入口。
- 将环境表单输入转换与视图切换整理为可测试的同目录模块。
- 保持环境管理的 API、文案、操作顺序与可观察行为不变。

## Capabilities

### New Capabilities

- `environment-drawer-modularity`: 定义环境 Drawer 内部模块化与稳定行为边界。

### Modified Capabilities

无。

## Impact

- 受影响代码：`src/pages/project-detail/StageDrawer/Environment/`。
- 不修改 API、领域类型、Vite mock、依赖或页面路由。
