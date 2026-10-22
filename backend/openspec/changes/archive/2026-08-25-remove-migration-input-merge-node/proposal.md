## Why

当前“迁移输入合并”作为独立节点会把用户确认动作集中到一个额外页面，实际流程中确认更适合发生在各分析节点内。继续保留独立合并节点会增加前端路径、后端 API 语义和报告输入状态之间的冗余。

## What Changes

- **BREAKING**：移除“迁移输入合并”作为主流程节点，不再推荐前端调用自动合并入口来准备报告输入。
- 保留 `migration_input_refs` 作为报告输入的统一 reference 表，报告仍只读取 `CONFIRMED`。
- 各分析节点在产出结果后负责创建或维护对应 migration input reference，并在本节点内提供人工加入、撤回和状态确认能力。
- 增加统一默认确认规则：`CRITICAL`、`HIGH`、`MEDIUM`、`INFO`、`COMMENT` 默认进入报告；`LOW` 默认不进入报告但可人工加入。
- 新流程不再使用 `SBOM_RESULT` 作为前序来源；遇到新流程中的 SBOM 自动合并、导入或展示入口时移除或标记 deprecated 后删除。
- 保留历史 `SBOM_RESULT` 读取兼容能力，避免旧报告快照和旧数据详情查询被破坏。

## Capabilities

### New Capabilities
- `node-local-migration-input-confirmation`: 定义迁移输入确认下沉到各分析节点后的统一状态规则、默认确认策略和来源边界。

### Modified Capabilities
- `migration-input-merge`: 废弃独立迁移输入合并节点和自动合并主流程，保留 reference 模型作为后端内部统一报告输入。
- `backend-api-design`: 调整迁移输入 API 主流程描述，移除 SBOM 作为新前序来源，明确节点内确认和历史兼容边界。
- `migration-report-runtime`: 明确报告继续只消费 `CONFIRMED` reference，但这些 reference 可由各节点按默认确认规则生成。
- `kb-scan-runtime`: 知识库扫描结果需要能在扫描节点内进入迁移输入确认流程。
- `dependency-analysis-runtime`: 依赖分析结果需要能在依赖分析节点内进入迁移输入确认流程，并继续作为新主流程依赖来源。
- `api-e2e-test-suite`: 调整 E2E 覆盖，从独立迁移输入合并模块迁移到节点内确认、撤回和报告生成链路。

## Impact

- 影响后端迁移输入 API、KB 扫描 API、依赖分析 API、报告生成和 E2E 测试。
- 数据库表 `migration_input_sets` 和 `migration_input_refs` 保留，不做破坏性删除。
- 前端后续应移除独立“迁移输入合并”页面，将确认控件放到各分析节点结果列表中。
- 历史 SBOM 数据和旧报告快照保留兼容，但 SBOM 不再作为新流程前序输入。
