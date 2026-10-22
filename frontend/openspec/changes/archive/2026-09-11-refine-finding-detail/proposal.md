## Why

当前 Finding 详情虽然已经接入 Scanner V2 的结构化数据，但结论、代码位置、证据链、扫描事实和处理建议被拆散在多个同权区域中，字段仍直接暴露英文枚举与“后端待提供”等实现语义，用户难以快速回答“发现了什么、为什么成立、影响哪里、下一步做什么”。需要围绕迁移判断重组详情页，并为缺失、部分完成和多命中位置建立一致的展示规则。

## What Changes

- 将 Finding 详情重组为“结论摘要 → 主要代码证据 → 判断依据 → 处理建议”的连续阅读路径，降低当前左右多卡片布局造成的信息跳跃。
- 统一展示风险、阻塞性、可处理性、分析完整度、架构可达性和业务状态，并将后端枚举转换为面向用户的中文语义。
- 以 `primaryOccurrenceId` 指定的命中作为默认位置；用户切换其他 occurrence 时，同步更新文件位置、代码上下文及该位置的配置、选择状态和原因。
- 将 `fact`、`conclusion`、`occurrences` 与 `evidenceChain` 组织为可追溯的判断依据；对断点、歧义、截断和缺失字段提供明确但不过度打扰的降级说明。
- 将迁移建议与“纳入报告 / 排除”状态放在明确的下一步区域；历史扫描详情保持只读，不提供会改变当前报告输入的操作。
- 保留原始扫描数据作为折叠的诊断入口，不让内部 JSON、字段名或占位文案干扰主要阅读路径。
- 补充 Finding 详情的展示、位置切换、降级、只读和报告操作测试。

## Capabilities

### New Capabilities

- `knowledge-base-finding-detail`: 定义知识库扫描 Finding 详情的阅读层级、结构化证据展示、多位置联动、报告操作和异常降级行为。

### Modified Capabilities

无。

## Impact

- 主要影响 `src/pages/project-detail/StageDrawer/KnowledgeBase/components/FindingDetail.tsx`、知识库展示映射、局部 SCSS Module 和相邻测试。
- 复用现有 Finding 详情与代码上下文接口、TanStack Query 缓存和 `MigrationInputActions`；不新增运行时依赖。
- 前端继续以 `fact`、`conclusion`、`occurrences`、`evidenceChain` 和 `evidence` 为事实来源；若后端补充顶层 `primaryOccurrenceId`，类型和 fixture 需要同步更新，现有嵌套字段读取只作为明确的兼容路径。
- 不修改扫描器规则、后端判断逻辑、Finding 列表筛选或 Workflow 拓扑。
