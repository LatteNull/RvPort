## 1. 固定 Workflow 拓扑

- [x] 1.1 调整 Workflow 阶段、分组和边：隐藏环境扫描、环境与依赖对比与迁移输入合并，并保留隐藏模块代码。
- [x] 1.2 在源码管理后并行布局知识库扫描与构建可用性分析；两条支路汇入评估报告，问题进入人工处理并反馈源码管理，满足条件时直接进入构建验证；源码对比不展示在主画布或源码管理 Drawer；保持自动化测试、优化闭环与归档处于现有后段位置。
- [x] 1.3 更新本地 Workflow 阶段状态映射、聚焦逻辑和节点标题，确保隐藏节点不再参与可见画布状态。

## 2. 构建可用性静态 Drawer

- [x] 2.1 新建 feature-local 静态 model，覆盖 x86 构建与依赖分析的通过、待处理、已失效和无结果示例。
- [x] 2.2 在 StageDrawer 组合入口中接入两个构建可用性节点 Drawer，并确保它们不调用领域 API、TanStack Query、mutation、SSE 或轮询。
- [x] 2.3 实现构建可用性分析的本地演示交互、问题汇总和版本范围展示，不将状态持久化。
- [x] 2.4 将既有构建节点标题保持为“构建验证”，不改变现有双环境构建 Drawer 的 API 调用与提交语义。

## 3. 测试与验证

- [x] 3.1 更新 Workflow 拓扑与节点映射单元测试，覆盖隐藏节点、汇总报告、构建可用性支路和后段节点位置关系。
- [x] 3.2 为静态 Drawer 增加交互测试，覆盖无网络请求、待处理汇总、人工确认和失效状态。
- [ ] 3.3 运行 `pnpm format:check`、`pnpm lint`、`pnpm typecheck`、`pnpm test` 与 `openspec validate refine-build-readiness-workflow --strict`。
