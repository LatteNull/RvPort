## Context

`StageDrawer` 现有九个阶段模块的入口体量从 28 到 564 行不等。`MigrationInputMerge`、`KnowledgeBase`、`KnowledgeBaseAi`、`Assets`、`AssessmentReport`、`Sbom` 和 `Project` 均同时包含本地视图状态、TanStack Query、mutation、表单、Drawer 标题/Footer 与多块展示 JSX；其中 `MigrationInputMerge` 与 `KnowledgeBase` 的风险最高。Environment 已完成第一轮拆分，但其展示文件仍平铺在模块根目录。

## Goals / Non-Goals

### Goals

- 为复杂阶段 Drawer 建立一致、可发现的职责边界和目录结构。
- 保持所有公开 `StageDrawerProps`、API 调用、缓存键、用户文案、确认交互与视图切换不变。
- 以小批次迁移和局部测试保护高交互阶段。

### Non-Goals

- 不把简单 Drawer 强制拆成 hook 或多个组件。
- 不抽象跨阶段的“通用业务 hook”或统一所有 Drawer 的视觉 chrome。
- 不变更后端 API、项目领域类型、路由、依赖或业务流程。

## Design

### 目录与职责

复杂 Drawer 采用以下结构；只有职责实际存在时才创建对应文件：

```text
StageDrawer/<Stage>/
  index.tsx                  # 默认导出和 BaseDrawer 组合入口
  use<Stage>Drawer.ts        # 本地视图状态、query、mutation、缓存和操作回调
  types.ts                   # 本模块 view、表单和局部领域类型
  input.ts                   # 可独立测试的表单/请求转换（如适用）
  components/
    content.tsx              # 按 view 选择内容区域
    drawer-chrome.tsx        # 标题、Footer 和确认交互；不调用领域 API
    *.tsx                    # 表格、表单、详情等稳定展示区域
```

`index.tsx` 保持对外 props 和 Drawer 配置，是组合边界；它不直接选择领域 API 或维护 mutation。`use<Stage>Drawer.ts` 是服务端状态和本地交互状态的唯一编排边界。`components/` 只接收显式数据、状态和回调，不能调用领域 API。Environment 迁移至该同一结构。

### 迁移批次

1. 高复杂度：`MigrationInputMerge`、`KnowledgeBase`、`KnowledgeBaseAi`，优先拆分多视图、批量选择和冲突/结果流程。
2. 中复杂度：`Assets`、`AssessmentReport`、`Sbom`、`Project`，按表单、详情和动作区分稳定展示区域与操作编排。
3. 轻量模块：`Default` 维持现状；仅在新增独立职责时采用相同边界。

每个模块独立提交可验证的迁移，避免跨阶段的大型机械移动。

### 行为与测试

迁移不改变 query key、mutation 顺序、缓存失效、反馈文案、确认框、关闭/返回语义或加载与空状态。现有测试随文件移动更新；对新增的纯输入/视图状态逻辑补充单元测试。高复杂度阶段补充关键用户操作路径测试。

## Risks / Trade-offs

- 分拆过细会增加定位成本，因此以“独立状态/API 编排”或“独立视觉区域”为拆分阈值，拒绝单行转发组件。
- Footer 依赖表单 dirty 状态，必须继续由同一个 `FormInstance` 传入 chrome，不能重建表单。
- 迁移中容易误改 query `enabled` 条件或缓存键；每个阶段都需保留原调用和测试验证。

## Validation

每批迁移运行相关单元测试；change 完成时使用 Node `>=24.18.0` 运行 `openspec validate refactor-stage-drawer-modularity`、`pnpm format:check`、`pnpm lint`、`pnpm typecheck` 与 `pnpm test`。
