## 1. 当前上下文过滤

- [x] 1.1 为构建验证、依赖分析、KB 扫描列表请求增加 `currentOnly` / `includeStale` 与必要的 `environmentConfigVersion` 查询参数。
- [x] 1.2 在服务层统一解析 active source revision 和当前 runtime environment version，未显式指定历史参数时默认使用当前上下文。
- [x] 1.3 更新构建验证列表查询，使默认结果只包含当前源码版本和当前运行环境配置版本。
- [x] 1.4 更新依赖分析列表查询，使默认结果只包含当前源码版本和当前运行环境配置版本。
- [x] 1.5 更新 KB 扫描列表查询，使默认结果只包含当前源码版本。

## 2. 陈旧状态响应

- [x] 2.1 为构建验证、依赖分析、KB 扫描响应增加 `currentSourceRevision` 和 `staleReasons`。
- [x] 2.2 保留并统一 `currentRuntimeEnvironment` 语义，环境版本不一致时返回 `RUNTIME_ENVIRONMENT_CHANGED`。
- [x] 2.3 确保详情接口可查看历史记录，并返回对应陈旧状态。

## 3. 报告纳入状态

- [x] 3.1 增加查询当前源码版本最新成功评估报告及其 `report_inputs` input id 集合的 repository 方法。
- [x] 3.2 增加按 `(sourceRevisionId, sourceType, sourceRefId)` 批量查询 migration input reference 状态的方法。
- [x] 3.3 为依赖分析结果列表和详情增加 `migrationInputRefId`、`migrationInputStatus`、`confirmedForNextReport`、`includedInLatestReport` 和 `latestReportId`。
- [x] 3.4 为 KB finding 列表和详情增加同样的报告纳入状态字段。
- [x] 3.5 确认无最新报告、无 reference、reference 已撤回三类场景返回值明确且稳定。

## 4. 报告更新状态

- [x] 4.1 在报告 readiness 中比较当前 confirmed migration input refs 与最新成功报告输入快照。
- [x] 4.2 在报告详情中返回 `reportUpToDate` 与 `reportDiffSummary`。
- [x] 4.3 `reportDiffSummary` 至少包含 added、removed、changed、currentConfirmedInputCount、latestReportInputCount 和 latestReportMissing。
- [x] 4.4 只比较报告可见关键字段，避免完整来源详情变化造成噪声。

## 5. 数据库与性能

- [x] 5.1 检查现有索引是否覆盖 `migration_input_refs(source_revision_id, source_type, source_ref_id)`、`report_inputs(report_id, input_id)` 和节点列表默认过滤字段。
- [x] 5.2 如索引不足，通过 Liquibase 增加非破坏性索引。
- [x] 5.3 保证报告纳入状态按分页当前页批量计算，避免 N+1 查询。

## 6. 测试与验证

- [x] 6.1 补充源码更新后旧构建、旧依赖分析、旧 KB 扫描默认不可见的正常流程测试。
- [x] 6.2 补充 `includeStale=true` 或显式历史参数能查看旧记录的 edge case 测试。
- [x] 6.3 补充运行环境更新后旧环境版本构建和依赖分析默认不可见的测试。
- [x] 6.4 补充报告生成后新增/撤回/修改 migration input 时 `reportUpToDate=false` 的测试。
- [x] 6.5 补充 KB finding 和依赖结果列表中报告纳入状态的正常、异常和 edge case 测试。
- [x] 6.6 更新 API E2E 模块，覆盖当前上下文过滤、历史查看和报告状态字段。
- [x] 6.7 运行 Maven 测试和相关 E2E，记录结果。

验证记录：

- `mvn test` 通过：466 个测试，0 failures，0 errors，2 skipped。
- `node --check e2e/cases/010-build-validation.js e2e/cases/008-migration-reports.js e2e/cases/015-dependency-analysis.js` 通过。
- `node e2e/runner.js run --module=build-validation` 通过。
- `node e2e/runner.js run --module=report` 通过。
- `node e2e/runner.js run --module=dependency-analysis` 未进入业务断言：当前 shell 未配置真实 x86/riscv SSH 环境变量，runner 按 runId 完成清理。
