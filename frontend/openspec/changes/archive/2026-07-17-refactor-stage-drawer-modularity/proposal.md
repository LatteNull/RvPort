## Why

`StageDrawer` 下的阶段模块随着环境、制品、知识库、SBOM 和报告等能力增加，逐步在入口组件中混合了视图切换、服务端请求、表单状态、Drawer chrome 与展示区域。环境管理已验证按职责拆分的可行性；现在需要将该边界推广为一致的阶段抽屉组织方式，降低后续功能迭代的理解与回归成本。

## What Changes

- 盘点所有 `StageDrawer` 阶段模块，以入口复杂度和交互风险确定迁移顺序。
- 为包含多视图、表单和领域操作的阶段抽屉，统一入口、编排 hook、领域类型/输入转换及 `components/` 展示模块的职责边界。
- 将 Environment 现有拆分整理为统一目录结构，并在后续阶段迁移中保持公开 props、API 调用、交互文案和可观察行为不变。
- 对纯展示或简单单表单 Drawer 保持轻量结构，避免机械性创建无收益的模块。

## Capabilities

### New Capabilities

- `stage-drawer-modularity`: 定义复杂 StageDrawer 的模块边界、迁移准则和稳定行为要求。

### Modified Capabilities

无。

## Impact

- 受影响代码：`src/pages/project-detail/StageDrawer/` 下的阶段模块及其局部测试。
- 不修改后端 API、领域类型、路由、依赖或用户可见的业务流程。
