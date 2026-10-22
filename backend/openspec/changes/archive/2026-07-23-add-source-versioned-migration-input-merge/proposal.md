## Why

当前 KB 扫描、SBOM 分析和后续代码类扫描都会产生候选问题，但项目缺少一个绑定源码版本的人工确认层。修复后源码重新入库时，如果迁移输入和扫描结果仍按项目维度展示，旧版本输入会污染新版本分析和报告。

## What Changes

- 新增“迁移输入合并”能力：为每个 `source_revision` 维护独立迁移输入集合。
- 新增迁移输入 reference 列表，统一展示“问题、来源、风险/状态、路径/组件、建议处理、确认状态”。
- 支持从当前源码版本相关的前序任务结果自动合并迁移输入：
  - 知识库扫描（AI扩展暂时没做）
  - 纯 AI 扫描（暂时没做）
  - 强弱内存模型扫描（暂时没做）
  - SBOM 替代性分析
- 支持在不同分析节点中选择单条或多条真实结果记录，通过批量导入接口加入当前源码版本的迁移输入。
- 暂不实现冲突检测；重复导入只做幂等跳过。
- 报告生成只消费当前源码版本下人工确认后的迁移输入项。
- SBOM 分析本身不绑定源码版本，但 SBOM 结果加入迁移输入时必须绑定当前 `source_revision_id`。

## Capabilities

### New Capabilities

- `migration-input-merge`: 定义源码版本作用域下的迁移输入集合、reference 列表、批量导入、自动合并、确认状态和报告消费边界。

### Modified Capabilities

- `backend-api-design`: 增加迁移输入合并 API、迁移输入列表/详情 API、报告只读取确认项的 API 约定。
- `backend-database-design`: 增加迁移输入集合和迁移输入 reference 表的持久化、索引、唯一约束和跨来源引用约束。
- `project-source-environment`: 明确源码版本创建后应拥有独立迁移输入集合，新源码版本不得继承旧版本输入。
- `kb-scan-runtime`: 明确 KB finding 可作为迁移输入来源，并且代码类来源必须校验 `source_revision_id`。
- `sbom-analysis-runtime`: 明确 SBOM run 不绑定源码版本，但 SBOM result item 加入迁移输入时绑定当前源码版本。

## Impact

- 数据库新增迁移输入集合与迁移输入 reference 表，并补充索引与唯一约束。
- 后端新增 migration input 相关 controller/service/repository/API DTO。
- 报告生成逻辑后续需要从迁移输入 confirmed reference 读取内容，而不是直接读取扫描原始结果。
- E2E 需要覆盖源码版本隔离、批量导入、自动合并、幂等跳过、确认状态和报告输入过滤。
