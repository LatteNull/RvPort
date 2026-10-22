## Why

现有浮点精度扫描结果协议采用扁平的 snake_case 结构，与 RvPort 已使用的 KB Scanner v2 `scan/project/summary/findings/diagnostics/extensions` 组织模型不一致，增加了后续展示、审计和消费的认知成本。当前旧结果协议尚无外部消费者，因此应在接入其他系统前直接完成一次明确的破坏性切换，避免维护没有价值的双版本兼容层。

## What Changes

- **BREAKING**：以唯一的 `schemaVersion: "2.0"` 结果协议替换当前 `FloatingPointPrecisionScanResult` 1.4；不保留旧 serializer、版本选择参数、双写、转换器或迁移期。
- 顶层结果改为 KB Scanner v2 风格的 `scan`、`project`、`summary`、`findings`、`diagnostics` 和可选 `extensions`，公共字段统一使用 camelCase。
- finding 改为 `fact`、`conclusion`、`occurrences`、`primaryOccurrenceId`、`evidenceChain` 和可选 `extensions`，以可验证引用链表达 AST、LLVM IR、AST↔IR binding、profile、build context、规则 assessment 与结论之间的关系。
- 保留并强化浮点扫描专属语义，包括规则及版本、确定性/启发式 evidence origin、人工确认要求、profile/build-context fingerprints、unknown/frontier、validation plan、suppression 审计和完整双语展示字段。
- 使用 `org.rvport.floating-point-scanner.*` 命名空间承载不属于公共骨架的分析、profiles、suppression、预算、缓存和运行元数据；不得复用 KB Scanner 专属 knowledge、fact、reason 或 step 枚举。
- 将原顶层 `facts`、`ir_facts`、`evidence` 和 `assessments` 投影为 finding 内的 typed references/evidence chain 或受版本化约束的审计扩展，避免后端重建语义关系。
- 同步切换 CLI 正常及失败输出、Schema 校验、协议不变量、稳定 ID 与排序、原子输出、validation corpus/oracle、benchmark、缓存等价性检查、fixtures 和文档。
- 本变更只修改浮点精度扫描工具；不修改 RvPort 后端、前端、共享 BC 生产逻辑、任务编排或其他工具。scan request、canonical AST facts、LLVM facts、AST↔IR evidence、共享 BC manifest、cache entry 和 validation result 的独立协议不因本变更改版。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `scanner-io-contract`：将唯一生产 scan result 切换为 KB Scanner v2 风格的浮点扫描结果 2.0，并规定引用完整性、双语字段、浮点专属扩展和破坏性切换边界。
- `scanner-quality-gates`：调整输出协议验收要求，明确本次不提供旧结果兼容，同时要求所有项目内消费者、fixtures、确定性测试和覆盖率门槛在同一变更中完成切换。

## Impact

- 影响 `src/floating_point_precision_scanner` 中的结果 Schema、结果构建、规则 finding 投影、诊断聚合、CLI 失败结果、协议校验和确定性摘要逻辑。
- 影响工具内所有读取或断言旧结果形状的单元测试、validation/benchmark 脚本、corpus/oracle、fixtures、示例和文档。
- 不影响后端、前端、共享 BC 制品生产者、memory-order-analyzer 或其他 RvPort 模块；这些系统的接入由独立 change 负责。
- 这是有意的结果协议破坏性变更；所有仓库内使用者必须原子切换，交付时不得残留对旧 `schema_version: "1.4"` 结果的生产或消费路径。
