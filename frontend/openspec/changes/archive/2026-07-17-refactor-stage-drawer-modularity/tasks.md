## 1. 基线与目录

- [x] 1.1 为复杂 StageDrawer 建立一致的 `components/`、编排 hook、局部类型/输入转换边界；不为 `Default` 创建机械性模块。
- [x] 1.2 将 Environment 已抽取的展示模块整理到 `components/`，保持入口、hook 和输入转换职责清晰。

## 2. 高复杂度阶段

- [x] 2.1 重构 `MigrationInputMerge`：分离视图状态与 query/mutation 编排、冲突/结果内容和 Drawer chrome。
- [x] 2.2 重构 `KnowledgeBase`：分离扫描配置、结果选择/导出内容与领域操作编排。
- [x] 2.3 重构 `KnowledgeBaseAi`：分离配置/结果内容、批量选择与建议生成/写入编排。

## 3. 中复杂度阶段

- [x] 3.1 重构 `Assets`：分离概览、上传/Git 表单和阶段推进编排。
- [x] 3.2 重构 `AssessmentReport`：分离报告结果、导出配置和重新生成/推进编排。
- [x] 3.3 重构 `Sbom` 与 `Project`：分别分离分析配置/结果操作及项目详情/编辑/推进操作。

## 4. 验证

- [x] 4.1 更新移动文件的既有测试，并为每个复杂阶段的关键操作路径或纯输入转换补充单元测试。
- [x] 4.2 使用 Node `>=24.18.0` 运行 `openspec validate refactor-stage-drawer-modularity`、`pnpm format:check`、`pnpm lint`、`pnpm typecheck` 和 `pnpm test`。
